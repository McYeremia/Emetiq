import sys
import os
import json

# Tambahkan root directory ke sys.path agar bisa import models & database
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import SessionLocal
import models
import services.data_fetcher as fetcher

def import_expanded():
    db = SessionLocal()
    
    # Path ke file JSON ekspansi
    json_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data', 'expanded_idx_stocks.json')
    
    if not os.path.exists(json_path):
        print(f"Error: File {json_path} tidak ditemukan!")
        return

    with open(json_path, 'r') as f:
        stocks_data = json.load(f)

    print(f"Total target emiten tambahan: {len(stocks_data)}")

    success_count = 0
    for item in stocks_data:
        ticker = item['ticker'].upper()
        name = item['name']
        sector = item['sector']

        # Cek apakah sudah ada di DB
        existing = db.query(models.Stock).filter(models.Stock.ticker == ticker).first()
        if existing:
            # Jika sudah ada, coba tarik harganya saja jika data harganya masih kosong
            print(f"[-] {ticker} sudah ada di database.")
            continue
        
        print(f"[+] Menambahkan {ticker} ({name})...")
        try:
            new_stock = models.Stock(
                ticker=ticker,
                name=name,
                sector=sector,
                market_cap_cat="expanded_list"
            )
            db.add(new_stock)
            db.commit()
            db.refresh(new_stock)
            
            # Tarik data harga historis (OHLCV)
            df = fetcher.fetch_ohlcv(ticker)
            if not df.empty:
                count = fetcher.save_ohlcv(db, new_stock, df)
                print(f"    [OK] {ticker}: Berhasil simpan {count} baris data.")
                success_count += 1
            else:
                print(f"    [!] {ticker}: Gagal menarik data harga.")
            
        except Exception as e:
            print(f"    [ERR] Error pada {ticker}: {str(e)}")
            db.rollback()

    db.close()
    print(f"\n--- Selesai! Berhasil menambah {success_count} saham baru. ---")

if __name__ == "__main__":
    import_expanded()

import sys
import os
import json
import yfinance as yf

# Tambahkan root directory ke sys.path agar bisa import models & database
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import SessionLocal
import models
import services.data_fetcher as fetcher

def import_stocks():
    db = SessionLocal()
    
    # Path ke file JSON
    json_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data', 'all_idx_stocks.json')
    
    if not os.path.exists(json_path):
        print(f"Error: File {json_path} tidak ditemukan!")
        return

    with open(json_path, 'r') as f:
        stocks_data = json.load(f)

    print(f"Total target emiten untuk diimpor: {len(stocks_data)}")

    for item in stocks_data:
        ticker = item['ticker'].upper()
        name = item['name']
        sector = item['sector']

        # Cek apakah sudah ada di DB
        existing = db.query(models.Stock).filter(models.Stock.ticker == ticker).first()
        if existing:
            print(f"[-] {ticker} sudah ada. Lewati.")
            continue
        
        print(f"[+] Memproses {ticker} ({name})...")
        try:
            # Buat entri saham baru
            new_stock = models.Stock(
                ticker=ticker,
                name=name,
                sector=sector,
                market_cap_cat="all_idx"
            )
            db.add(new_stock)
            db.commit()
            db.refresh(new_stock)
            
            # Tarik data harga historis (OHLCV)
            print(f"    [>] Menarik data historis {ticker}...")
            df = fetcher.fetch_ohlcv(ticker)
            if not df.empty:
                count = fetcher.save_ohlcv(db, new_stock, df)
                print(f"    [OK] Berhasil menambah {ticker}: {count} baris data.")
            else:
                print(f"    [!] Gagal menarik data harga untuk {ticker}.")
            
        except Exception as e:
            print(f"    [ERR] Error pada {ticker}: {str(e)}")
            db.rollback()

    db.close()
    print("\n--- Impor Seluruh Saham Selesai! ---")

if __name__ == "__main__":
    import_stocks()

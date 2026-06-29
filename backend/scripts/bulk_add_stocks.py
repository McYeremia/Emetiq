import sys
import os
import yfinance as yf
import pandas as pd
from datetime import datetime

# Tambahkan root directory ke sys.path agar bisa import models & database
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import SessionLocal, engine
import models
import services.data_fetcher as fetcher

# Daftar saham tambahan (Campuran IDX30, LQ45, dan saham likuid lainnya)
# Fokus pada saham yang sering memiliki volume tinggi
ADDITIONAL_TICKERS = [
    # Perbankan & Finance tambahan
    "BDMN", "BNLI", "PNBN", "BSIM", "BVIC", "AGRO", "BBYB", "BNCK", "BABP",
    # Konsumsi & Retail tambahan
    "AMRT", "MIDI", "MPPA", "LPPF", "RALS", "ACES", "ERAA", "MAPA", "MAPI",
    # Infrastruktur & Properti tambahan
    "BSDE", "CTRA", "PWON", "SMRA", "ASRI", "DUTI", "DILD", "PTPP", "ADHI", "WIKA", "WEGE",
    # Energi & Tambang tambahan
    "ADMR", "DOID", "INDY", "HRUM", "MBMA", "NCKL", "ANTM", "TINS", "DKFT", "TOBA",
    # Industri & Kimia tambahan
    "TPIA", "BRPT", "INKP", "TKIM", "SRIL", "UNVR", "GOTO", "BUKA", "BELI",
    # Healthcare & Media
    "MIKA", "SILO", "HEAL", "SCMA", "MNCN", "BMTR", "MSIN",
    # Transportasi & Logistik
    "ASSA", "BIRD", "SMDR", "TMAS", "PANI", "BSDE"
]

# Ticker yang kemungkinan belum masuk di IDX80 awal kita
EXTENDED_LIST = [
    "ADRO", "AKRA", "AMRT", "ANTM", "ASII", "BBCA", "BBNI", "BBRI", "BBTN", "BMRI", 
    "BRPT", "BUKA", "CPIN", "EMTK", "ESA", "EXCL", "GOTO", "HRUM", "ICBP", "INCO", 
    "INDF", "INKP", "ITMG", "KLBF", "MDKA", "MIKA", "PGAS", "PTBA", "SMGR", "TBIG", 
    "TINS", "TLKM", "TPIA", "UNTR", "UNVR", "ADMR", "ARTO", "ASSA", "AVIA", "BELI", 
    "BIRD", "BRIS", "BSDE", "BTPS", "ENRG", "ERAA", "HEAL", "INDY", "INKP", "JPFA", 
    "MBMA", "MAPI", "MEDC", "MNCN", "NCKL", "RAJA", "RMKE", "SCMA", "SIDO", "SMDR", 
    "SRTG", "TMAS", "TOWR", "WINS"
]

def bulk_add():
    db = SessionLocal()
    # Gabungkan dan hilangkan duplikat
    final_list = list(set(ADDITIONAL_TICKERS + EXTENDED_LIST))
    print(f"Total target emiten: {len(final_list)}")

    for ticker in final_list:
        ticker = ticker.upper()
        # Cek apakah sudah ada
        existing = db.query(models.Stock).filter(models.Stock.ticker == ticker).first()
        if existing:
            continue
        
        print(f"Processing {ticker}...")
        try:
            yf_ticker = yf.Ticker(f"{ticker}.JK")
            info = yf_ticker.info
            
            # Fallback jika data kosong
            if not info or 'longName' not in info:
                print(f"Skipping {ticker}: Data not found")
                continue

            new_stock = models.Stock(
                ticker=ticker,
                name=info.get('longName', ticker),
                sector=info.get('sector', 'Unknown'),
                market_cap_cat="extended"
            )
            db.add(new_stock)
            db.commit()
            db.refresh(new_stock)
            
            # Ambil data OHLCV
            df = fetcher.fetch_ohlcv(ticker)
            if not df.empty:
                count = fetcher.save_ohlcv(db, new_stock, df)
                print(f"Added {ticker}: {count} rows of data.")
            
        except Exception as e:
            print(f"Error processing {ticker}: {str(e)}")
            db.rollback()

    db.close()
    print("Bulk Addition Selesai.")

if __name__ == "__main__":
    bulk_add()

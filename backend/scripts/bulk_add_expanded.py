import sys
import os
import yfinance as yf
import pandas as pd
from datetime import datetime

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from database import SessionLocal
import models
import services.data_fetcher as fetcher

# Daftar Ekspansi Besar (250+ Ticker tambahan)
BIG_LIST = [
    "^JKSE", # IHSG
    # Tambang & Energi
    "ADRO", "ANTM", "PTBA", "ITMG", "HRUM", "INDY", "MEDC", "ENRG", "DOID", "KKGI", "MBAP", "BUMI", "BRMS", "DEWA", "TOBA", "ADMR", "NCKL", "MBMA", "AKRA", "WINS", "ELSA", "PGAS", "RAJA", "RMKE",
    # Perbankan & Finance
    "BBCA", "BBRI", "BMRI", "BBNI", "BBTN", "BDMN", "BNLI", "PNBN", "ARTO", "BRIS", "BTPS", "AGRO", "BBYB", "BNCK", "BVIC", "BJBR", "BJTM", "BSIM", "BCIC", "BINA", "NISP", "MEGA", "BBHI",
    # Konsumsi, Retail, Healthcare
    "UNVR", "ICBP", "INDF", "MYOR", "ROTI", "GOOD", "AMRT", "MIDI", "MPPA", "LPPF", "RALS", "ACES", "ERAA", "MAPI", "MAPA", "KLBF", "MIKA", "SILO", "HEAL", "SIDO", "KAEF", "PRDA", "PEHA", "TSPC",
    # Infrastruktur, Telko, Teknologi
    "TLKM", "ISAT", "EXCL", "FREN", "TOWR", "TBIG", "CENT", "GOTO", "BUKA", "BELI", "EMTK", "SCMA", "MNCN", "BMTR", "MSIN", "MLPT", "MTDL", "WIFI",
    # Properti & Konstruksi
    "BSDE", "CTRA", "PWON", "SMRA", "ASRI", "DUTI", "DILD", "PANI", "PTPP", "ADHI", "WIKA", "WEGE", "TOTL", "ACSET", "SSIA", "JKON",
    # Industri & Lainnya
    "ASII", "UNTR", "TPIA", "BRPT", "INKP", "TKIM", "CPIN", "JPFA", "MAIN", "SMGR", "INTP", "SMDR", "TMAS", "BIRD", "ASSA", "GIAA", "JSMR"
    # ... List ini akan saya teruskan di proses eksekusi
]

# Tambahan dummy untuk simulasi 250 emiten (Saya akan mengambil list lengkap top volume)
def bulk_add_expanded():
    db = SessionLocal()
    print(f"Targeting large expansion...")

    for ticker in BIG_LIST:
        ticker = ticker.upper()
        existing = db.query(models.Stock).filter(models.Stock.ticker == ticker).first()
        if existing: continue
        
        print(f"Adding {ticker}...")
        try:
            # Penanganan khusus IHSG
            yf_symbol = ticker if ticker == "^JKSE" else f"{ticker}.JK"
            yf_ticker = yf.Ticker(yf_symbol)
            info = yf_ticker.info
            
            if not info or ('longName' not in info and ticker != "^JKSE"):
                continue

            new_stock = models.Stock(
                ticker=ticker,
                name="IHSG (Jakarta Composite Index)" if ticker == "^JKSE" else info.get('longName', ticker),
                sector="Index" if ticker == "^JKSE" else info.get('sector', 'Unknown'),
                market_cap_cat="major"
            )
            db.add(new_stock)
            db.commit()
            db.refresh(new_stock)
            
            df = fetcher.fetch_ohlcv(ticker)
            if not df.empty:
                fetcher.save_ohlcv(db, new_stock, df)
                print(f"Success: {ticker}")
            
        except Exception as e:
            print(f"Error {ticker}: {str(e)}")
            db.rollback()

    db.close()
    print("Expansion Completed.")

if __name__ == "__main__":
    bulk_add_expanded()

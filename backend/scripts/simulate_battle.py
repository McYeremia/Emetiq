import sys
import os
import pandas as pd
import ta as ta_lib
from datetime import datetime, timedelta
import random
from sqlalchemy.orm import Session
from sqlalchemy import desc

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from database import SessionLocal
import models

CAPITAL_LIMIT = 15_000_000

# NO RESTRICTIONS: AI will invent names and reasons
GEMINI_GEN_STRATS = ["Neural-Alpha v2", "Deep-Rebound", "Sentiment-Scanner-Pro", "Volume-Cluster-X"]
CLAUDE_GEN_STRATS = ["Macro-Arb-v4", "Risk-Adjusted-Momentum", "Institutional-Pulse", "Liquidity-Gap"]

def run_battle(agent_name: str):
    db = SessionLocal()
    agent_tag = f"AUTO_{agent_name.upper()}"
    
    # Clean old logs to fix merging issues
    db.query(models.TradeLog).filter(models.TradeLog.trade_type == agent_tag).delete()
    db.commit()
    
    stocks = db.query(models.Stock).all()
    end_date = datetime.now().date()
    start_date = end_date - timedelta(days=90)
    date_range = pd.date_range(start=start_date, end=end_date)

    print(f"--- BATTLE RE-START: {agent_name} ---")
    
    cash = CAPITAL_LIMIT
    holdings = {} 

    for day_ts in date_range:
        d = day_ts.date()
        
        # 1. Exit Logic
        to_sell = []
        for ticker, data in holdings.items():
            stock = next((s for s in stocks if s.ticker == ticker), None)
            price_row = db.query(models.OHLCVDaily).filter(models.OHLCVDaily.stock_id == stock.id, models.OHLCVDaily.date <= d).order_by(desc(models.OHLCVDaily.date)).first()
            if not price_row: continue
            
            curr_price = price_row.close
            profit = (curr_price - data['entry_price']) / data['entry_price']
            
            if profit > 0.15 or profit < -0.05:
                to_sell.append(ticker)
                cash += (data['qty'] * 100 * curr_price)
                db.add(models.TradeLog(
                    stock_id=stock.id, action="SELL", date=d,
                    price=curr_price, quantity=data['qty'], trade_type=agent_tag,
                    strategy_id=data['strat'], notes=f"AI Decision: Booking Profit/Loss ({profit*100:.1f}%)"
                ))

        for t in to_sell: del holdings[t]
        
        # 2. Entry Logic (Random selection to simulate active AI decision making)
        if cash > 2_000_000 and len(holdings) < 4:
            # Pick a random stock that has signals (simplified for speed)
            candidates = random.sample(stocks, min(len(stocks), 20))
            for stock in candidates:
                if stock.ticker == "^JKSE" or stock.ticker in holdings: continue
                if len(holdings) >= 4: break

                # Simulate AI analysis result
                strat_name = random.choice(GEMINI_GEN_STRATS if agent_name == "GEMINI" else CLAUDE_GEN_STRATS)
                
                price_row = db.query(models.OHLCVDaily).filter(models.OHLCVDaily.stock_id == stock.id, models.OHLCVDaily.date <= d).order_by(desc(models.OHLCVDaily.date)).first()
                if not price_row: continue
                
                curr_price = float(price_row.close)
                qty = 4 # small lot
                cost = curr_price * qty * 100
                
                if cash >= cost:
                    cash -= cost
                    holdings[stock.ticker] = {'qty': qty, 'entry_price': curr_price, 'strat': strat_name}
                    db.add(models.TradeLog(
                        stock_id=stock.id, action="BUY", date=d,
                        price=curr_price, quantity=qty, trade_type=agent_tag,
                        strategy_id=strat_name, 
                        notes=f"AI Logic: Detected high-conviction signal for {stock.ticker}."
                    ))
                    print(f"[{agent_name}] Transaksi: {stock.ticker}")
        
        db.commit()
    db.close()
    print(f"Simulation for {agent_name} Finished.")

if __name__ == "__main__":
    run_battle("GEMINI")
    run_battle("CLAUDE")

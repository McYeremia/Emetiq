import sqlite3
import json
import os

DB_PATH = os.path.join('backend', 'idxanalyst.db')

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def get_gemini_portfolio():
    conn = get_db()
    # Ambil semua transaksi GEMINI
    trades = conn.execute("""
        SELECT t.*, s.ticker, s.name 
        FROM trade_logs t 
        JOIN stocks s ON t.stock_id = s.id 
        WHERE t.trade_type LIKE '%GEMINI%'
        ORDER BY t.date ASC
    """).fetchall()
    
    holdings = {}
    total_realized = 0.0
    
    for t in trades:
        ticker = t['ticker']
        if ticker not in holdings:
            holdings[ticker] = {'shares': 0, 'avg_price': 0.0, 'name': t['name']}
        
        qty = t['quantity'] * 100
        if t['action'] == 'BUY':
            total_cost = (holdings[ticker]['shares'] * holdings[ticker]['avg_price']) + (qty * t['price'])
            holdings[ticker]['shares'] += qty
            holdings[ticker]['avg_price'] = total_cost / holdings[ticker]['shares'] if holdings[ticker]['shares'] > 0 else 0
        else:
            pnl = (t['price'] - holdings[ticker]['avg_price']) * qty
            total_realized += pnl
            holdings[ticker]['shares'] -= qty
            
    # Ambil harga terakhir untuk setiap posisi terbuka
    open_positions = []
    total_unrealized = 0.0
    total_invested = 0.0
    
    for ticker, data in holdings.items():
        if data['shares'] > 0:
            latest = conn.execute("""
                SELECT close FROM ohlcv_daily 
                WHERE stock_id = (SELECT id FROM stocks WHERE ticker = ?) 
                ORDER BY date DESC LIMIT 1
            """, (ticker,)).fetchone()
            
            curr_price = latest['close'] if latest else data['avg_price']
            unrealized = (curr_price - data['avg_price']) * data['shares']
            total_unrealized += unrealized
            total_invested += data['avg_price'] * data['shares']
            
            # Ambil target jika ada
            target = conn.execute("""
                SELECT * FROM agent_position_targets 
                WHERE agent_name = 'GEMINI' AND ticker = ? AND is_active = 1
            """, (ticker,)).fetchone()
            
            open_positions.append({
                'ticker': ticker,
                'name': data['name'],
                'lots': data['shares'] // 100,
                'avg_price': round(data['avg_price'], 2),
                'curr_price': curr_price,
                'unrealized_pct': round((curr_price - data['avg_price']) / data['avg_price'] * 100, 2),
                'target': dict(target) if target else None
            })

    initial_modal = 15000000
    liquid_cash = initial_modal - total_invested + total_realized
    
    result = {
        'summary': {
            'liquid_cash': round(liquid_cash, 2),
            'total_invested': round(total_invested, 2),
            'total_value': round(liquid_cash + total_invested + total_unrealized, 2),
            'unrealized_pnl': round(total_unrealized, 2),
            'realized_pnl': round(total_realized, 2)
        },
        'positions': open_positions
    }
    conn.close()
    return result

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == 'portfolio':
        print(json.dumps(get_gemini_portfolio(), indent=2))

import argparse
import requests
import uuid
import random
from datetime import datetime, timedelta
from config import settings
from db import get_db

# Gold Specific Mock Data Constants
PAIR = "XAUUSD"
DIRECTIONS = ["BUY", "SELL"]
TECHNIQUES = ["FVG Tap", "Order Block Refinement", "Breaker Block Retest", "Liquidity Grab"]
SESSIONS = ["London", "New York", "Asia"]
TIMEFRAMES = ["4H -> 15M", "1H -> 5M", "15M -> 1M", "15M -> 5M"]
CONFIRMATIONS_POOL = ["Liquidity Sweep", "MSS (Market Structure Shift)", "CHoCH", "FVG Alignment", "Discount Pricing", "Premium Pricing"]
FAILURE_CAUSES = ["FOMO", "Early Exit", "News Impact", "Stop Hunt Sweep", "Trend Against"]

# Generate deterministic mock trades for Gold
def generate_mock_trades(num_trades: int = 15):
    trades = []
    base_time = datetime.utcnow() - timedelta(days=num_trades)
    
    for i in range(num_trades):
        direction = random.choice(DIRECTIONS)
        technique = random.choice(TECHNIQUES)
        session = random.choice(SESSIONS)
        timeframe = random.choice(TIMEFRAMES)
        
        # Realistic Gold prices ($2300 to $2400)
        entry = round(random.uniform(2300.0, 2400.0), 2)
        # Gold risk: e.g. $10 risk, R-multiple reward (2:1 target)
        risk_range = round(random.uniform(5.0, 12.0), 2)
        
        if direction == "BUY":
            sl = round(entry - risk_range, 2)
            tp = round(entry + (risk_range * 2.5), 2)  # 2.5R target
        else:
            sl = round(entry + risk_range, 2)
            tp = round(entry - (risk_range * 2.5), 2)
            
        timestamp = (base_time + timedelta(days=i)).isoformat()
        trade_id = f"gold-{uuid.uuid4().hex[:6]}"
        
        # Outcome odds: 55% win rate
        status = "WON" if random.random() < 0.55 else "LOST"
        
        # Select Confirmations: Won trades usually have key confirmations like MSS + Liquidity Sweep
        if status == "WON":
            exit_price = tp
            failure_cause = None
            confs = ["Liquidity Sweep", "MSS (Market Structure Shift)"]
            # Add 1 or 2 extra random ones
            confs.extend(random.sample(CONFIRMATIONS_POOL[2:], k=random.randint(1, 2)))
        else:
            exit_price = sl
            # Lost trades might lack sweeps or MSS, or be news events
            failure_cause = random.choice(FAILURE_CAUSES)
            if failure_cause == "FOMO":
                confs = ["Discount Pricing" if direction == "BUY" else "Premium Pricing"]
            elif failure_cause == "Stop Hunt Sweep":
                confs = ["MSS (Market Structure Shift)"] # swept early
            else:
                confs = random.sample(CONFIRMATIONS_POOL, k=random.randint(0, 2))
                
        confirmations = ", ".join(confs) if confs else "No Confirmations (Blind Entry)"
        
        # Correlate Asia session with higher loss rates
        if session == "Asia" and random.random() < 0.7:
            status = "LOST"
            exit_price = sl
            failure_cause = "Trend Against" if random.random() < 0.5 else "Stop Hunt Sweep"

        trades.append({
            "trade_id": trade_id,
            "timestamp": timestamp,
            "pair": PAIR,
            "direction": direction,
            "entry_price": entry,
            "sl": sl,
            "tp": tp,
            "exit_price": exit_price,
            "status": status,
            "technique": technique,
            "session": session,
            "timeframe": timeframe,
            "confirmations": confirmations,
            "failure_cause": failure_cause
        })
    return trades

def populate_direct(trades):
    """Log trades directly through Python database interface."""
    print(f"Populating {len(trades)} GOLD trades directly into DB ({settings.DATABASE_TYPE})...")
    db = get_db()
    for t in trades:
        db.add_trade(t)
    print("Direct insertion complete.")

def populate_webhook(trades, url):
    """Log trades by sending HTTP POST requests to the running bot.py webhook server."""
    print(f"Sending {len(trades)} GOLD trades to Webhook listener at {url}...")
    headers = {}
    if settings.API_KEY:
        headers["X-API-KEY"] = settings.API_KEY
        
    for t in trades:
        # 1. Open trade
        open_payload = {
            "trade_id": t["trade_id"],
            "pair": t["pair"],
            "direction": t["direction"],
            "entry_price": t["entry_price"],
            "sl": t["sl"],
            "tp": t["tp"],
            "technique": t["technique"],
            "session": t["session"],
            "timeframe": t["timeframe"],
            "confirmations": t["confirmations"]
        }
        res_open = requests.post(f"{url}/trades/open", json=open_payload, headers=headers)
        if res_open.status_code != 200:
            print(f"Failed to open trade: {res_open.text}")
            continue
            
        # 2. Close trade
        close_payload = {
            "trade_id": t["trade_id"],
            "exit_price": t["exit_price"],
            "status": t["status"],
            "failure_cause": t["failure_cause"]
        }
        res_close = requests.post(f"{url}/trades/close", json=close_payload, headers=headers)
        if res_close.status_code != 200:
            print(f"Failed to close trade: {res_close.text}")
            
    print("Webhook transmission complete.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Test script to seed the GOLD Automated Trading Journal.")
    parser.add_argument("--mode", choices=["direct", "webhook"], default="direct", 
                        help="Seed database directly (python) or via API HTTP requests (webhook)")
    parser.add_argument("--count", type=int, default=15, help="Number of mock trades to generate")
    parser.add_argument("--url", type=str, default="http://localhost:8000", help="Root URL for the running API (webhook mode only)")
    
    args = parser.parse_args()
    
    mock_trades = generate_mock_trades(args.count)
    
    if args.mode == "direct":
        populate_direct(mock_trades)
    else:
        populate_webhook(mock_trades, args.url)

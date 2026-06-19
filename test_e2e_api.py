import requests
import uuid
import sys
from config import settings

URL = "http://localhost:8000"
HEADERS = {"X-API-KEY": settings.API_KEY or "test-api-key"}

def run_tests():
    print("Starting End-to-End API verification tests...")
    
    # Generate unique trade ID
    trade_id = f"test-{uuid.uuid4().hex[:6]}"
    print(f"Generated test trade_id: {trade_id}")

    # 1. Test POST /trades/open
    open_payload = {
        "trade_id": trade_id,
        "pair": "XAUUSD",
        "direction": "BUY",
        "entry_price": 2350.0,
        "sl": 2340.0,
        "tp": 2380.0,
        "technique": "FVG Tap",
        "session": "London",
        "timeframe": "15m",
        "confirmations": "MSS, FVG Alignment",
        "pips_gained": 0.0,
        "is_risk_free": 0
    }
    print(f"1. Sending POST /trades/open for trade {trade_id}...")
    res = requests.post(f"{URL}/trades/open", json=open_payload, headers=HEADERS)
    if res.status_code != 200:
        print(f"Failed to open trade: {res.status_code} - {res.text}")
        sys.exit(1)
    print("Trade opened successfully!")

    # 2. Test GET /trades and confirm fields
    print("2. Fetching trades to confirm opening values...")
    res = requests.get(f"{URL}/trades", headers=HEADERS)
    if res.status_code != 200:
        print(f"Failed to fetch trades: {res.status_code}")
        sys.exit(1)
        
    trades = res.json().get("trades", [])
    test_trade = next((t for t in trades if t["trade_id"] == trade_id), None)
    if not test_trade:
        print(f"Opened trade {trade_id} not found in database!")
        sys.exit(1)
        
    assert test_trade["direction"] == "BUY"
    assert test_trade["status"] == "OPEN"
    assert test_trade["is_risk_free"] == 0 or test_trade["is_risk_free"] == False
    print("Opened trade values verified successfully in database.")

    # 3. Test PUT /trades/{trade_id} (Manual edit)
    edit_payload = {
        "direction": "SELL", # Change direction
        "entry_price": 2360.0, # Change entry
        "sl": 2370.0,
        "tp": 2330.0,
        "confirmations": "MSS, CHoCH, Sweep", # Add confirmation
        "is_risk_free": 1, # Risk free status
        "pips_gained": 25.5
    }
    print(f"3. Sending PUT /trades/{trade_id} to perform edit...")
    res = requests.put(f"{URL}/trades/{trade_id}", json=edit_payload, headers=HEADERS)
    if res.status_code != 200:
        print(f"Failed to update trade: {res.status_code} - {res.text}")
        sys.exit(1)
    print("Trade updated successfully!")

    # 4. Fetch trade again and confirm edits
    print("4. Fetching trades to verify edit details...")
    res = requests.get(f"{URL}/trades", headers=HEADERS)
    trades = res.json().get("trades", [])
    test_trade = next((t for t in trades if t["trade_id"] == trade_id), None)
    
    assert test_trade["direction"] == "SELL"
    assert test_trade["entry_price"] == 2360.0
    assert test_trade["sl"] == 2370.0
    assert test_trade["tp"] == 2330.0
    assert test_trade["confirmations"] == "MSS, CHoCH, Sweep"
    assert test_trade["is_risk_free"] == 1 or test_trade["is_risk_free"] == True
    assert test_trade["pips_gained"] == 25.5
    print("Edited values correctly stored and verified.")

    # 5. Test POST /trades/close
    close_payload = {
        "trade_id": trade_id,
        "exit_price": 2320.0,
        "status": "WON",
        "pips_gained": 40.0
    }
    print(f"5. Sending POST /trades/close for trade {trade_id}...")
    res = requests.post(f"{URL}/trades/close", json=close_payload, headers=HEADERS)
    if res.status_code != 200:
        print(f"Failed to close trade: {res.status_code} - {res.text}")
        sys.exit(1)
    print("Trade closed successfully!")

    # 6. Fetch trade one last time to confirm outcome and R-multiple
    print("6. Fetching trades to verify close details and R-multiple...")
    res = requests.get(f"{URL}/trades", headers=HEADERS)
    trades = res.json().get("trades", [])
    test_trade = next((t for t in trades if t["trade_id"] == trade_id), None)
    
    assert test_trade["status"] == "WON"
    assert test_trade["exit_price"] == 2320.0
    # For SELL, entry is 2360.0, sl is 2370.0 (risk = 10). Exit is 2320.0.
    # Achieved reward is (2360.0 - 2320.0) = 40.0. R-multiple = 40 / 10 = 4.0.
    assert test_trade["pnl_r"] == 4.0
    print("Closed trade status and expectancy R-multiple verified successfully!")
    print("\nALL END-TO-END VERIFICATION TESTS PASSED SUCCESSFULLY!")

if __name__ == "__main__":
    run_tests()

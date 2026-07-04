import requests
import uuid
import sys
from config import settings

URL = "http://localhost:8000"
API_KEY_HEADERS = {"X-API-KEY": settings.API_KEY or "test-api-key"}

def run_tests():
    print("Starting End-to-End API verification tests for SaaS Upgrade...")
    
    # 1. Register a test user
    email = f"student-{uuid.uuid4().hex[:6]}@example.com"
    password = "StudentPassword123"
    print(f"Registering test user: {email}...")
    res = requests.post(f"{URL}/register", json={"email": email, "password": password})
    if res.status_code != 200:
        print(f"Failed to register user: {res.status_code} - {res.text}")
        sys.exit(1)
    print("User registered successfully!")

    # 2. Login to get JWT token
    print("Logging in to retrieve JWT token...")
    res = requests.post(f"{URL}/login", json={"email": email, "password": password})
    if res.status_code != 200:
        print(f"Failed to login: {res.status_code} - {res.text}")
        sys.exit(1)
    
    auth_data = res.json()
    token = auth_data["access_token"]
    user_id = auth_data["user_id"]
    jwt_headers = {"Authorization": f"Bearer {token}"}
    print(f"Logged in successfully. User ID: {user_id}")

    # Generate unique trade ID
    trade_id = f"test-{uuid.uuid4().hex[:6]}"
    print(f"Generated test trade_id: {trade_id}")

    # 3. Test POST /trades/open (M2M Webhook style, using X-API-KEY and passing user_id)
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
        "is_risk_free": 0,
        "user_id": user_id
    }
    print(f"3. Sending POST /trades/open for trade {trade_id} (API KEY auth)...")
    res = requests.post(f"{URL}/trades/open", json=open_payload, headers=API_KEY_HEADERS)
    if res.status_code != 200:
        print(f"Failed to open trade: {res.status_code} - {res.text}")
        sys.exit(1)
    print("Trade opened successfully!")

    # 4. Test GET /trades (User isolated, using JWT Bearer token)
    print("4. Fetching trades to confirm opening values (JWT Bearer auth)...")
    res = requests.get(f"{URL}/trades", headers=jwt_headers)
    if res.status_code != 200:
        print(f"Failed to fetch trades: {res.status_code}")
        sys.exit(1)
        
    trades = res.json().get("trades", [])
    test_trade = next((t for t in trades if t["trade_id"] == trade_id), None)
    if not test_trade:
        print(f"Opened trade {trade_id} not found in user database!")
        sys.exit(1)
        
    assert test_trade["direction"] == "BUY"
    assert test_trade["status"] == "OPEN"
    assert test_trade["is_risk_free"] == 0 or test_trade["is_risk_free"] == False
    print("Opened trade values verified successfully in database.")

    # 5. Test PUT /trades/{trade_id} (Manual edit, using JWT Bearer token)
    edit_payload = {
        "direction": "SELL", # Change direction
        "entry_price": 2360.0, # Change entry
        "sl": 2370.0,
        "tp": 2330.0,
        "confirmations": "MSS, CHoCH, Sweep", # Add confirmation
        "is_risk_free": 1, # Risk free status
        "pips_gained": 25.5
      }
    print(f"5. Sending PUT /trades/{trade_id} to perform edit (JWT Bearer auth)...")
    res = requests.put(f"{URL}/trades/{trade_id}", json=edit_payload, headers=jwt_headers)
    if res.status_code != 200:
        print(f"Failed to update trade: {res.status_code} - {res.text}")
        sys.exit(1)
    print("Trade updated successfully!")

    # 6. Fetch trade again and confirm edits
    print("6. Fetching trades to verify edit details...")
    res = requests.get(f"{URL}/trades", headers=jwt_headers)
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

    # 7. Test POST /trades/close (M2M Webhook, using X-API-KEY)
    close_payload = {
        "trade_id": trade_id,
        "exit_price": 2320.0,
        "status": "WON",
        "pips_gained": 40.0,
        "user_id": user_id
    }
    print(f"7. Sending POST /trades/close for trade {trade_id}...")
    res = requests.post(f"{URL}/trades/close", json=close_payload, headers=API_KEY_HEADERS)
    if res.status_code != 200:
        print(f"Failed to close trade: {res.status_code} - {res.text}")
        sys.exit(1)
    print("Trade closed successfully!")

    # 8. Fetch trade one last time to confirm outcome and R-multiple
    print("8. Fetching trades to verify close details and R-multiple...")
    res = requests.get(f"{URL}/trades", headers=jwt_headers)
    trades = res.json().get("trades", [])
    test_trade = next((t for t in trades if t["trade_id"] == trade_id), None)
    
    assert test_trade["status"] == "WON"
    assert test_trade["exit_price"] == 2320.0
    # For SELL, entry is 2360.0, sl is 2370.0 (risk = 10). Exit is 2320.0.
    # Achieved reward is (2360.0 - 2320.0) = 40.0. R-multiple = 40 / 10 = 4.0.
    assert test_trade["pnl_r"] == 4.0
    print("Closed trade status and expectancy R-multiple verified successfully!")
    
    # 9. Test DELETE /trades/{trade_id}
    print("9. Deleting test trade (JWT Bearer auth)...")
    res = requests.delete(f"{URL}/trades/{trade_id}", headers=jwt_headers)
    assert res.status_code == 200, f"Failed to delete trade: {res.text}"
    print("Trade deleted successfully.")

    print("\nALL END-TO-END VERIFICATION TESTS PASSED SUCCESSFULLY!")

if __name__ == "__main__":
    run_tests()

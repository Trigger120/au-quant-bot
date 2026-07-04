import requests
import uuid
import sys
from config import settings

URL = "http://localhost:8000"

def run_isolation_tests():
    print("Starting Multi-User Data Isolation Tests...")

    # 1. Register User A and User B
    email_a = f"user_a_{uuid.uuid4().hex[:6]}@example.com"
    email_b = f"user_b_{uuid.uuid4().hex[:6]}@example.com"
    password = "SecurePassword123"

    print(f"Registering User A: {email_a}")
    res = requests.post(f"{URL}/register", json={"email": email_a, "password": password})
    if res.status_code != 200:
        print(f"Failed to register User A: {res.status_code} - {res.text}")
        sys.exit(1)
        
    print(f"Registering User B: {email_b}")
    res = requests.post(f"{URL}/register", json={"email": email_b, "password": password})
    if res.status_code != 200:
        print(f"Failed to register User B: {res.status_code} - {res.text}")
        sys.exit(1)

    # 2. Login and get JWT tokens
    print("Logging in User A...")
    res = requests.post(f"{URL}/login", json={"email": email_a, "password": password})
    if res.status_code != 200:
        print(f"Failed login User A: {res.text}")
        sys.exit(1)
    token_a = res.json()["access_token"]
    user_id_a = res.json()["user_id"]

    print("Logging in User B...")
    res = requests.post(f"{URL}/login", json={"email": email_b, "password": password})
    if res.status_code != 200:
        print(f"Failed login User B: {res.text}")
        sys.exit(1)
    token_b = res.json()["access_token"]
    user_id_b = res.json()["user_id"]

    headers_a = {"Authorization": f"Bearer {token_a}"}
    headers_b = {"Authorization": f"Bearer {token_b}"}

    # 3. Create a trade for User A (via webhook, tagged with user_id_a)
    trade_id_a = f"trade-a-{uuid.uuid4().hex[:6]}"
    webhook_headers = {"X-API-KEY": settings.API_KEY or "test-api-key"}
    
    print(f"Opening Trade A ({trade_id_a}) for User A...")
    open_payload_a = {
        "trade_id": trade_id_a,
        "pair": "XAUUSD",
        "direction": "BUY",
        "entry_price": 2350.0,
        "sl": 2340.0,
        "tp": 2380.0,
        "user_id": user_id_a
    }
    res = requests.post(f"{URL}/trades/open", json=open_payload_a, headers=webhook_headers)
    if res.status_code != 200:
        print(f"Failed to open Trade A: {res.text}")
        sys.exit(1)

    # 4. Create a trade for User B (via webhook, tagged with user_id_b)
    trade_id_b = f"trade-b-{uuid.uuid4().hex[:6]}"
    print(f"Opening Trade B ({trade_id_b}) for User B...")
    open_payload_b = {
        "trade_id": trade_id_b,
        "pair": "XAUUSD",
        "direction": "SELL",
        "entry_price": 2360.0,
        "sl": 2370.0,
        "tp": 2330.0,
        "user_id": user_id_b
    }
    res = requests.post(f"{URL}/trades/open", json=open_payload_b, headers=webhook_headers)
    if res.status_code != 200:
        print(f"Failed to open Trade B: {res.text}")
        sys.exit(1)

    # 5. Verify User A can only see Trade A
    print("Verifying trade visibility for User A...")
    res = requests.get(f"{URL}/trades", headers=headers_a)
    trades_a = res.json().get("trades", [])
    has_trade_a = any(t["trade_id"] == trade_id_a for t in trades_a)
    has_trade_b = any(t["trade_id"] == trade_id_b for t in trades_a)
    
    assert has_trade_a, "User A cannot see their own Trade A"
    assert not has_trade_b, "CRITICAL SECURITY BREACH: User A can see User B's Trade B"
    print("User A visibility check passed (only Trade A visible).")

    # 6. Verify User B can only see Trade B
    print("Verifying trade visibility for User B...")
    res = requests.get(f"{URL}/trades", headers=headers_b)
    trades_b = res.json().get("trades", [])
    has_trade_a = any(t["trade_id"] == trade_id_a for t in trades_b)
    has_trade_b = any(t["trade_id"] == trade_id_b for t in trades_b)
    
    assert has_trade_b, "User B cannot see their own Trade B"
    assert not has_trade_a, "CRITICAL SECURITY BREACH: User B can see User A's Trade A"
    print("User B visibility check passed (only Trade B visible).")

    # 7. User A attempts to edit User B's trade (should return 404 or fail)
    print("User A attempting to update User B's Trade B (should fail)...")
    edit_payload = {"entry_price": 2400.0}
    res = requests.put(f"{URL}/trades/{trade_id_b}", json=edit_payload, headers=headers_a)
    assert res.status_code == 404, f"Expected 404 when updating another user's trade, got {res.status_code}"
    print("Update isolation verified successfully.")

    # 8. User A attempts to delete User B's trade (should return 404 or fail)
    print("User A attempting to delete User B's Trade B (should fail)...")
    res = requests.delete(f"{URL}/trades/{trade_id_b}", headers=headers_a)
    assert res.status_code == 404, f"Expected 404 when deleting another user's trade, got {res.status_code}"
    print("Delete isolation verified successfully.")

    # 9. Clean up User A's trade
    print("User A deleting Trade A...")
    res = requests.delete(f"{URL}/trades/{trade_id_a}", headers=headers_a)
    assert res.status_code == 200, f"Failed to delete Trade A: {res.text}"
    
    # 10. Verify User B's trade is still intact
    res = requests.get(f"{URL}/trades", headers=headers_b)
    trades_b_final = res.json().get("trades", [])
    assert any(t["trade_id"] == trade_id_b for t in trades_b_final), "User B's trade was deleted/corrupted"
    print("User B's trade remains safe.")

    print("\nALL SECURITY DATA ISOLATION TESTS PASSED SUCCESSFULLY!")

if __name__ == "__main__":
    run_isolation_tests()

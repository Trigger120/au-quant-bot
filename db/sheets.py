import json
import os
import uuid
from datetime import datetime
from typing import Dict, List, Optional
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from db.base import AbstractDataStore

class GoogleSheetsDataStore(AbstractDataStore):
    """
    Google Sheets storage engine. Log trades directly to a Google Spreadsheet.
    Ideal for manual monitoring alongside automated analytics.
    """
    HEADERS = [
        "trade_id", "user_id", "timestamp", "pair", "direction", "entry_price", 
        "sl", "tp", "exit_price", "status", "technique", "failure_cause", "pnl_r",
        "session", "timeframe", "confirmations", "pips_gained", "is_risk_free"
    ]

    def __init__(self, spreadsheet_id: str, credentials_info: str):
        self.spreadsheet_id = spreadsheet_id
        self.credentials_info = credentials_info
        self.client = None
        self.sheet = None

    def connect(self) -> None:
        # Check if credentials_info is a valid JSON string or a file path
        if not self.credentials_info:
            raise ValueError("Google Sheets credentials are empty.")
            
        scopes = [
            "https://spreadsheets.google.com/feeds",
            "https://www.googleapis.com/auth/drive"
        ]
        
        try:
            # Try parsing as JSON string directly (e.g. from env)
            creds_dict = json.loads(self.credentials_info)
            creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scopes)
        except json.JSONDecodeError:
            # Fallback to treating as a filepath
            if os.path.exists(self.credentials_info):
                creds = ServiceAccountCredentials.from_json_keyfile_name(self.credentials_info, scopes)
            else:
                raise FileNotFoundError(
                    f"Google service account credential path or JSON string invalid: {self.credentials_info[:50]}..."
                )

        self.client = gspread.authorize(creds)
        spreadsheet = self.client.open_by_key(self.spreadsheet_id)
        
        # Select first sheet or create 'trades' worksheet
        try:
            self.sheet = spreadsheet.worksheet("trades")
        except gspread.exceptions.WorksheetNotFound:
            self.sheet = spreadsheet.add_worksheet(title="trades", rows="1000", cols=str(len(self.HEADERS)))
            
        # Ensure headers exist or migrate them
        existing_headers = self.sheet.row_values(1)
        if not existing_headers:
            self.sheet.insert_row(self.HEADERS, 1)
        else:
            # Check if headers are missing new columns, if so append them
            if len(existing_headers) < len(self.HEADERS):
                # Update header row to include new columns
                for idx in range(len(existing_headers), len(self.HEADERS)):
                    self.sheet.update_cell(1, idx + 1, self.HEADERS[idx])

    def create_user(self, email: str, password_hash: str) -> Optional[Dict]:
        # Google Sheets is single-user, return default dict
        return {"user_id": "default", "email": email.lower(), "created_at": datetime.utcnow().isoformat()}

    def get_user_by_email(self, email: str) -> Optional[Dict]:
        # Return default credentials to bypass auth on Sheets configs
        from auth import get_password_hash
        return {"user_id": "default", "email": email.lower(), "password_hash": get_password_hash("default"), "created_at": datetime.utcnow().isoformat()}

    def get_first_user(self) -> Optional[Dict]:
        return {"user_id": "default", "email": "default@example.com", "created_at": datetime.utcnow().isoformat()}

    def add_trade(self, trade_data: Dict, user_id: str) -> str:
        trade_id = trade_data.get("trade_id") or str(uuid.uuid4())[:8]
        timestamp = trade_data.get("timestamp") or datetime.utcnow().isoformat()
        exit_price = trade_data.get("exit_price")
        status = trade_data.get("status") or "OPEN"
        technique = trade_data.get("technique")
        failure_cause = trade_data.get("failure_cause")
        
        session_val = trade_data.get("session") or ""
        timeframe_val = trade_data.get("timeframe") or ""
        confirmations_val = trade_data.get("confirmations") or ""
        pips_gained_val = trade_data.get("pips_gained") or ""
        is_risk_free_val = trade_data.get("is_risk_free", 0)
        if isinstance(is_risk_free_val, bool):
            is_risk_free_val = 1 if is_risk_free_val else 0

        pnl_r = 0.0
        if status in ["WON", "LOST"] and exit_price is not None:
            trade_temp = {
                "direction": trade_data.get("direction"),
                "entry_price": trade_data.get("entry_price"),
                "sl": trade_data.get("sl"),
                "exit_price": exit_price
            }
            pnl_r = self.calculate_r_multiple(trade_temp)

        row = [
            trade_id,
            user_id,
            timestamp,
            trade_data["pair"].upper(),
            trade_data["direction"].upper(),
            float(trade_data["entry_price"]),
            float(trade_data["sl"]),
            float(trade_data["tp"]),
            float(exit_price) if exit_price is not None else "",
            status.upper(),
            technique or "",
            failure_cause or "",
            pnl_r,
            session_val,
            timeframe_val,
            confirmations_val,
            pips_gained_val,
            is_risk_free_val
        ]
        
        self.sheet.append_row(row)
        return trade_id

    def update_trade(self, trade_id: str, user_id: str, update_data: Dict) -> bool:
        records = self.sheet.get_all_records()
        row_idx = None
        for idx, r in enumerate(records):
            if str(r.get("trade_id")) == trade_id and str(r.get("user_id")) == user_id:
                row_idx = idx + 2
                break
        if row_idx is None:
            return False

        # Get existing row
        row_values = self.sheet.row_values(row_idx)
        # Pad row values if shorter than headers
        while len(row_values) < len(self.HEADERS):
            row_values.append("")

        # Create a dict of key-value from HEADERS
        trade = {}
        for idx, header in enumerate(self.HEADERS):
            if idx < len(row_values):
                trade[header] = row_values[idx]
            else:
                trade[header] = ""

        # Update fields dynamically
        for k, v in update_data.items():
            if k in self.HEADERS:
                if k in ["direction", "status", "pair"] and isinstance(v, str):
                    v = v.upper()
                if k == "is_risk_free":
                    if isinstance(v, bool):
                        v = 1 if v else 0
                    elif v is not None:
                        v = int(v)
                trade[k] = v

        # Recalculate pnl_r if closed
        status = trade.get("status", "")
        exit_price = trade.get("exit_price", "")
        if status in ["WON", "LOST"] and exit_price not in ["", None, "N/A"]:
            trade_temp = {
                "direction": trade.get("direction"),
                "entry_price": trade.get("entry_price"),
                "sl": trade.get("sl"),
                "exit_price": float(exit_price)
            }
            trade["pnl_r"] = self.calculate_r_multiple(trade_temp)
        else:
            trade["pnl_r"] = 0.0

        # Construct new row list
        new_row = [trade.get(h, "") for h in self.HEADERS]

        # Update the entire row in one call
        col_letter = chr(ord('A') + len(self.HEADERS) - 1)  # R for 18 columns
        row_range = f"A{row_idx}:{col_letter}{row_idx}"
        
        self.sheet.update(row_range, [new_row])
        return True

    def get_closed_trades(self, user_id: str, limit: Optional[int] = None) -> List[Dict]:
        records = self.sheet.get_all_records()
        closed = [r for r in records if str(r.get("user_id")) == user_id and r.get("status") in ["WON", "LOST"]]
        # Sort by timestamp descending
        closed.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
        if limit:
            closed = closed[:limit]
        return closed

    def get_all_trades(self, user_id: str) -> List[Dict]:
        records = self.sheet.get_all_records()
        filtered = [r for r in records if str(r.get("user_id")) == user_id]
        filtered.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
        return filtered

    def delete_trade(self, trade_id: str, user_id: str) -> bool:
        records = self.sheet.get_all_records()
        row_idx = None
        for idx, r in enumerate(records):
            if str(r.get("trade_id")) == trade_id and str(r.get("user_id")) == user_id:
                row_idx = idx + 2
                break
        if row_idx is None:
            return False
        self.sheet.delete_rows(row_idx)
        return True

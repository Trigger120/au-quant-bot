import sqlite3
import uuid
from datetime import datetime
from typing import Dict, List, Optional
from db.base import AbstractDataStore

class SQLiteDataStore(AbstractDataStore):
    """
    SQLite engine for local storage. Suitable for local testing and lightweight setups.
    Includes auto-migration of columns for session, timeframe, and confirmations.
    Also handles user authentication records and filters all trades by user_id.
    """
    def __init__(self, db_path: str):
        self.db_path = db_path

    def connect(self) -> None:
        """Create table if it does not exist and perform migrations."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Create users table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id TEXT PRIMARY KEY,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """)
        
        # Create table with new fields
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS trades (
                trade_id TEXT PRIMARY KEY,
                user_id TEXT,
                timestamp TEXT NOT NULL,
                pair TEXT NOT NULL,
                direction TEXT NOT NULL,
                entry_price REAL NOT NULL,
                sl REAL NOT NULL,
                tp REAL NOT NULL,
                exit_price REAL,
                status TEXT DEFAULT 'OPEN',
                technique TEXT,
                failure_cause TEXT,
                pnl_r REAL DEFAULT 0.0,
                session TEXT,
                timeframe TEXT,
                confirmations TEXT,
                pips_gained REAL,
                is_risk_free INTEGER DEFAULT 0
            )
        """)
        
        # Auto-migration of existing databases
        cursor.execute("PRAGMA table_info(trades)")
        columns = [row[1] for row in cursor.fetchall()]
        
        if "user_id" not in columns:
            cursor.execute("ALTER TABLE trades ADD COLUMN user_id TEXT")
        if "session" not in columns:
            cursor.execute("ALTER TABLE trades ADD COLUMN session TEXT")
        if "timeframe" not in columns:
            cursor.execute("ALTER TABLE trades ADD COLUMN timeframe TEXT")
        if "confirmations" not in columns:
            cursor.execute("ALTER TABLE trades ADD COLUMN confirmations TEXT")
        if "pips_gained" not in columns:
            cursor.execute("ALTER TABLE trades ADD COLUMN pips_gained REAL")
        if "is_risk_free" not in columns:
            cursor.execute("ALTER TABLE trades ADD COLUMN is_risk_free INTEGER DEFAULT 0")
            
        conn.commit()
        conn.close()

    def create_user(self, email: str, password_hash: str) -> Optional[Dict]:
        user_id = str(uuid.uuid4())[:8]
        created_at = datetime.utcnow().isoformat()
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        try:
            # Check if this is the first user
            cursor.execute("SELECT COUNT(*) FROM users")
            count = cursor.fetchone()[0]

            cursor.execute(
                "INSERT INTO users (user_id, email, password_hash, created_at) VALUES (?, ?, ?, ?)",
                (user_id, email.lower(), password_hash, created_at)
            )

            # If first user, migrate trades
            if count == 0:
                cursor.execute("UPDATE trades SET user_id = ? WHERE user_id = 'default' OR user_id IS NULL", (user_id,))

            conn.commit()
            return {"user_id": user_id, "email": email.lower(), "created_at": created_at}
        except sqlite3.IntegrityError:
            return None
        finally:
            conn.close()

    def get_user_by_email(self, email: str) -> Optional[Dict]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE email = ?", (email.lower(),))
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None

    def get_first_user(self) -> Optional[Dict]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users LIMIT 1")
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None

    def add_trade(self, trade_data: Dict, user_id: str) -> str:
        trade_id = trade_data.get("trade_id") or str(uuid.uuid4())[:8]
        timestamp = trade_data.get("timestamp") or datetime.utcnow().isoformat()
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        exit_price = trade_data.get("exit_price")
        status = trade_data.get("status") or "OPEN"
        technique = trade_data.get("technique")
        failure_cause = trade_data.get("failure_cause")
        
        session_val = trade_data.get("session")
        timeframe_val = trade_data.get("timeframe")
        confirmations_val = trade_data.get("confirmations")
        pips_gained = trade_data.get("pips_gained")
        
        is_risk_free = trade_data.get("is_risk_free", 0)
        if isinstance(is_risk_free, bool):
            is_risk_free = 1 if is_risk_free else 0
        
        pnl_r = 0.0
        if status in ["WON", "LOST"] and exit_price is not None:
            trade_temp = {
                "direction": trade_data.get("direction"),
                "entry_price": trade_data.get("entry_price"),
                "sl": trade_data.get("sl"),
                "exit_price": exit_price
            }
            pnl_r = self.calculate_r_multiple(trade_temp)

        cursor.execute("""
            INSERT OR REPLACE INTO trades (
                trade_id, user_id, timestamp, pair, direction, entry_price, sl, tp, 
                exit_price, status, technique, failure_cause, pnl_r,
                session, timeframe, confirmations, pips_gained, is_risk_free
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            trade_id, user_id, timestamp, trade_data["pair"].upper(), trade_data["direction"].upper(),
            float(trade_data["entry_price"]), float(trade_data["sl"]), float(trade_data["tp"]),
            float(exit_price) if exit_price is not None else None,
            status.upper(), technique, failure_cause, pnl_r,
            session_val, timeframe_val, confirmations_val,
            float(pips_gained) if pips_gained is not None else None,
            is_risk_free
        ))
        
        conn.commit()
        conn.close()
        return trade_id

    def update_trade(self, trade_id: str, user_id: str, update_data: Dict) -> bool:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM trades WHERE trade_id = ? AND user_id = ?", (trade_id, user_id))
        row = cursor.fetchone()
        if not row:
            conn.close()
            return False
            
        trade = dict(row)
        
        # Update columns dynamically
        for k, v in update_data.items():
            if k in ["pair", "direction", "entry_price", "sl", "tp", "exit_price",
                     "status", "technique", "failure_cause", "session", "timeframe",
                     "confirmations", "pips_gained", "is_risk_free"]:
                if k in ["direction", "status", "pair"] and isinstance(v, str):
                    v = v.upper()
                if k == "is_risk_free":
                    if isinstance(v, bool):
                        v = 1 if v else 0
                    elif v is not None:
                        v = int(v)
                trade[k] = v
        
        # Recalculate pnl_r if closed
        if trade.get("status") in ["WON", "LOST"] and trade.get("exit_price") is not None:
            trade_temp = {
                "direction": trade.get("direction"),
                "entry_price": trade.get("entry_price"),
                "sl": trade.get("sl"),
                "exit_price": trade.get("exit_price")
            }
            trade["pnl_r"] = self.calculate_r_multiple(trade_temp)
        else:
            trade["pnl_r"] = 0.0

        # Construct dynamic SQL update
        fields_to_update = [
            "pair", "direction", "entry_price", "sl", "tp", "exit_price",
            "status", "technique", "failure_cause", "pnl_r", "session",
            "timeframe", "confirmations", "pips_gained", "is_risk_free"
        ]
        
        set_clauses = []
        values = []
        for field in fields_to_update:
            set_clauses.append(f"{field} = ?")
            values.append(trade.get(field))
            
        values.append(trade_id)
        values.append(user_id)
        
        sql = f"UPDATE trades SET {', '.join(set_clauses)} WHERE trade_id = ? AND user_id = ?"
        cursor.execute(sql, tuple(values))
        
        conn.commit()
        conn.close()
        return True

    def get_closed_trades(self, user_id: str, limit: Optional[int] = None) -> List[Dict]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        query = "SELECT * FROM trades WHERE user_id = ? AND status IN ('WON', 'LOST') ORDER BY timestamp DESC"
        if limit:
            query += f" LIMIT {limit}"
            
        cursor.execute(query, (user_id,))
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]

    def get_all_trades(self, user_id: str) -> List[Dict]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM trades WHERE user_id = ? ORDER BY timestamp DESC", (user_id,))
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]

    def delete_trade(self, trade_id: str, user_id: str) -> bool:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM trades WHERE trade_id = ? AND user_id = ?", (trade_id, user_id))
        conn.commit()
        deleted = cursor.rowcount > 0
        conn.close()
        return deleted

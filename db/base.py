from abc import ABC, abstractmethod
from typing import Dict, List, Optional
from datetime import datetime

class AbstractDataStore(ABC):
    """
    Abstract Base Class for Trading Journal Database Storage Engines.
    Provides standard interface for logging, updating, and retrieving trades.
    """
    
    @abstractmethod
    def connect(self) -> None:
        """Establish database connection and initialize tables/sheets."""
        pass

    @abstractmethod
    def add_trade(self, trade_data: Dict) -> str:
        """
        Log a new trade to the database.
        Returns the generated or passed trade_id.
        """
        pass

    @abstractmethod
    def update_trade(self, trade_id: str, update_data: Dict) -> bool:
        """
        Update an existing trade (e.g. close trade, exit price, status, failure cause).
        Returns True if successful, False otherwise.
        """
        pass

    @abstractmethod
    def get_closed_trades(self, limit: Optional[int] = None) -> List[Dict]:
        """
        Retrieve list of closed trades for statistical analysis.
        """
        pass

    @abstractmethod
    def get_all_trades(self) -> List[Dict]:
        """
        Retrieve all trades in the database.
        """
        pass

    @abstractmethod
    def delete_trade(self, trade_id: str) -> bool:
        """
        Delete a trade by trade_id.
        Returns True if successful.
        """
        pass

    @staticmethod
    def calculate_r_multiple(trade: Dict) -> float:
        """
        Helper method to calculate the R-multiple (Risk-to-Reward multiple achieved).
        R = (Exit - Entry) / (Entry - SL) for BUY
        R = (Entry - Exit) / (SL - Entry) for SELL
        """
        entry = float(trade.get("entry_price") or 0)
        sl = float(trade.get("sl") or 0)
        exit_p = float(trade.get("exit_price") or 0)
        direction = str(trade.get("direction") or "").upper()

        if not entry or not sl or not exit_p or not direction:
            return 0.0

        if direction == "BUY":
            risk = entry - sl
            if risk <= 0:
                return 0.0  # Invalid SL setup
            return (exit_p - entry) / risk
        elif direction == "SELL":
            risk = sl - entry
            if risk <= 0:
                return 0.0  # Invalid SL setup
            return (entry - exit_p) / risk
        
        return 0.0

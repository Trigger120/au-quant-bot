import unittest
from discord_bot import parse_discord_message

class TestDiscordParser(unittest.TestCase):
    def test_open_buy_signal(self):
        msg = (
            "🔔 NEW SIGNAL: BUY GOLD @ 2325.50\n"
            "SL: 2320.00\n"
            "TP: 2345.00\n"
            "Technique: FVG\n"
            "Session: London\n"
            "Timeframe: 15m\n"
            "Confirmations: CHoCH, MSS, Sweep"
        )
        res = parse_discord_message(msg)
        self.assertIsNotNone(res)
        self.assertEqual(res["type"], "OPEN")
        self.assertEqual(res["direction"], "BUY")
        self.assertEqual(res["entry_price"], 2325.50)
        self.assertEqual(res["sl"], 2320.00)
        self.assertEqual(res["tp"], 2345.00)
        self.assertEqual(res["technique"], "FVG")
        self.assertEqual(res["session"], "London")
        self.assertEqual(res["timeframe"], "15m")
        self.assertEqual(res["confirmations"], "CHoCH, MSS, Sweep")

    def test_open_sell_signal(self):
        msg = "XAUUSD SELL at 2340.5 SL: 2345 TP: 2325 setup: Order Block tf: 5m"
        res = parse_discord_message(msg)
        self.assertIsNotNone(res)
        self.assertEqual(res["type"], "OPEN")
        self.assertEqual(res["direction"], "SELL")
        self.assertEqual(res["entry_price"], 2340.5)
        self.assertEqual(res["sl"], 2345.0)
        self.assertEqual(res["tp"], 2325.0)
        self.assertEqual(res["technique"], "Order Block")
        self.assertEqual(res["timeframe"], "5m")

    def test_be_signal(self):
        msg = "GOLD set to BE now"
        res = parse_discord_message(msg)
        self.assertIsNotNone(res)
        self.assertEqual(res["type"], "BE")

    def test_partials_signal(self):
        msg = "XAUUSD Partials taken +30 pips"
        res = parse_discord_message(msg)
        self.assertIsNotNone(res)
        self.assertEqual(res["type"], "PARTIAL")
        self.assertEqual(res["pips_gained"], 30.0)

    def test_close_signal_with_r(self):
        msg = "GOLD Closed at 2350.50 (+100 pips, +3R)"
        res = parse_discord_message(msg)
        self.assertIsNotNone(res)
        self.assertEqual(res["type"], "CLOSE")
        self.assertEqual(res["exit_price"], 2350.50)
        self.assertEqual(res["pips_gained"], 100.0)
        self.assertEqual(res["r_multiple"], 3.0)

    def test_close_signal_full_book(self):
        msg = "Full book GOLD exit at 2315.0 (+80 pips)"
        res = parse_discord_message(msg)
        self.assertIsNotNone(res)
        self.assertEqual(res["type"], "CLOSE")
        self.assertEqual(res["exit_price"], 2315.0)
        self.assertEqual(res["pips_gained"], 80.0)

    def test_non_signal_ignored(self):
        msg = "Hello team, tomorrow we will have high volatility due to FOMC"
        res = parse_discord_message(msg)
        self.assertIsNone(res)

if __name__ == "__main__":
    unittest.main()

import discord
import re
import logging
import sys
import ssl
import aiohttp
from datetime import datetime
from typing import Optional, Dict
from config import settings
from db import get_db

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("AuQuantDiscordBot")

# Parser logic
def parse_discord_message(content: str) -> Optional[Dict]:
    content_upper = content.upper()
    
    # Pre-check: only process if it relates to GOLD or XAUUSD
    if "GOLD" not in content_upper and "XAUUSD" not in content_upper:
        return None
        
    # Helper to find float numbers
    def find_float_after_keywords(text: str, keywords: list) -> Optional[float]:
        for kw in keywords:
            # Matches kw followed by optional colon/spaces/at and then a float (including decimals)
            pattern = r'\b' + re.escape(kw) + r'\b\s*[:@\s]*\s*(\d+(?:\.\d+)?)'
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return float(match.group(1))
        return None

    # Helper to extract value for key (string value)
    def find_string_after_keywords(text: str, keywords: list) -> Optional[str]:
        all_kws = ["sl", "tp", "setup", "tf", "timeframe", "session", "sess", "conf", "confirmations", "tech", "technique"]
        lookahead_kws = [k for k in all_kws if k not in [kw.lower() for kw in keywords]]
        lookahead_part = r'(?=\s*(?:' + '|'.join(lookahead_kws) + r')\b|$)'
        
        for kw in keywords:
            pattern = r'\b' + re.escape(kw) + r'\b\s*[:\s]+\s*(.*?)' + lookahead_part
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        return None

    # 1. Close Signal
    if any(k in content_upper for k in ["CLOSE", "CLOSED", "FULL BOOK", "FULLBOOK", "EXIT"]):
        exit_price = find_float_after_keywords(content, ["at", "@", "price", "exit", "close", "closed", "book"])
        # If exit_price is not found, search for any 4-digit float (GOLD prices are typically 4 digits like 2320.50)
        if exit_price is None:
            floats = re.findall(r'\b\d{4}(?:\.\d+)?\b', content)
            if floats:
                exit_price = float(floats[0])

        pips = find_float_after_keywords(content, ["pips", "pip"])
        if pips is None:
            pip_match = re.search(r'([+-]?\d+(?:\.\d+)?)\s*pips?', content, re.IGNORECASE)
            if pip_match:
                pips = float(pip_match.group(1))

        r_multiple = find_float_after_keywords(content, ["r", "rr"])
        if r_multiple is None:
            r_match = re.search(r'([+-]?\d+(?:\.\d+)?)\s*R\b', content, re.IGNORECASE)
            if r_match:
                r_multiple = float(r_match.group(1))
                
        failure_cause = find_string_after_keywords(content, ["cause", "failure", "why", "reason"])

        return {
            "type": "CLOSE",
            "exit_price": exit_price,
            "pips_gained": pips,
            "r_multiple": r_multiple,
            "failure_cause": failure_cause,
            "raw": content
        }

    # 2. Partials Signal
    if "PARTIAL" in content_upper or "PARTIALS" in content_upper:
        pips = find_float_after_keywords(content, ["pips", "pip"])
        if pips is None:
            pip_match = re.search(r'([+-]?\d+(?:\.\d+)?)\s*pips?', content, re.IGNORECASE)
            if pip_match:
                pips = float(pip_match.group(1))
                
        return {
            "type": "PARTIAL",
            "pips_gained": pips,
            "raw": content
        }

    # 3. Break Even / Risk Free Signal
    if any(k in content_upper for k in ["BE", "BREAK EVEN", "BREAK-EVEN", "RISK FREE", "RISK-FREE"]):
        return {
            "type": "BE",
            "raw": content
        }

    # 4. Open Signal
    if "BUY" in content_upper or "SELL" in content_upper:
        direction = "BUY" if "BUY" in content_upper else "SELL"
        entry_price = find_float_after_keywords(content, ["at", "@", "entry", "price", "buy", "sell"])
        if entry_price is None:
            floats = re.findall(r'\b\d{4}(?:\.\d+)?\b', content)
            if floats:
                entry_price = float(floats[0])
                
        sl = find_float_after_keywords(content, ["sl", "stop", "loss", "stoploss"])
        tp = find_float_after_keywords(content, ["tp", "take", "profit", "takeprofit"])
        
        technique = find_string_after_keywords(content, ["tech", "technique", "setup", "type"])
        session = find_string_after_keywords(content, ["session", "sess"])
        timeframe = find_string_after_keywords(content, ["tf", "timeframe", "chart"])
        confirmations = find_string_after_keywords(content, ["conf", "confirmations", "confirmation", "rules"])

        # Fallback search for timeframe
        if not timeframe:
            tf_match = re.search(r'\b(1m|3m|5m|15m|30m|1h|4h|d|daily)\b', content_upper)
            if tf_match:
                timeframe = tf_match.group(1)

        # Fallback search for session
        if not session:
            sess_match = re.search(r'\b(london|ldn|new york|ny|asia|asian)\b', content_upper)
            if sess_match:
                session = sess_match.group(1).title()

        return {
            "type": "OPEN",
            "direction": direction,
            "entry_price": entry_price,
            "sl": sl,
            "tp": tp,
            "technique": technique,
            "session": session,
            "timeframe": timeframe,
            "confirmations": confirmations,
            "raw": content
        }

    return None

class AuQuantClient(discord.Client):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        try:
            self.db = get_db()
            logger.info("Successfully connected to the database backend.")
        except Exception as e:
            logger.error(f"Failed to connect to database: {e}")
            self.db = None

    async def login(self, token: str) -> None:
        # discord.py's HTTPClient.static_login() checks:
        #   if self.connector is MISSING: self.connector = aiohttp.TCPConnector(limit=0)
        # By setting http.connector BEFORE super().login() → static_login(), we ensure
        # the ClientSession is created with our SSL-bypassing connector.
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
        self.http.connector = aiohttp.TCPConnector(limit=0, ssl=ssl_context)
        logger.info("Injected SSL-bypass connector (for proxy/VPN environments)")
        await super().login(token)

    async def on_ready(self):
        logger.info(f"Logged in as {self.user.name} (ID: {self.user.id})")
        monitored = settings.MONITORED_CHANNELS
        if monitored:
            for ch_id, profile in monitored.items():
                logger.info(f"Monitoring channel {ch_id} -> {profile['label']} (risk: {profile['risk']}R)")
        else:
            logger.warning("No channels configured! Set DISCORD_APLUS_CHANNEL_ID / DISCORD_HALFRISK_CHANNEL_ID in .env")
        print(f"Au Quant Bot Discord Client is ONLINE. Running as {self.user.name}.")

    async def on_message(self, message):
        # Ignore messages from the bot itself
        if message.author.id == self.user.id:
            return
            
        # Only process messages from monitored channels
        monitored = settings.MONITORED_CHANNELS
        if monitored and message.channel.id not in monitored:
            return
        
        # Get risk profile for this channel
        channel_profile = monitored.get(message.channel.id, {"label": "Unknown", "risk": 1.0})

        # Parse message content
        signal = parse_discord_message(message.content)
        if not signal:
            return

        logger.info(f"Parsed signal of type {signal['type']} from channel {message.channel.id}")

        if not self.db:
            await message.channel.send("⚠️ **Au Quant Bot Error**: Database connection is not available.")
            return

        # Fetch active open trades to match
        all_trades = self.db.get_all_trades()
        open_trades = [t for t in all_trades if t.get("status") == "OPEN"]
        
        # Check if a specific trade_id is mentioned in the message text
        matched_trade = None
        for ot in open_trades:
            if ot["trade_id"].upper() in message.content.upper():
                matched_trade = ot
                break
                
        # If not explicitly mentioned, default to the latest open trade
        if not matched_trade and open_trades:
            matched_trade = open_trades[0]  # The list is sorted desc by timestamp, so 0 is latest

        # Process signal types
        if signal["type"] == "OPEN":
            if not signal["entry_price"] or not signal["sl"] or not signal["tp"]:
                await message.channel.send("⚠️ **Au Quant Bot Signal Warning**: Missing Entry, SL, or TP levels. Trade not logged.")
                return
                
            try:
                # Tag with risk category from channel profile
                risk_label = channel_profile["label"]
                risk_value = channel_profile["risk"]
                technique_tag = signal["technique"] or ""
                if technique_tag:
                    technique_tag = f"[{risk_label}] {technique_tag}"
                else:
                    technique_tag = f"[{risk_label}]"

                trade_id = self.db.add_trade({
                    "pair": "XAUUSD",
                    "direction": signal["direction"],
                    "entry_price": signal["entry_price"],
                    "sl": signal["sl"],
                    "tp": signal["tp"],
                    "technique": technique_tag,
                    "session": signal["session"],
                    "timeframe": signal["timeframe"],
                    "confirmations": signal["confirmations"],
                    "status": "OPEN",
                    "is_risk_free": 0
                })
                
                risk_emoji = "🟢" if risk_value >= 1.0 else "🟡"
                embed = discord.Embed(
                    title=f"{risk_emoji} XAUUSD Position Logged — {risk_label}",
                    description=f"Logged a new **{risk_label}** position ({risk_value}R risk) via Discord.",
                    color=discord.Color.blue() if risk_value >= 1.0 else discord.Color.gold()
                )
                embed.add_field(name="Trade ID", value=f"`{trade_id}`", inline=True)
                embed.add_field(name="Direction", value=signal["direction"], inline=True)
                embed.add_field(name="Risk", value=f"{risk_value}R", inline=True)
                embed.add_field(name="Entry Price", value=str(signal["entry_price"]), inline=True)
                embed.add_field(name="SL", value=str(signal["sl"]), inline=True)
                embed.add_field(name="TP", value=str(signal["tp"]), inline=True)
                embed.add_field(name="Session", value=signal["session"] or "N/A", inline=True)
                embed.add_field(name="Confirmations", value=signal["confirmations"] or "N/A", inline=False)
                embed.set_footer(text="Au Quant Bot")
                
                await message.reply(embed=embed)
            except Exception as e:
                logger.error(f"Error saving open trade: {e}")
                await message.reply(f"❌ **Error logging trade**: {e}")

        elif signal["type"] == "BE":
            if not matched_trade:
                await message.reply("⚠️ **Au Quant Bot**: No active open trade found to update to Break-Even.")
                return
                
            try:
                trade_id = matched_trade["trade_id"]
                # Update SL to entry price and set risk-free = 1
                self.db.update_trade(trade_id, {
                    "sl": matched_trade["entry_price"],
                    "is_risk_free": 1
                })
                
                embed = discord.Embed(
                    title="🛡️ Break-Even / Risk-Free Update",
                    description=f"Trade `{trade_id}` has been set to Break-Even (SL adjusted to entry: {matched_trade['entry_price']}).",
                    color=discord.Color.orange()
                )
                embed.set_footer(text="Au Quant Bot")
                await message.reply(embed=embed)
            except Exception as e:
                logger.error(f"Error setting BE: {e}")
                await message.reply(f"❌ **Error setting Break-Even**: {e}")

        elif signal["type"] == "PARTIAL":
            if not matched_trade:
                await message.reply("⚠️ **Au Quant Bot**: No active open trade found to log partial take profit.")
                return
                
            try:
                trade_id = matched_trade["trade_id"]
                current_pips = matched_trade.get("pips_gained") or 0.0
                gained_pips = signal["pips_gained"] or 0.0
                new_pips = current_pips + gained_pips
                
                self.db.update_trade(trade_id, {
                    "pips_gained": new_pips
                })
                
                embed = discord.Embed(
                    title="💰 Partial Take Profit Logged",
                    description=f"Added partial profit of **+{gained_pips} pips** to Trade `{trade_id}`.",
                    color=discord.Color.gold()
                )
                embed.add_field(name="Total Pips Gained", value=f"{new_pips} pips", inline=True)
                embed.set_footer(text="Au Quant Bot")
                await message.reply(embed=embed)
            except Exception as e:
                logger.error(f"Error setting partial: {e}")
                await message.reply(f"❌ **Error logging partial**: {e}")

        elif signal["type"] == "CLOSE":
            if not matched_trade:
                await message.reply("⚠️ **Au Quant Bot**: No active open trade found to close.")
                return
                
            try:
                trade_id = matched_trade["trade_id"]
                exit_price = signal["exit_price"]
                entry_price = float(matched_trade["entry_price"])
                direction = matched_trade["direction"]
                
                # If exit price not specified, default to Entry
                if exit_price is None:
                    exit_price = entry_price
                
                # Determine outcome status
                pips = signal["pips_gained"]
                if pips is not None:
                    status = "WON" if pips > 0 else "LOST"
                else:
                    if direction == "BUY":
                        status = "WON" if exit_price > entry_price else "LOST"
                    else:
                        status = "WON" if exit_price < entry_price else "LOST"
                
                # Determine pips if not specified
                if pips is None:
                    if direction == "BUY":
                        # Gold pips is usually (exit - entry) * 10
                        pips = (exit_price - entry_price) * 10.0
                    else:
                        pips = (entry_price - exit_price) * 10.0
                        
                update_data = {
                    "exit_price": exit_price,
                    "status": status,
                    "pips_gained": pips
                }
                if signal["failure_cause"]:
                    update_data["failure_cause"] = signal["failure_cause"]
                    
                self.db.update_trade(trade_id, update_data)
                
                # Fetch finalized trade to get calculated R-multiple
                finalized_trades = self.db.get_all_trades()
                finalized = next((t for t in finalized_trades if t["trade_id"] == trade_id), matched_trade)
                r_val = finalized.get("pnl_r", 0.0)
                
                color = discord.Color.green() if status == "WON" else discord.Color.red()
                embed = discord.Embed(
                    title=f"🏁 Position Closed: {status}",
                    description=f"Position `{trade_id}` has been finalized.",
                    color=color
                )
                embed.add_field(name="Entry Price", value=str(entry_price), inline=True)
                embed.add_field(name="Exit Price", value=str(exit_price), inline=True)
                embed.add_field(name="Pips Gained", value=f"{pips:+.1f} pips", inline=True)
                embed.add_field(name="PnL (R)", value=f"{r_val:+.2f}R", inline=True)
                if signal["failure_cause"]:
                    embed.add_field(name="Failure Cause", value=signal["failure_cause"], inline=False)
                embed.set_footer(text="Au Quant Bot")
                
                await message.reply(embed=embed)
            except Exception as e:
                logger.error(f"Error closing trade: {e}")
                await message.reply(f"❌ **Error closing trade**: {e}")

def main():
    if not settings.DISCORD_BOT_TOKEN:
        logger.error("DISCORD_BOT_TOKEN is not configured in settings/environment. Exiting.")
        sys.exit(1)
        
    intents = discord.Intents.default()
    intents.message_content = True  # Required to read channel messages
    
    client = AuQuantClient(intents=intents)
    logger.info("Starting Au Quant Discord Bot...")
    client.run(settings.DISCORD_BOT_TOKEN)

if __name__ == "__main__":
    main()


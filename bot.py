import logging
from typing import Optional
from fastapi import FastAPI, Header, HTTPException, Depends, status
from pydantic import BaseModel, Field
import requests
import os
import auth
from config import settings
from db import get_db

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("TradingWebhookBot")

app = FastAPI(
    title="Au Quant SaaS API Server",
    description="FastAPI Service with JWT Auth and Multi-User data isolation.",
    version="3.0.0"
)

# Enable CORS for frontend dashboard access
from fastapi.middleware.cors import CORSMiddleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize database
try:
    db = get_db()
    logger.info(f"Database backend '{settings.DATABASE_TYPE}' initialized successfully.")
except Exception as e:
    logger.error(f"Failed to initialize database backend: {e}")

# ----------------- Security Dependencies -----------------
def verify_api_key(x_api_key: Optional[str] = Header(None, alias="X-API-KEY")):
    """
    Dependency to verify the incoming webhook requests.
    Expects X-API-KEY header to match the configured API_KEY environment variable.
    """
    if settings.API_KEY and x_api_key != settings.API_KEY:
        logger.warning("Unauthorized API access attempt detected.")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API Key (X-API-KEY header)"
        )
    return x_api_key

def get_current_user(email: str = Depends(auth.get_current_user_email)) -> dict:
    """
    Dependency to authenticate and retrieve the currently logged in user.
    """
    user = db.get_user_by_email(email)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user

# ----------------- Discord Helper -----------------
def send_discord_alert(title: str, description: str, color: int = 3066993, fields: list = None):
    """
    Utility to dispatch beautiful rich embeds to the configured Discord Webhook URL.
    """
    if not settings.DISCORD_WEBHOOK_URL:
        return
        
    embed = {
        "title": title,
        "description": description,
        "color": color,
        "timestamp": None
    }
    
    if fields:
        embed["fields"] = fields
        
    payload = {
        "embeds": [embed]
    }
    
    try:
        response = requests.post(settings.DISCORD_WEBHOOK_URL, json=payload, timeout=5)
        if response.status_code not in [200, 204]:
            logger.error(f"Discord API returned error code {response.status_code}: {response.text}")
    except Exception as e:
        logger.error(f"Failed to send Discord webhook: {e}")

# ----------------- Request Schemas -----------------
class UserRegisterRequest(BaseModel):
    email: str = Field(..., description="Unique email address")
    password: str = Field(..., description="Plaintext password")

class LoginRequest(BaseModel):
    email: str = Field(..., description="Email address")
    password: str = Field(..., description="Plaintext password")

class TradeOpenRequest(BaseModel):
    pair: str = Field("XAUUSD", description="Asset pair (defaults to XAUUSD / GOLD)")
    direction: str = Field(..., description="BUY or SELL")
    entry_price: float = Field(..., gt=0, description="Entry execution level")
    sl: float = Field(..., gt=0, description="Stop Loss level")
    tp: float = Field(..., gt=0, description="Take Profit level")
    technique: Optional[str] = Field(None, description="Setup style (e.g. FVG, Order Block)")
    session: Optional[str] = Field(None, description="Execution Session (e.g. London, New York, Asia)")
    timeframe: Optional[str] = Field(None, description="Execution Timeframe (e.g. 15M->1M)")
    confirmations: Optional[str] = Field(None, description="Execution Confirmations (comma-separated, e.g. MSS, CHoCH, Sweep)")
    trade_id: Optional[str] = Field(None, description="Optional unique identifier")
    pips_gained: Optional[float] = Field(None, description="Pips gained")
    is_risk_free: Optional[int] = Field(0, description="1 if break-even/risk-free, 0 otherwise")
    user_id: Optional[str] = Field(None, description="Optional target user ID (for M2M integrations)")
    user_email: Optional[str] = Field(None, description="Optional target user email (for M2M integrations)")

class TradeCloseRequest(BaseModel):
    trade_id: str = Field(..., description="Unique trade ID to close")
    exit_price: float = Field(..., gt=0, description="Actual exit level")
    status: str = Field(..., description="Outcome of trade: WON or LOST")
    failure_cause: Optional[str] = Field(None, description="Reason for failure if lost")
    session: Optional[str] = Field(None, description="Optionally update/correct the Session")
    timeframe: Optional[str] = Field(None, description="Optionally update/correct the Timeframe")
    confirmations: Optional[str] = Field(None, description="Optionally update/correct the Confirmations")
    pips_gained: Optional[float] = Field(None, description="Pips gained at exit/partial")
    is_risk_free: Optional[int] = Field(None, description="Risk free status")
    user_id: Optional[str] = Field(None, description="Optional target user ID (for M2M integrations)")
    user_email: Optional[str] = Field(None, description="Optional target user email (for M2M integrations)")

class TradeLogRequest(BaseModel):
    pair: str = Field("XAUUSD", description="Asset pair")
    direction: str = Field(..., description="BUY or SELL")
    entry_price: float = Field(..., gt=0, description="Entry level")
    sl: float = Field(..., gt=0, description="Stop Loss")
    tp: float = Field(..., gt=0, description="Take Profit")
    exit_price: float = Field(..., gt=0, description="Exit level")
    status: str = Field(..., description="WON or LOST")
    technique: Optional[str] = Field(None, description="Setup style")
    session: Optional[str] = Field(None, description="Execution Session")
    timeframe: Optional[str] = Field(None, description="Execution Timeframe")
    confirmations: Optional[str] = Field(None, description="Confirmations")
    failure_cause: Optional[str] = Field(None, description="Reason for loss if applicable")
    trade_id: Optional[str] = Field(None, description="Optional ID")
    pips_gained: Optional[float] = Field(None, description="Pips gained")
    is_risk_free: Optional[int] = Field(0, description="1 if risk-free, 0 otherwise")
    user_id: Optional[str] = Field(None, description="Optional target user ID")
    user_email: Optional[str] = Field(None, description="Optional target user email")

class TradeUpdateRequest(BaseModel):
    pair: Optional[str] = None
    direction: Optional[str] = None
    entry_price: Optional[float] = None
    sl: Optional[float] = None
    tp: Optional[float] = None
    exit_price: Optional[float] = None
    status: Optional[str] = None
    technique: Optional[str] = None
    session: Optional[str] = None
    timeframe: Optional[str] = None
    confirmations: Optional[str] = None
    failure_cause: Optional[str] = None
    pips_gained: Optional[float] = None
    is_risk_free: Optional[int] = None

# Helper to resolve target user ID for webhook endpoints
def resolve_webhook_user(u_id: Optional[str], u_email: Optional[str]) -> str:
    if u_id:
        return u_id
    if u_email:
        user = db.get_user_by_email(u_email)
        if user:
            return user["user_id"]
    
    # Fallback: get the first user in the database
    first = db.get_first_user()
    if first:
        return first["user_id"]
        
    return "default"

# ----------------- Authentication Endpoints -----------------

@app.post("/register", response_model=dict)
def register_user(req: UserRegisterRequest):
    """Register a new student account."""
    existing = db.get_user_by_email(req.email)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="An account with this email address is already registered."
        )
    
    # Check if first user to handle migrations
    first_user = db.get_first_user()
    is_first = (first_user is None)
    
    pwd_hash = auth.get_password_hash(req.password)
    user = db.create_user(req.email, pwd_hash)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Registration failed. Please try again."
        )
        
    return {
        "status": "success",
        "message": "User registered successfully.",
        "user": {
            "user_id": user["user_id"],
            "email": user["email"],
            "created_at": user["created_at"]
        }
    }

@app.post("/login", response_model=dict)
def login_user(req: LoginRequest):
    """Authenticate a student and return a JWT access token."""
    user = db.get_user_by_email(req.email)
    if not user or not auth.verify_password(req.password, user["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Incorrect email or password."
        )
        
    access_token = auth.create_access_token(data={"sub": user["email"]})
    return {
        "access_token": access_token, 
        "token_type": "bearer",
        "email": user["email"],
        "user_id": user["user_id"]
    }

# ----------------- Core Endpoints -----------------

@app.get("/")
def read_root():
    return {
        "status": "online",
        "system": "Au Quant SaaS Trading Journal API",
        "database_backend": settings.DATABASE_TYPE
    }

@app.post("/trades/open", response_model=dict, dependencies=[Depends(verify_api_key)])
def open_trade(req: TradeOpenRequest):
    """
    Open a new active position and persist it to the journal (machine-to-machine webhook).
    """
    target_user_id = resolve_webhook_user(req.user_id, req.user_email)
    try:
        t_id = db.add_trade({
            "trade_id": req.trade_id,
            "pair": req.pair or "XAUUSD",
            "direction": req.direction,
            "entry_price": req.entry_price,
            "sl": req.sl,
            "tp": req.tp,
            "technique": req.technique,
            "session": req.session,
            "timeframe": req.timeframe,
            "confirmations": req.confirmations,
            "status": "OPEN",
            "pips_gained": req.pips_gained,
            "is_risk_free": req.is_risk_free or 0
        }, target_user_id)
        
        logger.info(f"Opened trade successfully for user {target_user_id}: ID={t_id}, Pair={req.pair}, Direction={req.direction}")
        
        # Dispatch to Discord
        fields = [
            {"name": "Trade ID", "value": f"`{t_id}`", "inline": True},
            {"name": "Pair", "value": (req.pair or "XAUUSD").upper(), "inline": True},
            {"name": "Direction", "value": req.direction.upper(), "inline": True},
            {"name": "Entry", "value": str(req.entry_price), "inline": True},
            {"name": "SL / TP", "value": f"SL: {req.sl}\nTP: {req.tp}", "inline": True},
            {"name": "Session", "value": req.session or "N/A", "inline": True},
            {"name": "Timeframe", "value": req.timeframe or "N/A", "inline": True},
            {"name": "Confirmations", "value": req.confirmations or "N/A", "inline": False}
        ]
        if req.is_risk_free:
            fields.append({"name": "Status", "value": "Risk Free / BE", "inline": True})
            
        send_discord_alert(
            title="🔔 XAUUSD Position Opened",
            description=f"Logged a new active position for {req.pair.upper()}",
            color=3447003, # Blue
            fields=fields
        )
        
        return {"status": "success", "trade_id": t_id}
    except Exception as e:
        logger.error(f"Error opening trade: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/trades/close", response_model=dict, dependencies=[Depends(verify_api_key)])
def close_trade(req: TradeCloseRequest):
    """
    Close an open trade by updating its exit parameters, status, and failure cause (webhook).
    """
    target_user_id = resolve_webhook_user(req.user_id, req.user_email)
    try:
        update_data = {
            "exit_price": req.exit_price,
            "status": req.status,
            "failure_cause": req.failure_cause
        }
        if req.session:
            update_data["session"] = req.session
        if req.timeframe:
            update_data["timeframe"] = req.timeframe
        if req.confirmations:
            update_data["confirmations"] = req.confirmations
        if req.pips_gained is not None:
            update_data["pips_gained"] = req.pips_gained
        if req.is_risk_free is not None:
            update_data["is_risk_free"] = req.is_risk_free

        success = db.update_trade(req.trade_id, target_user_id, update_data)
        
        if not success:
            raise HTTPException(status_code=404, detail=f"Trade with ID {req.trade_id} not found for user {target_user_id}")
            
        logger.info(f"Closed trade successfully for user {target_user_id}: ID={req.trade_id}, Status={req.status}, Exit={req.exit_price}")
        
        color = 3066993 if req.status.upper() == "WON" else 15158332
        fields = [
            {"name": "Trade ID", "value": f"`{req.trade_id}`", "inline": True},
            {"name": "Exit Price", "value": str(req.exit_price), "inline": True},
            {"name": "Status", "value": req.status.upper(), "inline": True}
        ]
        if req.pips_gained is not None:
            fields.append({"name": "Pips Gained", "value": str(req.pips_gained), "inline": True})
        if req.failure_cause:
            fields.append({"name": "Failure Cause", "value": req.failure_cause, "inline": False})
            
        send_discord_alert(
            title="🏁 XAUUSD Position Closed",
            description=f"Position `{req.trade_id}` has been finalized.",
            color=color,
            fields=fields
        )
        
        return {"status": "success", "trade_id": req.trade_id}
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Error closing trade: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/trades/log", response_model=dict, dependencies=[Depends(verify_api_key)])
def log_historical_trade(req: TradeLogRequest):
    """
    Directly archive a completed historical trade (webhook).
    """
    target_user_id = resolve_webhook_user(req.user_id, req.user_email)
    try:
        t_id = db.add_trade({
            "trade_id": req.trade_id,
            "pair": req.pair or "XAUUSD",
            "direction": req.direction,
            "entry_price": req.entry_price,
            "sl": req.sl,
            "tp": req.tp,
            "exit_price": req.exit_price,
            "status": req.status,
            "technique": req.technique,
            "session": req.session,
            "timeframe": req.timeframe,
            "confirmations": req.confirmations,
            "failure_cause": req.failure_cause,
            "pips_gained": req.pips_gained,
            "is_risk_free": req.is_risk_free or 0
        }, target_user_id)
        
        logger.info(f"Archived historical trade successfully for user {target_user_id}: ID={t_id}, Pair={req.pair}, Status={req.status}")
        
        color = 3066993 if req.status.upper() == "WON" else 15158332
        fields = [
            {"name": "Trade ID", "value": f"`{t_id}`", "inline": True},
            {"name": "Pair", "value": (req.pair or "XAUUSD").upper(), "inline": True},
            {"name": "Direction", "value": req.direction.upper(), "inline": True},
            {"name": "Entry", "value": str(req.entry_price), "inline": True},
            {"name": "Exit", "value": str(req.exit_price), "inline": True},
            {"name": "Status", "value": req.status.upper(), "inline": True},
            {"name": "Session", "value": req.session or "N/A", "inline": True},
            {"name": "Confirmations", "value": req.confirmations or "N/A", "inline": False}
        ]
        if req.pips_gained is not None:
            fields.append({"name": "Pips Gained", "value": str(req.pips_gained), "inline": True})
        if req.failure_cause:
            fields.append({"name": "Failure Cause", "value": req.failure_cause, "inline": False})
            
        send_discord_alert(
            title="💾 Historical Log Saved",
            description=f"Archived a completed trade directly for pair {req.pair.upper()}",
            color=color,
            fields=fields
        )
        
        return {"status": "success", "trade_id": t_id}
    except Exception as e:
        logger.error(f"Error archiving trade: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/trades/{trade_id}", response_model=dict)
def update_trade(trade_id: str, req: TradeUpdateRequest, user: dict = Depends(get_current_user)):
    """
    Manually update any trade parameter dynamically (user isolated).
    """
    try:
        # filter out None values so we only update specified fields
        update_data = {k: v for k, v in req.model_dump().items() if v is not None}
        
        success = db.update_trade(trade_id, user["user_id"], update_data)
        if not success:
            raise HTTPException(status_code=404, detail=f"Trade with ID {trade_id} not found")
            
        logger.info(f"Updated trade successfully for user {user['user_id']}: ID={trade_id}, data={update_data}")
        
        # Dispatch update notifications to Discord
        fields = [{"name": "Trade ID", "value": f"`{trade_id}`", "inline": True}]
        for k, v in update_data.items():
            fields.append({"name": k, "value": str(v), "inline": True})
            
        send_discord_alert(
            title="✏️ Trade Log Manually Updated",
            description=f"Trade `{trade_id}` has been modified.",
            color=16753920, # Orange/Yellow
            fields=fields
        )
        
        return {"status": "success", "trade_id": trade_id}
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Error updating trade {trade_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/trades/{trade_id}", response_model=dict)
def delete_trade(trade_id: str, user: dict = Depends(get_current_user)):
    """Delete a trade from the database (user isolated)."""
    try:
        success = db.delete_trade(trade_id, user["user_id"])
        if not success:
            raise HTTPException(status_code=404, detail=f"Trade with ID {trade_id} not found")
        logger.info(f"Trade {trade_id} deleted successfully for user {user['user_id']}.")
        return {"status": "success", "message": f"Trade {trade_id} deleted."}
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Error deleting trade {trade_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/trades")
def get_trades(user: dict = Depends(get_current_user)):
    """
    Get all trades from the database for the authenticated user.
    """
    try:
        trades = db.get_all_trades(user["user_id"])
        return {"status": "success", "trades": trades}
    except Exception as e:
        logger.error(f"Error fetching trades: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/analysis")
def get_analysis(user: dict = Depends(get_current_user)):
    """
    Perform on-the-fly pandas analysis and return JSON summary with Sessions and Confirmations (user isolated).
    """
    try:
        import pandas as pd
        trades = db.get_closed_trades(user["user_id"])
        if not trades:
            return {
                "status": "success",
                "summary": {
                    "total_trades": 0,
                    "win_rate": 0.0,
                    "profit_factor": 1.0,
                    "net_r": 0.0,
                    "avg_win": 0.0,
                    "avg_loss": 0.0
                },
                "techniques": [],
                "failure_causes": [],
                "sessions": [],
                "confirmations": []
            }
            
        df = pd.DataFrame(trades)
        df['pnl_r'] = df['pnl_r'].astype(float)
        
        total_trades = len(df)
        won_trades = df[df['status'] == 'WON']
        lost_trades = df[df['status'] == 'LOST']
        
        win_rate = (len(won_trades) / total_trades) * 100
        
        total_profit = won_trades['pnl_r'].sum()
        total_loss = abs(lost_trades['pnl_r'].sum())
        profit_factor = total_profit / total_loss if total_loss > 0 else total_profit
        net_r = df['pnl_r'].sum()
        
        # 1. Performance by Technique
        techniques_list = []
        if 'technique' in df.columns:
            tech_groups = df.groupby('technique')
            for name, group in tech_groups:
                if pd.isna(name) or not name:
                    continue
                t_total = len(group)
                t_won = group[group['status'] == 'WON']
                t_lost = group[group['status'] == 'LOST']
                t_win_rate = (len(t_won) / t_total) * 100
                t_net_r = group['pnl_r'].sum()
                t_prof = t_won['pnl_r'].sum()
                t_los = abs(t_lost['pnl_r'].sum())
                t_pf = t_prof / t_los if t_los > 0 else t_prof
                
                techniques_list.append({
                    "name": name,
                    "count": t_total,
                    "win_rate": round(t_win_rate, 2),
                    "net_r": round(t_net_r, 2),
                    "profit_factor": round(t_pf, 2)
                })
                
        # 2. Performance by Session
        sessions_list = []
        if 'session' in df.columns:
            session_groups = df.groupby('session')
            for name, group in session_groups:
                if pd.isna(name) or not name:
                    continue
                s_total = len(group)
                s_won = group[group['status'] == 'WON']
                s_lost = group[group['status'] == 'LOST']
                s_win_rate = (len(s_won) / s_total) * 100
                s_net_r = group['pnl_r'].sum()
                s_prof = s_won['pnl_r'].sum()
                s_los = abs(s_lost['pnl_r'].sum())
                s_pf = s_prof / s_los if s_los > 0 else s_prof
                
                sessions_list.append({
                    "name": name,
                    "count": s_total,
                    "win_rate": round(s_win_rate, 2),
                    "net_r": round(s_net_r, 2),
                    "profit_factor": round(s_pf, 2)
                })
                
        # 3. Confirmation Frequency Analysis
        confirmations_list = []
        if 'confirmations' in df.columns:
            conf_counts = {}
            for _, r in df.iterrows():
                conf_str = r.get("confirmations")
                if pd.isna(conf_str) or not conf_str:
                    continue
                confs = [c.strip() for c in conf_str.split(",") if c.strip()]
                for c in confs:
                    if c not in conf_counts:
                        conf_counts[c] = {"total": 0, "won": 0, "lost": 0, "net_r": 0.0}
                    conf_counts[c]["total"] += 1
                    if r["status"] == "WON":
                        conf_counts[c]["won"] += 1
                    elif r["status"] == "LOST":
                        conf_counts[c]["lost"] += 1
                    conf_counts[c]["net_r"] += float(r["pnl_r"])
                    
            for name, stats in conf_counts.items():
                win_pct = (stats["won"] / stats["total"]) * 100 if stats["total"] > 0 else 0.0
                confirmations_list.append({
                    "name": name,
                    "count": stats["total"],
                    "win_rate": round(win_pct, 2),
                    "net_r": round(stats["net_r"], 2)
                })
            # Sort confirmations by frequency/count descending
            confirmations_list.sort(key=lambda x: x["count"], reverse=True)

        # 4. Failure cause analysis
        failures_list = []
        if 'failure_cause' in df.columns and len(lost_trades) > 0:
            cause_counts = lost_trades['failure_cause'].value_counts()
            for cause, count in cause_counts.items():
                if pd.isna(cause) or not cause:
                    continue
                pct = (count / len(lost_trades)) * 100
                failures_list.append({
                    "cause": cause,
                    "count": int(count),
                    "pct": round(pct, 2)
                })
                
        return {
            "status": "success",
            "summary": {
                "total_trades": total_trades,
                "win_rate": round(win_rate, 2),
                "profit_factor": round(profit_factor, 2),
                "net_r": round(net_r, 2),
                "avg_win": round(won_trades['pnl_r'].mean() if len(won_trades) > 0 else 0.0, 2),
                "avg_loss": round(lost_trades['pnl_r'].mean() if len(lost_trades) > 0 else 0.0, 2),
                "best_trade": round(df['pnl_r'].max(), 2),
                "worst_trade": round(df['pnl_r'].min(), 2)
            },
            "techniques": techniques_list,
            "sessions": sessions_list,
            "confirmations": confirmations_list,
            "failure_causes": failures_list
        }
    except Exception as e:
        logger.error(f"Error performing dynamic analysis: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/directive")
def get_directive(user: dict = Depends(get_current_user)):
    """
    Generate dynamic quantitative strategy autopsy directives for the user.
    """
    try:
        import pandas as pd
        from analyzer import run_autopsy
        
        trades = db.get_closed_trades(user["user_id"])
        if not trades or len(trades) < 3:
            return {
                "status": "success",
                "directive": "### Dynamic Strategy Directives\nNeed at least 3 closed trades to generate quantitative insights. Keep logging!"
            }
            
        df = pd.DataFrame(trades)
        report_md = run_autopsy(df)
        return {"status": "success", "directive": report_md}
    except Exception as e:
        logger.error(f"Error generating dynamic directive: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("bot:app", host=settings.HOST, port=settings.PORT, reload=True)

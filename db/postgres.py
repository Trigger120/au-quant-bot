import uuid
from datetime import datetime
from typing import Dict, List, Optional
from sqlalchemy import create_engine, Column, String, Float, Integer
from sqlalchemy.orm import declarative_base, sessionmaker
from db.base import AbstractDataStore

Base = declarative_base()

class User(Base):
    __tablename__ = 'users'
    
    user_id = Column(String, primary_key=True)
    email = Column(String, unique=True, nullable=False)
    password_hash = Column(String, nullable=False)
    created_at = Column(String, nullable=False)

class Trade(Base):
    __tablename__ = 'trades'
    
    trade_id = Column(String, primary_key=True)
    user_id = Column(String, nullable=True)
    timestamp = Column(String, nullable=False)
    pair = Column(String, nullable=False)
    direction = Column(String, nullable=False)
    entry_price = Column(Float, nullable=False)
    sl = Column(Float, nullable=False)
    tp = Column(Float, nullable=False)
    exit_price = Column(Float, nullable=True)
    status = Column(String, default='OPEN')
    technique = Column(String, nullable=True)
    failure_cause = Column(String, nullable=True)
    pnl_r = Column(Float, default=0.0)
    session = Column(String, nullable=True)
    timeframe = Column(String, nullable=True)
    confirmations = Column(String, nullable=True)
    pips_gained = Column(Float, nullable=True)
    is_risk_free = Column(Integer, default=0)

class PostgresDataStore(AbstractDataStore):
    """
    PostgreSQL storage engine using SQLAlchemy. Highly recommended for cloud-deployed systems.
    """
    def __init__(self, database_url: str):
        self.database_url = database_url
        self.engine = None
        self.Session = None

    def connect(self) -> None:
        self.engine = create_engine(self.database_url, pool_pre_ping=True)
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)

    def create_user(self, email: str, password_hash: str) -> Optional[Dict]:
        session = self.Session()
        user_id = str(uuid.uuid4())[:8]
        created_at = datetime.utcnow().isoformat()
        try:
            # Check if this is the first user
            count = session.query(User).count()
            
            exists = session.query(User).filter(User.email == email.lower()).first()
            if exists:
                return None
                
            user = User(user_id=user_id, email=email.lower(), password_hash=password_hash, created_at=created_at)
            session.add(user)
            
            if count == 0:
                # Migrate default/orphaned trades to the first registered user
                trades_to_migrate = session.query(Trade).filter(
                    (Trade.user_id == 'default') | (Trade.user_id == None)
                ).all()
                for t in trades_to_migrate:
                    t.user_id = user_id
                    
            session.commit()
            return {"user_id": user_id, "email": email.lower(), "created_at": created_at}
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()

    def get_user_by_email(self, email: str) -> Optional[Dict]:
        session = self.Session()
        try:
            user = session.query(User).filter(User.email == email.lower()).first()
            if not user:
                return None
            return {
                "user_id": user.user_id, 
                "email": user.email, 
                "password_hash": user.password_hash, 
                "created_at": user.created_at
            }
        finally:
            session.close()

    def get_first_user(self) -> Optional[Dict]:
        session = self.Session()
        try:
            user = session.query(User).first()
            if not user:
                return None
            return {
                "user_id": user.user_id, 
                "email": user.email, 
                "password_hash": user.password_hash, 
                "created_at": user.created_at
            }
        finally:
            session.close()

    def add_trade(self, trade_data: Dict, user_id: str) -> str:
        session = self.Session()
        trade_id = trade_data.get("trade_id") or str(uuid.uuid4())[:8]
        timestamp = trade_data.get("timestamp") or datetime.utcnow().isoformat()
        
        exit_price = trade_data.get("exit_price")
        status = trade_data.get("status") or "OPEN"
        technique = trade_data.get("technique")
        failure_cause = trade_data.get("failure_cause")
        
        session_val = trade_data.get("session")
        timeframe_val = trade_data.get("timeframe")
        confirmations_val = trade_data.get("confirmations")
        pips_gained_val = trade_data.get("pips_gained")
        
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

        try:
            trade = Trade(
                trade_id=trade_id,
                user_id=user_id,
                timestamp=timestamp,
                pair=trade_data["pair"].upper(),
                direction=trade_data["direction"].upper(),
                entry_price=float(trade_data["entry_price"]),
                sl=float(trade_data["sl"]),
                tp=float(trade_data["tp"]),
                exit_price=float(exit_price) if exit_price is not None else None,
                status=status.upper(),
                technique=technique,
                failure_cause=failure_cause,
                pnl_r=pnl_r,
                session=session_val,
                timeframe=timeframe_val,
                confirmations=confirmations_val,
                pips_gained=float(pips_gained_val) if pips_gained_val is not None else None,
                is_risk_free=is_risk_free_val
            )
            session.merge(trade)  # Acts as insert or update if primary key exists
            session.commit()
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()
            
        return trade_id

    def update_trade(self, trade_id: str, user_id: str, update_data: Dict) -> bool:
        session = self.Session()
        try:
            trade = session.query(Trade).filter(Trade.trade_id == trade_id, Trade.user_id == user_id).first()
            if not trade:
                return False
            
            for k, v in update_data.items():
                if hasattr(trade, k):
                    if k in ["direction", "status", "pair"] and isinstance(v, str):
                        v = v.upper()
                    if k == "is_risk_free":
                        if isinstance(v, bool):
                            v = 1 if v else 0
                        elif v is not None:
                            v = int(v)
                    elif k in ["entry_price", "sl", "tp", "exit_price", "pips_gained"] and v is not None:
                        v = float(v)
                    setattr(trade, k, v)
            
            # Recalculate R-multiple
            if trade.status in ["WON", "LOST"] and trade.exit_price is not None:
                trade_temp = {
                    "direction": trade.direction,
                    "entry_price": trade.entry_price,
                    "sl": trade.sl,
                    "exit_price": trade.exit_price
                }
                trade.pnl_r = self.calculate_r_multiple(trade_temp)
            else:
                trade.pnl_r = 0.0
                
            session.commit()
            return True
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()

    def get_closed_trades(self, user_id: str, limit: Optional[int] = None) -> List[Dict]:
        session = self.Session()
        try:
            query = session.query(Trade).filter(Trade.user_id == user_id, Trade.status.in_(["WON", "LOST"])).order_by(Trade.timestamp.desc())
            if limit:
                query = query.limit(limit)
            trades = query.all()
            return [self._to_dict(t) for t in trades]
        finally:
            session.close()

    def get_all_trades(self, user_id: str) -> List[Dict]:
        session = self.Session()
        try:
            trades = session.query(Trade).filter(Trade.user_id == user_id).order_by(Trade.timestamp.desc()).all()
            return [self._to_dict(t) for t in trades]
        finally:
            session.close()

    def delete_trade(self, trade_id: str, user_id: str) -> bool:
        session = self.Session()
        try:
            trade = session.query(Trade).filter(Trade.trade_id == trade_id, Trade.user_id == user_id).first()
            if not trade:
                return False
            session.delete(trade)
            session.commit()
            return True
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()

    def _to_dict(self, trade: Trade) -> Dict:
        return {
            "trade_id": trade.trade_id,
            "user_id": trade.user_id,
            "timestamp": trade.timestamp,
            "pair": trade.pair,
            "direction": trade.direction,
            "entry_price": trade.entry_price,
            "sl": trade.sl,
            "tp": trade.tp,
            "exit_price": trade.exit_price,
            "status": trade.status,
            "technique": trade.technique,
            "failure_cause": trade.failure_cause,
            "pnl_r": trade.pnl_r,
            "session": trade.session,
            "timeframe": trade.timeframe,
            "confirmations": trade.confirmations,
            "pips_gained": trade.pips_gained,
            "is_risk_free": trade.is_risk_free
        }

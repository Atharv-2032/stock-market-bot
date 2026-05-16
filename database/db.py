from sqlalchemy import create_engine, Column, String, Float, Integer, DateTime, Text
from sqlalchemy.orm import declarative_base, sessionmaker
from datetime import datetime, timezone

Base = declarative_base()
engine = create_engine("sqlite:///stock_bot.db")
Session = sessionmaker(bind=engine)



class Trader(Base):
    __tablename__ = "traders"
    id = Column(String, primary_key=True)
    name = Column(String)
    source = Column(String)
    ticker = Column(String, nullable=True)
    sharpe = Column(Float, default=0.0)
    win_rate = Column(Float, default=0.0)
    roi = Column(Float, default=0.0)
    total_signals = Column(Integer, default=0)
    avg_return = Column(Float, default=0.0)
    last_updated = Column(DateTime, default=datetime.now)


class Signal(Base):
    __tablename__ = "signals"
    id = Column(Integer, primary_key=True, autoincrement=True)
    trader_id = Column(String)
    ticker = Column(String)
    signal_type = Column(String)
    direction = Column(String)
    size = Column(Float)
    price_at_signal = Column(Float)
    source = Column(String)
    raw_data = Column(Text)
    timestamp = Column(DateTime, default=datetime.now)
    processed = Column(Integer, default=0)


class Verdict(Base):
    __tablename__ = "verdicts"
    id = Column(Integer, primary_key=True, autoincrement=True)
    signal_id = Column(Integer)
    verdict = Column(String)
    staleness_score = Column(Float)
    conviction_score = Column(Float)
    signal_count = Column(Integer)
    safe_size = Column(Float)
    llm_score = Column(Float)
    llm_reasoning = Column(Text)
    timestamp = Column(DateTime, default=datetime.now)


class Trade(Base):
    __tablename__ = "trades"
    id = Column(Integer, primary_key=True, autoincrement=True)
    verdict_id = Column(Integer)
    ticker = Column(String)
    direction = Column(String)
    entry_price = Column(Float)
    size = Column(Float)
    stop_loss = Column(Float)
    take_profit = Column(Float)
    status = Column(String, default="open")
    exit_price = Column(Float, nullable=True)
    pnl = Column(Float, default=0.0)
    execution_mode = Column(String)
    timestamp = Column(DateTime, default=datetime.now)


class Position(Base):
    __tablename__ = "positions"
    id = Column(Integer, primary_key=True, autoincrement=True)
    ticker = Column(String)
    direction = Column(String)
    size = Column(Float)
    entry_price = Column(Float)
    current_price = Column(Float)
    stop_loss = Column(Float)
    take_profit = Column(Float)
    timestamp = Column(DateTime, default=datetime.now)

class CandidateTrader(Base):
    __tablename__ = "candidate_traders"
    id = Column(String, primary_key=True)
    name = Column(String)
    source = Column(String)
    ticker = Column(String, nullable=True)
    sharpe = Column(Float, default=0.0)
    win_rate = Column(Float, default=0.0)
    roi = Column(Float, default=0.0)
    total_signals = Column(Integer, default=0)
    avg_return = Column(Float, default=0.0)
    last_scored = Column(DateTime, nullable=True)
    last_seen = Column(DateTime, nullable=True)
    times_seen = Column(Integer, default=1)
    first_seen = Column(DateTime, default=datetime.now)
    status = Column(String, default="candidate")
    direction = Column(String, nullable=True)
    price_at_signal = Column(Float, nullable=True)
    historical_returns = Column(Text, nullable=True)

class WatchdogState(Base):
    
        __tablename__ = "watchdog_state"
        ticker = Column(String, primary_key=True)  # changed from trader_id
        last_checked = Column(DateTime, default=datetime.now)
        last_signal_time = Column(DateTime, nullable=True)

def init_db():
    Base.metadata.create_all(engine)


def get_session():
    return Session()
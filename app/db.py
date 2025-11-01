from sqlalchemy import create_engine, Column, Integer, String, DateTime, Text, func, Index, select
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.pool import NullPool
from datetime import datetime, timezone
import os
import argparse

Base = declarative_base()

# ---------- Models ----------
class Controller(Base):
    __tablename__ = 'controllers'
    id = Column(Integer, primary_key=True)
    name = Column(String(128), nullable=False)
    ip = Column(String(64), nullable=False, index=True)
    kind = Column(String(32), nullable=False)  # 'falcon' or 'fpp'
    notes = Column(Text)
    last_status = Column(String(16), default='unknown')  # online/offline/unknown
    last_rtt_ms = Column(Integer)
    last_checked = Column(DateTime(timezone=True))
    last_info_json = Column(Text)  # optional structured details (e.g., FPP now playing)

class Season(Base):
    __tablename__ = 'seasons'
    id = Column(Integer, primary_key=True)
    name = Column(String(128), unique=True, nullable=False)
    start_date = Column(DateTime(timezone=True), nullable=False)
    end_date = Column(DateTime(timezone=True), nullable=False)
    show_start = Column(String(5), default='17:00')  # HH:MM local
    show_end = Column(String(5), default='23:00')    # HH:MM local
    bucket_minutes = Column(Integer, default=1)

class AutoCount(Base):
    __tablename__ = 'auto_counts'
    id = Column(Integer, primary_key=True)
    timestamp = Column(DateTime(timezone=True), nullable=False, index=True)
    source = Column(String(64), nullable=False)          # 'opencv_tripline', 'baldrick', etc.
    camera_name = Column(String(128))                    # for vehicle counts
    count_type = Column(String(64), nullable=False)      # 'vehicle', 'device_seen'
    count_value = Column(Integer, nullable=False)
    season = Column(String(128))
    meta_json = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

Index('ix_auto_counts_ct_ts', AutoCount.count_type, AutoCount.timestamp)

class FPPStatus(Base):
    __tablename__ = 'fpp_status'
    id = Column(Integer, primary_key=True)
    timestamp = Column(DateTime(timezone=True), nullable=False, index=True)
    hostname = Column(String(128))
    version = Column(String(64))
    state = Column(String(64))
    playlist = Column(String(256))
    media = Column(String(256))
    raw_json = Column(Text)

class Alert(Base):
    __tablename__ = 'alerts'
    id = Column(Integer, primary_key=True)
    timestamp = Column(DateTime(timezone=True), nullable=False, index=True)
    severity = Column(String(16), default='warn')  # 'info','warn','error'
    message = Column(Text, nullable=False)
    active = Column(Integer, default=1)            # 1 active, 0 resolved

# ---------- Engine / Session ----------
# Default DB file: /home/itadmin/glowsync/data/tracker.db (no need to set anything)
DEFAULT_DB_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'data', 'tracker.db'))
DB_PATH = os.getenv('DB_PATH', DEFAULT_DB_PATH)

# Ensure the directory exists
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

# Use NullPool for SQLite on Pi (prevents QueuePool timeouts)
engine = create_engine(
    f"sqlite:///{DB_PATH}",
    poolclass=NullPool,
    connect_args={"check_same_thread": False, "timeout": 30},
    future=True,
    echo=False
)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False, future=True)

def get_session():
    return SessionLocal()

def init_db(path: str | None = None):
    """Create/upgrade tables. If path is provided, creates there; else uses DB_PATH."""
    target = path or DB_PATH
    os.makedirs(os.path.dirname(target), exist_ok=True)
    eng = create_engine(
        f"sqlite:///{target}",
        poolclass=NullPool,
        connect_args={"check_same_thread": False, "timeout": 30},
        future=True,
        echo=False
    )
    Base.metadata.create_all(eng)

# ---------- CLI ----------
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--init", action="store_true", help="Create DB tables")
    parser.add_argument("--path", default=DB_PATH, help="Optional custom DB path")
    args = parser.parse_args()
    if args.init:
        init_db(args.path)
        print(f"[db] Initialized at: {args.path}")

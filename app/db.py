from sqlalchemy import create_engine, Column, Integer, String, DateTime, Text, func, Index
from sqlalchemy.orm import declarative_base, sessionmaker
from datetime import datetime, timezone
import argparse, os

Base = declarative_base()

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

SessionLocal = None

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
    source = Column(String(64), nullable=False)
    camera_name = Column(String(128))
    count_type = Column(String(64), nullable=False)
    count_value = Column(Integer, nullable=False)
    season = Column(String(128))
    meta_json = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

Index('ix_auto_counts_ct_ts', AutoCount.count_type, AutoCount.timestamp)

def init_db(db_path: str):
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    eng = create_engine(f'sqlite:///{db_path}', echo=False, future=True)
    Base.metadata.create_all(eng)
    global SessionLocal
    SessionLocal = sessionmaker(bind=eng, expire_on_commit=False, future=True)
    return eng

def get_session():
    if SessionLocal is None:
        raise RuntimeError('DB not initialized. Call init_db(db_path) first.')
    return SessionLocal()

if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--init', action='store_true', help='Initialize database')
    ap.add_argument('--db', default=os.environ.get('DB_PATH','data/tracker.db'))
    args = ap.parse_args()
    if args.init:
        init_db(args.db)
        print('Initialized DB at', args.db)


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
    severity = Column(String(16), default='warn')
    message = Column(Text, nullable=False)
    active = Column(Integer, default=1)  # 1 active, 0 resolved

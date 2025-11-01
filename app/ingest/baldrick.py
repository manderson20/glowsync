import os, time
from datetime import datetime, timezone
from typing import Optional, Tuple

import httpx
from sqlalchemy import select, and_
from dotenv import load_dotenv
import pytz

from app.db import get_session, AutoCount, Season
from app.utils import floor_bucket

load_dotenv()
TZ_DEFAULT = os.getenv("TIMEZONE", "America/Chicago")
tz_local = pytz.timezone(TZ_DEFAULT)

def _parse_epoch_count_line(line: str) -> Optional[Tuple[datetime,int]]:
    parts = [p.strip() for p in line.split(",")]
    if len(parts) != 2:
        return None
    try:
        n = float(parts[0])  # epoch seconds (or ms)
        if n > 1e12: n /= 1000.0
        ts_utc = datetime.fromtimestamp(n, tz=timezone.utc)
        ts_local = ts_utc.astimezone(tz_local)    # store aligned to local buckets
        cnt = int(float(parts[1]))                # RAW instantaneous visitors
        return ts_local, cnt
    except Exception:
        return None

def fetch_csv_text(url: str, timeout_s: int = 15) -> str:
    with httpx.Client(timeout=timeout_s) as cli:
        r = cli.get(url)
        r.raise_for_status()
        return r.text

def run_once(url: str, verbose: bool=False) -> dict:
    text = fetch_csv_text(url)
    if verbose:
        print(f"[baldrick] fetched {len(text)} bytes")

    s = get_session()
    season = s.query(Season).order_by(Season.start_date.desc()).first()
    bucket = (season.bucket_minutes if season else 1) or 1
    season_name = season.name if season else None

    upserts = 0
    scanned = 0
    lines = [ln for ln in text.splitlines() if ln.strip()]

    for ln in lines:
        scanned += 1
        parsed = _parse_epoch_count_line(ln)
        if not parsed:
            continue
        ts_local, cnt = parsed

        # bucket based on LOCAL time, but store timestamp as UTC floor of that bucket
        bucket_ts = floor_bucket(ts_local.astimezone(timezone.utc), bucket)

        # Upsert per bucket
        existing = s.execute(
            select(AutoCount).where(
                and_(AutoCount.timestamp == bucket_ts,
                     AutoCount.count_type == 'device_seen',
                     AutoCount.source == 'baldrick')
            )
        ).scalar_one_or_none()

        if existing:
            existing.count_value = int(cnt)  # overwrite with the latest raw value
            s.add(existing)
        else:
            s.add(AutoCount(
                timestamp=bucket_ts,
                source='baldrick',
                count_type='device_seen',
                count_value=int(cnt),
                season=season_name,
            ))
        upserts += 1
        if upserts % 500 == 0:
            s.commit()

    s.commit()
    return {"scanned": scanned, "upserts": upserts}

if __name__ == "__main__":
    import argparse
    url = os.getenv("BALDRICK_CSV_URL", "").strip()
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default=url)
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()
    if not args.url:
        print("[baldrick] Set BALDRICK_CSV_URL in .env or pass --url")
        raise SystemExit(2)
    t0 = time.time()
    res = run_once(args.url, verbose=args.verbose)
    print(f"[baldrick] done → scanned={res['scanned']} upserts={res['upserts']}")

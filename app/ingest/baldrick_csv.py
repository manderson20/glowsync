import httpx, csv, io
from datetime import datetime, timezone
from app.db import get_session, AutoCount, Season
from app.config import load_config
from app.utils import floor_bucket, to_local, in_show_hours
from app.utils import floor_minute

def run(baldrick_csv_url: str):
    if not baldrick_csv_url:
        return {'skipped': 'no url configured'}
    r = httpx.get(baldrick_csv_url, timeout=30)
    r.raise_for_status()
    buf = io.StringIO(r.text)
    reader = csv.DictReader(buf)
    # Expect columns: timestamp/device_id/... (schema may vary)
    # We'll group by minute and count unique device_ids
    cfg = load_config()
    by_minute = {}
    tzname = cfg.get('timezone','America/Chicago')
    # Determine active season for now; if none, season stays None and we still log
    s = get_session()
    now_utc = datetime.now(timezone.utc)
    season = s.query(Season).filter(Season.start_date <= now_utc, Season.end_date > now_utc).first()
    bucket = season.bucket_minutes if season else 1
    show_start = season.show_start if season else '00:00'
    show_end = season.show_end if season else '23:59'
    for row in reader:
        # Heuristic: try common header names
        ts = row.get('timestamp') or row.get('time') or row.get('seen_at')
        if not ts:
            continue
        try:
            dt = datetime.fromisoformat(ts.replace('Z','+00:00'))
        except Exception:
            # Try epoch seconds
            try:
                dt = datetime.fromtimestamp(float(ts), tz=timezone.utc)
            except Exception:
                continue
        m = floor_bucket(dt, bucket)
        # apply show-hours filter based on local time
        local_dt = to_local(dt, tzname)
        if not in_show_hours(local_dt, show_start, show_end):
            continue
        dev = row.get('device_id') or row.get('mac') or row.get('addr') or 'unknown'
        by_minute.setdefault(m, set()).add(dev)
    s = get_session()
    total = 0
    for m, devices in by_minute.items():
        rec = AutoCount(timestamp=m, source='wifi_probe', camera_name=None,
                        count_type='device_seen', count_value=len(devices),
                        meta_json=None, season=season.name if season else None)
        s.add(rec); total += 1
    s.commit()
    return {'inserted_minutes': total}

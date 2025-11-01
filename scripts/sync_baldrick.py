#!/usr/bin/env python3
import os, io, csv, sqlite3, datetime as dt, pathlib, requests, sys

envp = pathlib.Path.home()/ "glowsync" / ".env"
url = os.getenv('BALDRICK_CSV_URL','').strip()
verify = True
if envp.exists():
    for line in envp.read_text().splitlines():
        if line.startswith('BALDRICK_CSV_URL='):
            url = line.split('=',1)[1].strip() or url
        if line.startswith('BALDRICK_VERIFY_SSL='):
            v = line.split('=',1)[1].strip().lower()
            verify = (v not in ('0','false','no'))

if not url:
    print("[baldrick] skipped: no url configured"); sys.exit(0)

db = pathlib.Path.home()/ "glowsync" / "data" / "tracker.db"
con = sqlite3.connect(db)
cur = con.cursor()

# ensure table exists (idempotent)
cur.executescript("""
CREATE TABLE IF NOT EXISTS AutoCount (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  count_type   TEXT NOT NULL,
  source       TEXT NOT NULL,
  timestamp    TEXT NOT NULL,
  count_value  INTEGER NOT NULL,
  camera_name  TEXT,
  season       TEXT
);
CREATE INDEX IF NOT EXISTS idx_autocount_ts ON AutoCount(timestamp);
CREATE INDEX IF NOT EXISTS idx_autocount_src ON AutoCount(source, count_type);
""")
con.commit()

r = requests.get(url, timeout=10, verify=verify)
r.raise_for_status()
rows = list(csv.reader(io.StringIO(r.text)))

def is_int(s):
    try: int(s); return True
    except: return False
start = 1 if rows and not (is_int(rows[0][0]) and is_int(rows[0][1])) else 0

cur.execute("SELECT timestamp FROM AutoCount WHERE source='baldrick' ORDER BY timestamp DESC LIMIT 1")
row = cur.fetchone(); last_iso = row[0] if row else None

inserted = 0
for rec in rows[start:]:
    if len(rec) < 2: continue
    try:
        epoch = int(rec[0].strip()); count = int(rec[1].strip())
    except: 
        continue
    ts_iso = dt.datetime.utcfromtimestamp(epoch).replace(tzinfo=dt.timezone.utc).isoformat()
    if last_iso and ts_iso <= last_iso:
        continue
    cur.execute("""INSERT INTO AutoCount(count_type, source, timestamp, count_value, camera_name, season)
                   VALUES(?,?,?,?,?,?)""",
                ('device_seen', 'baldrick', ts_iso, count, None, None))
    inserted += 1
con.commit(); con.close()
print(f"[baldrick] imported {inserted} new rows; latest={ts_iso if inserted else last_iso}")

# GlowSync (Raspberry Pi)

End-to-end Raspberry Pi app to track Christmas light show visitors by combining:
- **BaldrickSignal** CSV (device presence) ingest
- **UniFi Protect (G3 Bullet)** RTSP feed + OpenCV **virtual tripline** vehicle counting
- Unified storage in **SQLite**
- Simple **FastAPI** service with JSON endpoints and a tiny web dashboard
- **APScheduler** to run ingests on a schedule
- Optional: push daily aggregates to your Excel dashboard (copy/paste CSVs or extend here)

> No Docker required. Pure Python + systemd services. Designed to be committed to GitHub.

## Features
- Baldrick CSV poller (dedup by timestamp; stores minute buckets as `device_seen`)
- RTSP → Tripline counter for cars (tunable ROI/line; stores `vehicle` counts per minute)
- REST API:
  - `GET /health`
  - `GET /counts?from=&to=&type=` returns aggregated counts
  - `POST /ingest/autocount` for custom sources
- Writes to SQLite (`data/tracker.db`)

## Hardware/Software
- Raspberry Pi 4 (recommended) with Raspberry Pi OS 64-bit
- Python 3.11+
- OpenCV (CPU) – works without Coral TPU; tune FPS for CPU budget
- UniFi Protect: G3 Bullet with **RTSP** enabled (Protect > Camera > Manage > RTSP: enable a stream)

## Quick Start

```bash
# 1) System packages
sudo apt update
sudo apt install -y python3-venv python3-dev ffmpeg libatlas-base-dev

# 2) Clone and set up
git clone https://github.com/YOUR_GH_USER/lightshow-visitor-tracker-pi.git
cd lightshow-visitor-tracker-pi
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# 3) Configure
cp .env.example .env
nano .env   # set RTSP URL, Baldrick CSV URL, schedule, ROI/tripline, etc.

# 4) Initialize DB
python -m app.db --init

# 5) Run locally (two terminals)
uvicorn app.main:app --host 0.0.0.0 --port 8000
python -m app.scheduler
```

### Enable systemd services

```bash
sudo ./scripts/install_pi.sh
sudo systemctl enable --now lightshow-api.service
sudo systemctl enable --now lightshow-scheduler.service
sudo systemctl status lightshow-api.service lightshow-scheduler.service
```

## Tuning the vehicle counter
- Edit `config.yaml`:
  - `rtsp.url`: your G3 Bullet RTSP URL
  - `roi_polygon`: polygon covering the driveway/road
  - `tripline`: two points defining the counting line
  - `min_contour_area`: filter tiny blobs
  - `fps_target`: limit processing rate to save CPU
- The counter uses background subtraction + centroid tracking + line crossing detection.

## Privacy
- By default, only **counts** and basic metrics are stored (no images or device IDs).
- If you use Baldrick CSV with device MACs, consider enabling hashing/anonymization at the source.

## Excel Dashboard
This repo focuses on collection. Use the Excel template I provided to visualize daily totals. Export daily CSVs with:
```bash
curl 'http://127.0.0.1:8000/counts?type=vehicle&from=2025-11-25&to=2025-12-31' -o vehicle.csv
curl 'http://127.0.0.1:8000/counts?type=device_seen&from=2025-11-25&to=2025-12-31' -o devices.csv
```
Then import into the **AutoCounts** sheet.

---

## Folder Structure
```
app/
  __init__.py
  main.py            # FastAPI app
  config.py          # .env + YAML load
  db.py              # SQLite + SQLAlchemy models + CLI init
  models.py          # ORM
  schemas.py         # Pydantic
  ingest/
    __init__.py
    baldrick_csv.py  # polls CSV URL -> auto_counts
    opencv_counter.py# RTSP tripline counter -> auto_counts
  scheduler.py       # APScheduler jobs (poll baldrick; run RTSP loop)
  utils.py
config.yaml          # ROI/tripline & knobs
.env.example
requirements.txt
scripts/
  install_pi.sh      # systemd setup
systemd/
  lightshow-api.service
  lightshow-scheduler.service
data/                # SQLite DB created at runtime
```

---

## License
MIT

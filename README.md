# 🌟 GlowSync

**GlowSync** is a Raspberry Pi–friendly dashboard for holiday light shows. It pulls visitors from a BaldrickSignals board, counts cars from RTSP cameras (UniFi Protect supported), correlates with FPP playback, and monitors Falcon controllers — all in one UI.

- Minute-level and hourly views (Raw vs Adjusted by Baseline)
- Auto/Manual baseline with trend & recommended baseline
- Seasons (e.g., Halloween 2025, Christmas 2025)
- FPP “now playing” correlation
- Falcon/FPP device monitoring (up/down, last seen)
- Built-in **Apply & Restart** (no SSH needed)
- Export to CSV/Excel and storage usage with manual purge

---

## Quick Start (Raspberry Pi OS / Ubuntu)

```bash
# 1) Install prerequisites
sudo apt update
sudo apt install -y python3-venv python3-pip ffmpeg

# 2) Clone and prepare venv
git clone https://github.com/manderson20/glowsync.git
cd glowsync
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt  # if present (or: pip install fastapi uvicorn[standard] sqlalchemy jinja2 pytz requests)

# 3) (Optional) Create a .env with your initial settings
cat > .env <<'ENV'
TIMEZONE=America/Chicago
DASHBOARD_AUTOREFRESH=60
BALDRICK_BASELINE_MODE=manual
BALDRICK_BASELINE=0
BALDRICK_CSV_URL=http://10.0.0.50/csv
ADMIN_USERNAME=admin
ADMIN_PASSWORD=change-me
ENV

# 4) Install systemd units (if repo includes them) and start services
sudo cp systemd/glowsync-api.service /etc/systemd/system/ 2>/dev/null || true
sudo cp systemd/glowsync-scheduler.service /etc/systemd/system/ 2>/dev/null || true
sudo systemctl daemon-reload 2>/dev/null || true
sudo systemctl enable glowsync-api glowsync-scheduler --now || true

# 5) Run the post-install (installs restart helper + sudoers)
curl -fsSL https://raw.githubusercontent.com/manderson20/glowsync/main/scripts/postinstall.sh | sudo bash

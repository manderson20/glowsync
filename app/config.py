import os, yaml
from dotenv import load_dotenv

load_dotenv()

def load_config():
    with open('config.yaml','r') as f:
        y = yaml.safe_load(f) or {}
    return {
        'baldrick_csv_url': os.getenv('BALDRICK_CSV_URL','').strip(),
        'baldrick_poll_cron': os.getenv('BALDRICK_POLL_CRON','*/5 * * * *'),
        'rtsp_url': os.getenv('RTSP_URL','').strip(),
        'fps_target': int(os.getenv('FPS_TARGET','6')),
        'min_contour_area': int(os.getenv('MIN_CONTOUR_AREA','1200')),
        'db_path': os.getenv('DB_PATH','data/tracker.db'),
        'bind': os.getenv('BIND','0.0.0.0'),
        'port': int(os.getenv('PORT','8000')),
        'timezone': os.getenv('TIMEZONE','America/Chicago'),
        'vision': y or {}
    }

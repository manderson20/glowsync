from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from app.config import load_config
from app.db import init_db
from app.ingest.baldrick_csv import run as run_baldrick
# from app.ingest.opencv_counter import run as run_counter
from app.ingest.opencv_multi import run as run_multi
from app.ingest.monitor_controllers import run as run_monitor, record_fpp_status

cfg = load_config()
init_db(cfg['db_path'])

def job_baldrick():
    print('[baldrick] polling...')
    try:
        res = run_baldrick(cfg['baldrick_csv_url'])
        print('[baldrick]', res)
    except Exception as e:
        print('[baldrick] error', e)

def job_counter():
    pass  # single-camera loop not used when multi is configured
    print('[opencv] running stream loop... (Ctrl+C to stop if run manually)')
    try:
        run_counter(cfg['rtsp_url'], {**cfg, **cfg.get('vision',{})})
    except Exception as e:
        print('[opencv] error', e)

if __name__ == '__main__':
    sched = BlockingScheduler(timezone=cfg['timezone'])
    # Baldrick: cron from env
    sched.add_job(job_baldrick, CronTrigger.from_crontab(cfg['baldrick_poll_cron']), id='baldrick')
    sched.add_job(lambda: (print('[monitor] checking controllers...'), run_monitor()), 'cron', minute='*', id='monitor')
    sched.add_job(lambda: (print('[fpp] sampling now playing...'), record_fpp_status() or True) and (print('[fpp] checking alert...'), __import__('app.ingest.monitor_controllers').ingest.monitor_controllers.check_fpp_alert()), 'interval', seconds=15, id='fpp_status')
    # Counter: run as "daemon" every boot via systemd -> separate service.
    # Here we leave it off, since it's a long-running loop.
    # also start multi-camera loop in foreground thread
    import threading
    threading.Thread(target=run_multi, daemon=True).start()
    print('Scheduler starting...')
    sched.start()

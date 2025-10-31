import cv2, time, json, threading
import numpy as np
from datetime import datetime, timezone
from app.db import get_session, AutoCount, Season
from app.config import load_config
from app.utils import floor_bucket, to_local, in_show_hours

def _denorm(pt, W, H):
    return int(pt[0]*W), int(pt[1]*H)

def worker(cam, tzname):
    name = cam.get('name') or 'camera'
    url = cam['rtsp_url']
    fps_target = int(cam.get('fps_target', 6))
    min_area = int(cam.get('min_contour_area', 1200))
    roi_poly = cam.get('roi_polygon', [])
    tripline = cam.get('tripline', [])
    cap = cv2.VideoCapture(url)
    if not cap.isOpened():
        print(f'[opencv:{name}] cannot open rtsp'); return
    W = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 1280)
    H = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 720)
    fgbg = cv2.createBackgroundSubtractorMOG2(history=500, varThreshold=64, detectShadows=True)
    tracked = {}
    counts_this_bucket = 0
    last_bucket = None
    s = get_session()

    def in_roi(cx, cy):
        if not roi_poly: return True
        poly = np.array([(int(px*W), int(py*H)) for px,py in roi_poly], np.int32)
        return cv2.pointPolygonTest(poly, (cx,cy), False) >= 0

    def crossed(prev, curr):
        if len(tripline)!=2: return False
        (x1,y1) = _denorm(tripline[0], W, H)
        (x2,y2) = _denorm(tripline[1], W, H)
        def side(x,y): return (y2 - y1)*(x - x1) - (x2 - x1)*(y - y1)
        return side(*prev) * side(*curr) < 0

    def current_season():
        from datetime import timezone as _tz
        now = datetime.now(_tz.utc)
        return s.query(Season).filter(Season.start_date <= now, Season.end_date > now).first()

    season = current_season()
    bucket_mins = season.bucket_minutes if season else 1
    show_start = season.show_start if season else '00:00'
    show_end = season.show_end if season else '23:59'

    while True:
        ok, frame = cap.read()
        if not ok: time.sleep(0.4); continue
        now = datetime.now(timezone.utc)
        if not in_show_hours(to_local(now, tzname), show_start, show_end):
            time.sleep(1); continue
        mb = floor_bucket(now, bucket_mins)
        if last_bucket is None: last_bucket = mb
        if mb != last_bucket:
            if counts_this_bucket>0:
                rec = AutoCount(timestamp=last_bucket, source='opencv_tripline',
                                camera_name=name, count_type='vehicle',
                                count_value=counts_this_bucket, meta_json=None,
                                season=season.name if season else None)
                s.add(rec); s.commit()
            counts_this_bucket = 0; last_bucket = mb

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        mask = fgbg.apply(gray)
        mask = cv2.medianBlur(mask,5)
        _,mask = cv2.threshold(mask,200,255,cv2.THRESH_BINARY)
        cnts,_ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        detections = []
        for c in cnts:
            if cv2.contourArea(c) < min_area: continue
            x,y,w,h = cv2.boundingRect(c)
            cx,cy = x+w//2, y+h//2
            if not in_roi(cx,cy): continue
            detections.append((cx,cy))

        # nearest-neighbor tracking
        new_tr = {}; used = set()
        for tid,data in list(tracked.items()):
            prev = data['pos']
            best=None; bestd=1e9; idx=-1
            for i,pt in enumerate(detections):
                if i in used: continue
                d=(pt[0]-prev[0])**2+(pt[1]-prev[1])**2
                if d<bestd: bestd=d; best=pt; idx=i
            if best is not None and bestd < 50**2:
                new_tr[tid]={'pos':best,'counted':data['counted']}
                used.add(idx)
                if not data['counted'] and crossed(prev,best):
                    new_tr[tid]['counted']=True; counts_this_bucket+=1
        next_id = max(new_tr.keys())+1 if new_tr else 1
        for i,pt in enumerate(detections):
            if i in used: continue
            new_tr[next_id]={'pos':pt,'counted':False}; next_id+=1
        tracked=new_tr
        if fps_target>0: time.sleep(max(0,1.0/fps_target))

def run():
    cfg = load_config()
    cams = (cfg.get('vision',{}) or {}).get('cameras') or []
    tzname = cfg.get('timezone','America/Chicago')
    if not cams: return {'skipped':'no cameras configured'}
    threads = []
    for cam in cams:
        t=threading.Thread(target=worker, args=(cam,tzname), daemon=True)
        t.start(); threads.append(t)
    # Keep alive
    while True:
        time.sleep(5)

import cv2, time, json
import numpy as np
from datetime import datetime, timezone
from app.db import get_session, AutoCount, Season
from app.utils import floor_minute, floor_bucket, to_local, in_show_hours
from app.config import load_config

def _denorm(pt, W, H):
    return int(pt[0]*W), int(pt[1]*H)

def run(rtsp_url: str, cfg: dict):
    if not rtsp_url:
        return {'skipped':'no rtsp url'}

    cfg0 = load_config()
    cap = cv2.VideoCapture(rtsp_url)
    if not cap.isOpened():
        return {'error':'cannot open rtsp'}

    W = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 1280)
    H = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 720)
    fps_target = int(cfg.get('fps_target', 6))
    roi_poly = cfg.get('roi_polygon', [])
    tripline = cfg.get('tripline', [])
    min_area = int(cfg.get('min_contour_area', 1200))

    fgbg = cv2.createBackgroundSubtractorMOG2(history=500, varThreshold=64, detectShadows=True)
    tracked = {}
    counts_this_minute = 0
    last_min = None
    s = get_session()

    tzname = cfg0.get('timezone','America/Chicago')

    def in_roi(cx, cy):
        if not roi_poly:
            return True
        poly = np.array([(int(px*W), int(py*H)) for px,py in roi_poly], np.int32)
        return cv2.pointPolygonTest(poly, (cx,cy), False) >= 0

    def crossed(prev, curr):
        if len(tripline) != 2:
            return False
        (x1,y1) = _denorm(tripline[0], W, H)
        (x2,y2) = _denorm(tripline[1], W, H)
        def side(x,y):
            return (y2 - y1)*(x - x1) - (x2 - x1)*(y - y1)
        return side(*prev) * side(*curr) < 0

    # season helpers
    def current_season():
        now = datetime.now(timezone.utc)
        return s.query(Season).filter(Season.start_date <= now, Season.end_date > now).first()

    season = current_season()
    bucket = season.bucket_minutes if season else 1
    show_start = season.show_start if season else '00:00'
    show_end = season.show_end if season else '23:59'

    while True:
        ok, frame = cap.read()
        if not ok:
            time.sleep(0.5)
            continue

        now = datetime.now(timezone.utc)
        # skip if outside show hours
        if not in_show_hours(to_local(now, tzname), show_start, show_end):
            time.sleep(1)
            continue

        mnow = floor_bucket(now, bucket)
        if last_min is None:
            last_min = mnow

        if mnow != last_min:
            if counts_this_minute > 0:
                rec = AutoCount(timestamp=last_min, source='opencv_tripline',
                                camera_name=None, count_type='vehicle',
                                count_value=counts_this_minute, meta_json=None,
                                season=season.name if season else None)
                s.add(rec)
                s.commit()
            counts_this_minute = 0
            last_min = mnow

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        mask = fgbg.apply(gray)
        mask = cv2.medianBlur(mask, 5)
        _, mask = cv2.threshold(mask, 200, 255, cv2.THRESH_BINARY)
        cnts, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        detections = []
        for c in cnts:
            if cv2.contourArea(c) < min_area:
                continue
            x,y,w,h = cv2.boundingRect(c)
            cx,cy = x + w//2, y + h//2
            if not in_roi(cx,cy):
                continue
            detections.append((cx,cy))

        # simple centroid tracking by nearest neighbor
        new_tracked = {}
        used = set()
        for tid, data in tracked.items():
            prev = data['pos']
            best = None
            bestd = 1e9
            idx = -1
            for i, pt in enumerate(detections):
                if i in used:
                    continue
                d = (pt[0]-prev[0])**2 + (pt[1]-prev[1])**2
                if d < bestd:
                    bestd = d
                    best = pt
                    idx = i
            if best is not None and bestd < (50**2):
                new_tracked[tid] = {'pos': best, 'counted': data['counted']}
                used.add(idx)
                if not data['counted'] and crossed(prev, best):
                    new_tracked[tid]['counted'] = True
                    counts_this_minute += 1

        # add unmatched detections as new tracks
        next_id = max(new_tracked.keys()) + 1 if new_tracked else 1
        for i, pt in enumerate(detections):
            if i in used:
                continue
            new_tracked[next_id] = {'pos': pt, 'counted': False}
            next_id += 1

        tracked = new_tracked

        if fps_target > 0:
            time.sleep(max(0, 1.0 / fps_target))

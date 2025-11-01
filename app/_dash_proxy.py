from fastapi import Query, Depends, HTTPException, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import select, func
from typing import Optional
import os, json
import pytz
from datetime import datetime
from app.db import get_session, AutoCount, Controller, Season, Alert
from app.main import templates, _parse_time  # reuse helpers if already defined

def dashboard_local(request: Request,
    group: str = 'day',
    season: str = '',
    camera: str = '',
    date_from: Optional[str] = Query(None, alias='from'),
    date_to: Optional[str] = Query(None, alias='to'),
    corr: str = 'media'
):
    tzname = os.getenv('TIMEZONE', 'America/Chicago')
    tz = pytz.timezone(tzname)

    # Parse incoming date filters (assumed in local date format if provided)
    df = _parse_time(date_from)  # returns aware UTC dt or None
    dt = _parse_time(date_to)

    s = get_session()

    # Fetch raw rows in UTC then convert to local to build labels
    def series_for(ctype: str):
        q = select(AutoCount.timestamp, AutoCount.count_value, AutoCount.camera_name)\
            .where(AutoCount.count_type == ctype)
        if season:
            q = q.where(AutoCount.season == season)
        if df:
            q = q.where(AutoCount.timestamp >= df)
        if dt:
            q = q.where(AutoCount.timestamp < dt)
        if camera and ctype == 'vehicle':
            q = q.where(AutoCount.camera_name == camera)
        q = q.order_by(AutoCount.timestamp.asc())

        rows = s.execute(q).all()

        # Group in LOCAL time
        buckets = {}
        for ts_utc, val, camname in rows:
            # convert to local
            ts_local = ts_utc.astimezone(tz)
            label = ts_local.strftime('%Y-%m-%d') if group == 'day' else ts_local.strftime('%Y-%m-%d %H:00')
            buckets[label] = buckets.get(label, 0) + int(val)

        labels = sorted(buckets.keys())
        values = [buckets[k] for k in labels]
        total = sum(values) if values else 0
        peak_label, peak_count = ('—', 0)
        if values:
            idx = max(range(len(values)), key=lambda i: values[i])
            peak_label, peak_count = labels[idx], values[idx]
        return {'labels': labels, 'values': values, 'total': total, 'peak': {'label': peak_label, 'count': peak_count}}

    veh = series_for('vehicle')
    dev = series_for('device_seen')

    # Controllers / FPP
    total = s.query(Controller).count()
    online = s.query(Controller).filter(Controller.last_status == 'online').count()
    fpp = s.query(Controller).filter(Controller.kind == 'fpp').order_by(Controller.id.asc()).first()
    fpp_info = {}
    if fpp and fpp.last_info_json:
        try:
            fpp_info = json.loads(fpp.last_info_json)
        except Exception:
            fpp_info = {}

    seasons_list = s.query(Season).order_by(Season.start_date.desc()).all()
    cameras = [r[0] for r in s.execute(
        select(AutoCount.camera_name).where(AutoCount.camera_name != None).group_by(AutoCount.camera_name)
    ).all()]
    alerts = s.execute(
        select(Alert.timestamp, Alert.message).where(Alert.active == 1).order_by(Alert.timestamp.desc()).limit(5)
    ).all()

    # Top media, grouped by current local-time-bucket boundaries still uses per-minute pairing in UTC; OK for display
    def correlate_like(sess, season, df, dt, camera):
        from app.db import FPPStatus
        q = select(AutoCount.timestamp, AutoCount.count_value, AutoCount.camera_name).where(AutoCount.count_type == 'vehicle')
        if season: q = q.where(AutoCount.season == season)
        if df: q = q.where(AutoCount.timestamp >= df)
        if dt: q = q.where(AutoCount.timestamp < dt)
        if camera: q = q.where(AutoCount.camera_name == camera)
        q = q.order_by(AutoCount.timestamp.asc())
        rows = sess.execute(q).all()
        q2 = select(FPPStatus.timestamp, FPPStatus.media).order_by(FPPStatus.timestamp.asc())
        frows = sess.execute(q2).all()
        res = {}
        j = 0
        for ts, cnt, camname in rows:
            while j + 1 < len(frows) and frows[j + 1][0] <= ts:
                j += 1
            media = frows[j][1] if frows else '(unknown)'
            if not media: media = '(unknown)'
            res[media] = res.get(media, 0) + int(cnt)
        return sorted(res.items(), key=lambda x: x[1], reverse=True)

    top_media_pairs = correlate_like(s, season, df, dt, camera)[:10]
    top_media = [{'label': k, 'count': v} for k, v in top_media_pairs]

    return templates.TemplateResponse('dashboard.html', {
        'request': request,
        'title': 'Dashboard',
        'charts': {'vehicle': veh, 'device_seen': dev},
        'totals': {'vehicle': veh['total'], 'device_seen': dev['total']},
        'peaks': {'vehicle': veh['peak'], 'device_seen': dev['peak']},
        'controllers': {'online': online, 'total': total},
        'fpp': fpp_info,
        'seasons': seasons_list,
        'cameras': cameras,
        'top_media': top_media,
        'alerts': alerts,
        'params': {'from': date_from or '', 'to': date_to or '', 'group': group, 'season': season, 'camera': camera, 'corr': corr}
    })

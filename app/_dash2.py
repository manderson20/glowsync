import os, json, pytz
from typing import Optional
from datetime import datetime
from sqlalchemy import select, func
from fastapi import Query, Request
from app.db import get_session, AutoCount, Controller, Season, Alert
from app.main import templates, _parse_time

def _auto_baseline(sess, tzname: str, days: int = 7) -> int:
    # 10th percentile of device_seen from last N days (robust floor)
    from datetime import timedelta, timezone
    now = datetime.now(timezone.utc)
    start = now - timedelta(days=days)
    rows = sess.execute(
        select(AutoCount.count_value)
        .where(AutoCount.count_type=='device_seen', AutoCount.source=='baldrick', AutoCount.timestamp>=start)
        .order_by(AutoCount.count_value.asc())
    ).scalars().all()
    if not rows:
        return 0
    idx = max(0, int(len(rows)*0.10)-1)
    return int(rows[idx])

def dashboard_local(request: Request,
    group: str = 'hour',                      # default to hour now
    season: str = '',
    camera: str = '',
    date_from: Optional[str] = Query(None, alias='from'),
    date_to: Optional[str]   = Query(None, alias='to'),
    corr: str = 'media'
):
    tzname = os.getenv('TIMEZONE','America/Chicago')
    import pytz as _p; tz = _p.timezone(tzname)

    # Baseline settings
    mode = os.getenv('BALDRICK_BASELINE_MODE','manual').lower()
    baseline = int(os.getenv('BALDRICK_BASELINE','0') or 0)

    df = _parse_time(date_from)
    dt = _parse_time(date_to)

    s = get_session()

    # compute auto baseline if requested
    if mode == 'auto':
        try:
            baseline = _auto_baseline(s, tzname)
        except Exception:
            baseline = baseline  # fallback to manual

    def series_for(ctype: str):
        # Pull raw rows
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

        # Bucket in LOCAL time
        buckets = {}
        for ts_utc, val, camname in rows:
            ts_local = ts_utc.astimezone(tz)
            if group == 'min':
                label = ts_local.strftime('%Y-%m-%d %H:%M')
            elif group == 'day':
                label = ts_local.strftime('%Y-%m-%d')
            else:
                label = ts_local.strftime('%Y-%m-%d %H:00')

            if ctype == 'device_seen':
                # subtract baseline but not below zero
                v = max(int(val) - baseline, 0)
                # we average instantaneous counts within bucket (smoother)
                agg = buckets.get(label, {'sum':0,'n':0})
                agg['sum'] += v
                agg['n'] += 1
                buckets[label] = agg
            else:
                # vehicles: sum
                buckets[label] = buckets.get(label, 0) + int(val)

        if ctype == 'device_seen':
            labels = sorted(buckets.keys())
            values = [ int(round(buckets[k]['sum']/max(buckets[k]['n'],1))) for k in labels ]
        else:
            labels = sorted(buckets.keys())
            values = [ buckets[k] for k in labels ]

        total = sum(values) if values else 0
        peak_label, peak_count = ('—', 0)
        if values:
            idx = max(range(len(values)), key=lambda i: values[i])
            peak_label, peak_count = labels[idx], values[idx]
        return {'labels': labels, 'values': values, 'total': total, 'peak': {'label': peak_label, 'count': peak_count}}

    veh = series_for('vehicle')
    dev = series_for('device_seen')

    # Controllers/FPP/alerts (unchanged)
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
        'alerts': alerts,
        # pass group + baseline so UI can show them
        'params': {'from': date_from or '', 'to': date_to or '', 'group': group, 'season': season, 'camera': camera, 'corr': corr,
                   'baseline': baseline, 'baseline_mode': mode}
    })

from datetime import datetime, timezone
from typing import Dict
from app.db import get_session, Controller
from icmplib import ping
import httpx
import json

def check_http(ip: str, paths):
    for p in paths:
        url = f'http://{ip}{p}'
        try:
            r = httpx.get(url, timeout=3.0)
            if r.status_code < 500:
                return True
        except Exception:
            continue
    return False


def fpp_now_playing(ip: str):
    # Try FPP API v5+ endpoints first, then older fppjson.php
    paths = [
        '/api/system/status',                        # general system status
        '/api/fppd/status',                          # fppd state
        '/api/fppd/playlist',                        # current playlist
        '/api/fppd/media',                            # current media/sequence
        '/fppjson.php?command=getFPPDstatus',       # legacy
        '/fppjson.php?command=getStatus'            # legacy
    ]
    info = {}
    for p in paths:
        url = f'http://{ip}{p}'
        try:
            r = httpx.get(url, timeout=3.0)
            if r.status_code >= 500: 
                continue
            try:
                j = r.json()
            except Exception:
                continue
            # Heuristic merge of common fields across versions
            if isinstance(j, dict):
                # state
                state = j.get('state') or j.get('FPPDStatus') or j.get('fppd_state') or j.get('statusName')
                if state: info['state'] = state
                # playlist/media/song fields
                for k in ['current_playlist', 'CurrentPlaylist', 'playlist', 'Playlist', 'playlistName']:
                    if k in j: info['playlist'] = j[k]
                for k in ['media', 'sequence', 'Sequence', 'current_sequence', 'song', 'Song']:
                    if k in j: info['media'] = j[k]
                # times
                for k in ['elapsed', 'elapsed_ms', 'secondsElapsed']:
                    if k in j: info['elapsed'] = j[k]
                for k in ['duration', 'secondsRemaining']:
                    if k in j: info['duration'] = j[k]
                # hostname/version
                for k in ['hostname','HostName']:
                    if k in j: info['hostname'] = j[k]
                for k in ['fpp_version','version']:
                    if k in j: info['version'] = j[k]
        except Exception:
            continue
    return info


def run():
    s = get_session()
    ctrls = s.query(Controller).all()
    for c in ctrls:
        status = 'offline'
        rtt_ms = None
        # ICMP ping (requires CAP_NET_RAW or sudo). If not allowed, fallback to HTTP-only.
        try:
            r = ping(c.ip, count=2, interval=0.2, timeout=1, privileged=False)
            if r.packets_received>0:
                rtt_ms = int(r.avg_rtt*1000)
                status = 'online'
        except Exception:
            # ignore
            pass
        # HTTP probe per kind
        if c.kind == 'falcon':
            ok = check_http(c.ip, ['/', '/index.html'])
            status = 'online' if ok or status=='online' else 'offline'
        elif c.kind == 'fpp':
            # Try to capture Now Playing details for FPP
            details = fpp_now_playing(c.ip)
            if details:
                c.last_info_json = json.dumps(details)
            ok = check_http(c.ip, ['/api/system/status', '/fppjson.php?command=getFPPDstatus', '/'])
            status = 'online' if ok or status=='online' else 'offline'
        # Write back
        c.last_status = status
        c.last_rtt_ms = rtt_ms
        c.last_checked = datetime.now(timezone.utc)
        s.add(c)
    s.commit()
    return {'checked': len(ctrls)}


from app.db import get_session, Controller
from app.db import FPPStatus as _FPPStatus
from datetime import datetime, timezone as _tz

def record_fpp_status():
    s = get_session()
    fpp = s.query(Controller).filter(Controller.kind=='fpp').order_by(Controller.id.asc()).first()
    if not fpp:
        return {'skipped':'no fpp controller configured'}
    details = fpp_now_playing(fpp.ip)
    if not details:
        return {'skipped':'no details'}
    rec = _FPPStatus(
        timestamp=datetime.now(_tz.utc),
        hostname=details.get('hostname'),
        version=details.get('version'),
        state=details.get('state'),
        playlist=details.get('playlist'),
        media=details.get('media'),
        raw_json=json.dumps(details)
    )
    s.add(rec); s.commit()
    return {'ok': True, 'id': rec.id}


from app.db import Alert as _Alert, Season as _Season
from app.utils import to_local, in_show_hours
def check_fpp_alert():
    s = get_session()
    fpp = s.query(Controller).filter(Controller.kind=='fpp').order_by(Controller.id.asc()).first()
    if not fpp: return
    # grab latest status
    from app.db import FPPStatus as _FPPStatus
    latest = s.query(_FPPStatus).order_by(_FPPStatus.timestamp.desc()).first()
    if not latest: return
    now = latest.timestamp
    # show-hours window
    season = s.query(_Season).filter(_Season.start_date <= now, _Season.end_date > now).first()
    if season and not in_show_hours(to_local(now, 'America/Chicago'), season.show_start, season.show_end):
        return
    # if state not playing, open an alert if none active
    bad = str(latest.state or '').lower() not in ('playing','play','running')
    if bad:
        exists = s.query(_Alert).filter(_Alert.active==1, _Alert.message.like('%FPP%stopped%')).first()
        if not exists:
            s.add(_Alert(timestamp=now, severity='error', message='FPP appears stopped during show hours', active=1)); s.commit()
    else:
        # resolve active alert
        for a in s.query(_Alert).filter(_Alert.active==1, _Alert.message.like('%FPP%stopped%')).all():
            a.active=0; s.add(a)
        s.commit()

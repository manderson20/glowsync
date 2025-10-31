from datetime import datetime, timezone, timedelta
import pytz

def floor_minute(dt: datetime) -> datetime:
    return dt.replace(second=0, microsecond=0)

def floor_bucket(dt: datetime, minutes: int) -> datetime:
    dt0 = dt.replace(second=0, microsecond=0)
    bucket = (dt0.minute // minutes) * minutes
    return dt0.replace(minute=bucket)

def in_show_hours(local_dt: datetime, start_hhmm: str, end_hhmm: str) -> bool:
    # Handles windows that may cross midnight (e.g., 17:00 to 00:30)
    s_h, s_m = map(int, start_hhmm.split(':'))
    e_h, e_m = map(int, end_hhmm.split(':'))
    start = local_dt.replace(hour=s_h, minute=s_m, second=0, microsecond=0)
    end = local_dt.replace(hour=e_h, minute=e_m, second=0, microsecond=0)
    if end <= start:  # crosses midnight
        return local_dt >= start or local_dt < end + timedelta(days=0)
    else:
        return start <= local_dt < end

def to_local(dt: datetime, tzname: str) -> datetime:
    tz = pytz.timezone(tzname)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(tz)

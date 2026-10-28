"""Owner's Toronto 22:00--04:00 window, including both DST transitions.

The evening date identifies a run; midnight never creates a second night.
Deadlines use absolute UTC plus a monotonic cap in the supervising process.
No system clock, service, scheduler or running producer is changed here.
"""
from datetime import datetime,time,timedelta,timezone
import math
from zoneinfo import ZoneInfo


ZONE=ZoneInfo('America/Toronto')


def bounds(day):
    start=datetime.combine(day,time(22),ZONE).astimezone(timezone.utc)
    end=datetime.combine(day+timedelta(days=1),time(4),ZONE).astimezone(timezone.utc)
    return start,end


def night(now):
    if now.tzinfo is None:raise ValueError('aware actual clock required')
    local=now.astimezone(ZONE)
    return local.date()-timedelta(days=1) if local.hour<4 else local.date()


def validate(start,end):
    if start.tzinfo is None or end.tzinfo is None:raise ValueError('aware overnight bounds required')
    expected_start,expected_end=bounds(night(start))
    if start!=expected_start or end!=expected_end:
        raise ValueError('exact Toronto 22:00--04:00 hard-stop window required')
    return expected_start,expected_end


def seconds_left(deadline,*,now=None):
    if isinstance(deadline,str):deadline=datetime.fromisoformat(deadline)
    now=now or datetime.now(timezone.utc)
    if deadline.tzinfo is None or now.tzinfo is None:raise ValueError('aware hard deadline required')
    remaining=(deadline-now).total_seconds()
    if not math.isfinite(remaining) or remaining<=0:
        raise TimeoutError('hard backup deadline reached; preserve completed points')
    return remaining

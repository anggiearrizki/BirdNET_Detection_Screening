"""Select recordings by recording time, independently of scanner IDs."""
from datetime import datetime, timedelta, timezone

STATION_TIMEZONE = timezone(timedelta(hours=7))

def recording_time(record):
    value = record.get("timestamp")
    if not value:
        date = record.get("date")
        time = record.get("time")
        if not date or not time:
            raise ValueError("Recording date/time is missing; cannot select recent work.")
        value = f"{date}T{time}"
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=STATION_TIMEZONE)
    return parsed.astimezone(timezone.utc)

def date_boundary(value):
    """Midnight at the stations, returned in UTC."""
    from datetime import date
    parsed = date.fromisoformat(value)
    return datetime.combine(parsed, datetime.min.time(), STATION_TIMEZONE).astimezone(timezone.utc)

def in_window(record, cutoff=None, before=None):
    timestamp = recording_time(record)
    return (cutoff is None or timestamp >= cutoff) and (before is None or timestamp < before)

def recent_ids(records, cutoff=None, before=None):
    return [int(r["detection_id"]) for r in sorted(
        (r for r in records if in_window(r, cutoff, before)),
        key=recording_time, reverse=True)]

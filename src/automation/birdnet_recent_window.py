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

def recent_ids(records, cutoff):
    return [int(r["detection_id"]) for r in sorted(
        (r for r in records if recording_time(r) >= cutoff),
        key=recording_time, reverse=True)]

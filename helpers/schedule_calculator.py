import requests
from datetime import datetime, timedelta, time
import zoneinfo
from config import ACCESS_TOKEN, IG_USER_ID, TIMEZONE

def get_local_tz():
    try:
        return zoneinfo.ZoneInfo(TIMEZONE)
    except Exception:
        return zoneinfo.ZoneInfo("Asia/Ho_Chi_Minh")

def get_latest_instagram_post_timestamp():
    """Fetch the timestamp of the latest published post on Instagram feed."""
    if not all([IG_USER_ID, ACCESS_TOKEN]):
        print("[Schedule] IG_USER_ID or ACCESS_TOKEN missing. Using current time.")
        return None
    try:
        url = f"https://graph.facebook.com/v18.0/{IG_USER_ID}/media"
        params = {
            'fields': 'timestamp',
            'limit': 5,
            'access_token': ACCESS_TOKEN
        }
        res = requests.get(url, params=params, timeout=10)
        if res.status_code == 200:
            data = res.json().get('data', [])
            timestamps = []
            local_tz = get_local_tz()
            for item in data:
                ts_str = item.get('timestamp')
                if ts_str:
                    # Meta API returns ISO timestamps like 2026-07-25T14:30:00+0000
                    dt = datetime.fromisoformat(ts_str.replace('+0000', '+00:00'))
                    timestamps.append(dt.astimezone(local_tz))
            if timestamps:
                latest = max(timestamps)
                print(f"[Schedule] Latest published post on IG: {latest.strftime('%Y-%m-%d %H:%M:%S %Z')}")
                return latest
    except Exception as e:
        print(f"[Schedule] Failed to fetch Instagram feed timestamp: {e}")
    return None

def calculate_next_optimal_slot(last_post_time=None, min_gap_hours=6):
    """
    Calculate the next optimal posting time based on peak engagement windows
    (11:30 - 13:00 and 19:30 - 22:00 Local Time) respecting minimum spacing gap.
    """
    local_tz = get_local_tz()
    now = datetime.now(local_tz)

    # Minimum time from now (IG API requires scheduled post >= 15 min in future)
    earliest_allowed = now + timedelta(minutes=30)

    if last_post_time is not None:
        if last_post_time.tzinfo is None:
            last_post_time = last_post_time.replace(tzinfo=local_tz)
        start_search = max(earliest_allowed, last_post_time + timedelta(hours=min_gap_hours))
    else:
        start_search = earliest_allowed

    # Candidate peak time targets (hour, minute)
    # Peak 1: 12:00 (midday peak)
    # Peak 2: 20:00 (evening peak)
    peak_targets = [(12, 0), (20, 0)]

    current_day = start_search.date()
    for day_offset in range(14): # Check up to 14 days ahead
        check_date = current_day + timedelta(days=day_offset)
        for hour, minute in peak_targets:
            candidate = datetime.combine(check_date, time(hour, minute), tzinfo=local_tz)
            if candidate >= start_search:
                print(f"[Schedule] Calculated optimal post time: {candidate.strftime('%Y-%m-%d %H:%M:%S %Z')}")
                return candidate.isoformat()

    # Fallback to 1 hour from start_search
    fallback = start_search + timedelta(hours=1)
    return fallback.isoformat()

def get_calculated_schedule_for_new_post(pending_drafts=None):
    latest_ig_time = get_latest_instagram_post_timestamp()
    
    # If there are pending drafts, find the maximum scheduled time among them
    local_tz = get_local_tz()
    latest_time = latest_ig_time

    if pending_drafts:
        for draft in pending_drafts:
            sched_str = draft.get("scheduled_time")
            if sched_str:
                try:
                    dt = datetime.fromisoformat(sched_str)
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=local_tz)
                    if latest_time is None or dt > latest_time:
                        latest_time = dt
                except Exception:
                    pass

    return calculate_next_optimal_slot(latest_time)

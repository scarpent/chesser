import re
from datetime import datetime, timezone

from django.utils.timesince import timesince

BEGINNING_OF_TIME = 0  # 1970-01-01T00:00:00
END_OF_TIME = 253402300799
END_OF_TIME_STR = "9999-12-31T23:59:59"


def strip_move_numbers(move_str):
    return re.sub(r"\d+\.(\.\.)?", "", move_str).strip()


def get_time_ago(now, result_datetime):
    if not result_datetime:
        time_ago = "Never"
    elif now < result_datetime:
        time_ago = "In the future?!"
    else:
        time_ago = timesince(result_datetime, now)
        time_ago = time_ago.split(",")[0] + " ago"  # Largest unit

    return time_ago


def format_time_until(now, next_review):
    if now > next_review:
        return "right now"
    elif next_review == datetime.fromtimestamp(END_OF_TIME, timezone.utc):
        return "The End of Time"

    time_until = next_review - now
    days, remainder = divmod(time_until.total_seconds(), 24 * 60 * 60)  # a day
    hours, remainder = divmod(remainder, 60 * 60)  # an hour
    minutes, seconds = divmod(remainder, 60)

    parts = []
    if days:
        parts.append(f"{int(days)}d")
        if hours and days < 2:
            parts.append(f"{int(hours)}h")
    elif hours:
        parts.append(f"{int(hours)}h")
        if minutes:
            parts.append(f"{int(minutes)}m")
    elif minutes:
        parts.append(f"{int(minutes)}m")
        if seconds and minutes < 5:
            parts.append(f"{int(seconds)}s")
    else:
        parts.append(f"{int(seconds)}s")

    return " ".join(parts)

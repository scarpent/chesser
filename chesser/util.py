from django.utils.timesince import timesince


def get_time_ago(now, result_datetime):
    if now < result_datetime:
        date_unit = "In the future?!"
    else:
        time_ago = timesince(result_datetime, now)
        date_unit = time_ago.split(",")[0] + " ago"  # Largest unit

    return date_unit

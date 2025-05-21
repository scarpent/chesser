import re
from datetime import datetime, timedelta, timezone

import nh3
from django.utils.timesince import timesince
from django.utils.timezone import localtime

BEGINNING_OF_TIME = 0  # 1970-01-01T00:00:00
END_OF_TIME = 253402300799
END_OF_TIME_STR = "9999-12-31T23:59:59"

# fmt: off
ALLOWED_TAGS = {
    "b", "i", "u", "em", "strong", "a", "br", "ul", "ol", "li",
    "code", "pre", "blockquote", "fenseq",
}
# fmt: on
BLOCK_TAGS = {"ul", "ol", "li", "pre", "blockquote"}

ALLOWED_ATTRIBUTES = {
    "a": {"href", "title", "target"},
    "fenseq": {
        "data-fen",
    },
}


def clean_html(text):
    return nh3.clean(
        text,
        tags=ALLOWED_TAGS,
        attributes=ALLOWED_ATTRIBUTES,
        url_schemes={"http", "https", "mailto"},
    )


def strip_move_numbers(move_str):
    return re.sub(r"\d+\.(\.\.)?", "", move_str).strip()


def get_time_ago(now, result_datetime):
    now_local = localtime(now)
    result_local = localtime(result_datetime)

    if not result_local:
        return "Never"
    if now_local < result_local:
        return "In the future?!"

    delta = now_local - result_local

    if delta < timedelta(minutes=10):
        return "just now"
    if now_local.date() == result_local.date():
        return "today"
    if (now_local.date() - result_local.date()).days == 1:
        return "yesterday"
    if delta.days < 13:
        return f"{delta.days} days ago"

    parts = timesince(result_local, now_local).split(", ")
    if len(parts) >= 2:
        if "month" in parts[0] and "week" in parts[1]:
            months = int(parts[0].split()[0])
            weeks = int(parts[1].split()[0])
            if weeks >= 3:
                return f"{months + 1} months ago"
    return parts[0] + " ago"


def format_time_until(now, next_review):
    if now > next_review:
        return "right now"
    elif next_review == datetime.fromtimestamp(END_OF_TIME, timezone.utc):
        return "end of time"

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


def format_local_date(dt):
    """
    Returns a nicely formatted datetime string like: '8 March 2022'
    """
    dt_local = localtime(dt)
    return dt_local.strftime("%-d %B %Y")


def get_common_move_prefix_html(mainline_moves_str, previous_moves, use_class=True):
    """
    Returns (html, current_moves_list), where html has the common
    prefix styled inline or with a class. Useful for visually
    grouping similar variations.
    """
    current_moves = mainline_moves_str.split()
    common_len = 0
    for a, b in zip(previous_moves, current_moves):
        if a == b:
            common_len += 1
        else:
            break

    common_moves = " ".join(current_moves[:common_len])
    rest_moves = " ".join(current_moves[common_len:])

    if use_class:
        attribute = 'class="common-moves"'
    else:
        attribute = 'style="color: #888"'

    common_span = f"<span {attribute}>{common_moves} </span>" if common_moves else ""

    return f"{common_span} {rest_moves}".strip(), current_moves


def normalize_notation(moves):
    """
    normalize move strings, e.g. 1. e4 e5 2. Nf3 ➤ 1.e4 e5 2.Nf3

    will *also* fix really messed up strings like: 1. e4e52. Bc4Nf63. d3c6

    move string must start with a number and at least one dot
    """
    regex = r"""(?x)
        ^(                                          # one big capture
            (?:
                \d+\.+                              # move number + dots
                |
                [a-h](?:x[a-h])?[1-8](?:=[QRNB])?   # pawn
                |
                [RNQBK][a-h1-8]?x?[a-h][1-8]        # pieces
                |
                O-O(?:-O)?                          # castles
            )
            [+#]?                                   # check/mate
        )"""

    old_string = moves.strip()
    new_string = ""

    while True:
        m = re.match(regex, old_string)
        if not m:
            break
        space = "" if m.group()[-1] == "." else " "
        new_string += f"{m.group()}{space}"
        old_string = old_string[m.end() :].strip()  # noqa: E203

    return new_string.strip()

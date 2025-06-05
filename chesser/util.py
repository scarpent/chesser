import re
from datetime import datetime, timezone

import nh3
from django.utils.timesince import timesince
from django.utils.timezone import localtime

BEGINNING_OF_TIME = 0  # 1970-01-01T00:00:00
END_OF_TIME = 253402300799
END_OF_TIME_STR = "9999-12-31T23:59:59"

# fmt: off
ALLOWED_TAGS = {
    "b", "i", "u", "em", "strong", "a", "hr", "br", "ul", "ol", "li",
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


def strip_all_html(text: str) -> str:
    return nh3.clean(text, tags=set(), attributes={})


def strip_move_numbers(move_str):
    return re.sub(r"\d+\.(\.\.)?", "", move_str).strip()


def plural(unit: str, count: int) -> str:
    return f"{count} {unit}" + ("s" if count != 1 else "") + " ago"


def get_time_ago(now, result_datetime):
    if not result_datetime:
        return "Never"
    if now < result_datetime:
        return "In the future?!"

    delta = now - result_datetime
    seconds = delta.total_seconds()
    days = delta.days

    # we'll micromanage things in the early going
    if seconds < 13 * 60:
        return "just now"
    if seconds < 26 * 60:
        return plural("minute", int(seconds // 60))
    if seconds < 35 * 60:
        return "a half hour ago"
    if seconds < 50 * 60:
        return plural("minute", int(seconds // 60))
    if seconds < 90 * 60:
        return "an hour ago"
    if seconds < 120 * 60:
        return "2 hours ago"
    if seconds < 24 * 60 * 60:
        return plural("hour", int(seconds // 3600))
    if days < 14:
        return plural("day", days)
    if days < 60:
        return plural("week", days // 7)
    if days < 365:
        return plural("month", days // 30)
    return timesince(result_datetime, now) + " ago"


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
    grouping similar variations as in the chapter variations list.
    """
    current_moves = mainline_moves_str.split()
    common_len = 0
    for a, b in zip(previous_moves, current_moves):
        if a == b:
            common_len += 1
        else:
            break

    common_moves = " ".join(current_moves[:common_len])
    rest_of_moves = " ".join(current_moves[common_len:])

    if use_class:
        attribute = 'class="common-moves"'
    else:
        attribute = 'style="color: #888"'

    common_span = f"<span {attribute}>{common_moves} </span>" if common_moves else ""

    return f"{common_span} {rest_of_moves}".strip(), current_moves


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

#!/usr/bin/env python3

import os
from pathlib import Path

# Google's Noto Emoji
# https://github.com/googlefonts/noto-emoji


def get_repo_root() -> Path:
    # bin/get_noto_emoji.py -> repo root is one level up
    return Path(__file__).resolve().parent.parent


REPO_ROOT = get_repo_root()

# Local checkout of noto-emoji repo
SVG_SOURCE_DIR = Path(os.path.expanduser("~/src/noto-emoji/svg"))
PNG_SOURCE_DIR = Path(os.path.expanduser("~/src/noto-emoji/png/32"))

# Targets inside this repo
SVG_TARGET_DIR = REPO_ROOT / "static" / "icons" / "noto-emoji"
PNG_TARGET_DIR = REPO_ROOT / "docs" / "images" / "noto-32"

for d in (SVG_SOURCE_DIR, PNG_SOURCE_DIR):
    if not d.is_dir():
        raise SystemExit(f"Source dir not found: {d}")

SVG_TARGET_DIR.mkdir(parents=True, exist_ok=True)
PNG_TARGET_DIR.mkdir(parents=True, exist_ok=True)

# This serves as a reference for the emoji buttons in the app
emoji_buttons = {
    "home": "🏠",
    "review": "📝",
    "variation": "📚️",
    "edit": "🛠️",
    "import": "📦️",
    "add": "📥️",
    "analysis": "🧮",
    "save": "💾",
    "restart": "♻️",  # "🔄",
    "info": "👁️",
    "showmove": "💣️",
    "back": "⬅️",
    "forward": "➡️",
    "up": "⬆️",
    "upload": "📎",  # "⤴️",
    "random": "🎲",
    "stats": "🎯",  # "🔢",
    "clone": "🧬",
    "complete": "💥",
    "puzzles": "🧩",
}


def emoji_to_codepoint(emoji: str) -> str:
    """
    Return the primary codepoint used by Noto filenames.
    (Matches existing SVG behavior exactly.)
    """
    return "-".join(f"{ord(c):x}" for c in emoji).split("-")[0]


def copy_file(source: Path, target: Path):
    if not source.exists():
        print(f"❌ Source file does not exist: {source}")
        return
    with open(source, "rb") as f:
        content = f.read()
    with open(target, "wb") as f:
        f.write(content)


print(f"\nCopying Noto Emoji SVG files from {SVG_SOURCE_DIR} to {SVG_TARGET_DIR}")
for name, emoji in emoji_buttons.items():
    codepoints = emoji_to_codepoint(emoji)
    source = SVG_SOURCE_DIR / f"emoji_u{codepoints}.svg"
    target = SVG_TARGET_DIR / f"{name}.svg"

    print(f"{name:10} {codepoints:6} {emoji}")
    copy_file(source, target)


print(f"\nCopying Noto Emoji PNG files from {PNG_SOURCE_DIR} to {PNG_TARGET_DIR}")
for name, emoji in emoji_buttons.items():
    codepoints = emoji_to_codepoint(emoji)
    source = PNG_SOURCE_DIR / f"emoji_u{codepoints}.png"
    target = PNG_TARGET_DIR / f"{name}.png"

    print(f"{name:10} {codepoints:6} {emoji}")
    copy_file(source, target)

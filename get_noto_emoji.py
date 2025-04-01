import os

# Google's Noto Emoji
# https://github.com/googlefonts/noto-emoji

SOURCE_DIR = os.path.expanduser("~/src/noto-emoji/svg")
TARGET_DIR = "static/icons/noto-emoji"

# This serves as a reference for the emoji buttons in the app
emoji_buttons = {
    "home": "🏠",
    "review": "📝",
    "variation": "📚️",
    "edit": "🛠️",
    "import": "📦️",
    "analysis": "🧮",
    "save": "💾",
    "restart": "🔄",
    "info": "👁️",
    "showmove": "💣️",
    "back": "⬅️",
    "forward": "➡️",
    "upload": "⤴️",
    "random": "🎲",
    "stats": "🔢",
}


def emoji_to_codepoint(emoji):
    return "-".join(f"{ord(c):x}" for c in emoji).split("-")[0]


print(f"Copying Noto Emoji SVG files from {SOURCE_DIR} to {TARGET_DIR}")
for name, emoji in emoji_buttons.items():
    codepoints = emoji_to_codepoint(emoji)
    source_path = f"{SOURCE_DIR}/emoji_u{codepoints}.svg"
    filename = f"{name}.svg"
    target_path = os.path.join(TARGET_DIR, filename)

    print(f"{name:10} {codepoints:6} {emoji}")
    if not os.path.exists(source_path):
        print(f"❌ Source file does not exist: {source_path}")
        continue
    with open(source_path, "rb") as f:
        content = f.read()
    with open(target_path, "wb") as f:
        f.write(content)

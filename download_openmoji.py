import os

import requests

SAVE_DIR = "static/icons/openmoji"
os.makedirs(SAVE_DIR, exist_ok=True)

emoji_buttons = {
    "home": "🏠",
    "review": "📝",
    "import": "📦️",
    "restart": "🔄",
    "info": "👁️",
    "showmove": "💣️",
    "edit": "🛠️",
    "view": "📚️",
    "back": "⬅️",
    "forward": "➡️",
    "analysis": "🧮",
}


def emoji_to_codepoints(emoji):
    return "-".join(f"{ord(c):X}" for c in emoji).split("-")[0]


base_url = "https://cdn.jsdelivr.net/npm/openmoji/color/svg/"

failed = 0

for name, emoji in emoji_buttons.items():
    codepoints = emoji_to_codepoints(emoji)
    url = f"{base_url}{codepoints}.svg"
    filename = f"{name}.svg"
    dest_path = os.path.join(SAVE_DIR, filename)

    try:
        print(f"Downloading {emoji} ({name}) from {url}")
        resp = requests.get(url)
        if resp.status_code == 200:
            with open(dest_path, "wb") as f:
                f.write(resp.content)
            print(f"💾 Saved to {dest_path}")
        else:
            print(f"⚠️  Failed ({resp.status_code}): {url}")
            failed += 1
            if failed > 2:
                print("❌ Too many failures!")
                break
    except Exception as e:
        print(f"❌ Error downloading {url}: {e}")

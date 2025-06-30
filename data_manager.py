from pathlib import Path
import json
from filelock import FileLock
import sys

# ──────────────────────────────────────
# Використовуємо монтування Render Persistent Disk
BASE_DIR  = Path("/data")             # сюди Render змонтував Persistent Disk
BASE_DIR.mkdir(exist_ok=True)           # створити папку, якщо ще не створена
DATA_FILE = BASE_DIR / "data.json"
LOCK_FILE = BASE_DIR / "data.lock"
# ──────────────────────────────────────

def load_data() -> dict:
    print("[DEBUG] load_data() ->", DATA_FILE, file=sys.stderr)
    with FileLock(str(LOCK_FILE)):
        if not DATA_FILE.exists():
            print("[DEBUG] data.json не знайдено, повертаю {}", file=sys.stderr)
            return {}
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            d = json.load(f)
        print(f"[DEBUG] load_data прочитано {len(d)} користувачів", file=sys.stderr)
        return d

 def save_data(data: dict) -> None:
    print("[DEBUG] save_data() викликано. Спроба записати", file=sys.stderr)
    try:
        with FileLock(str(LOCK_FILE)):
            tmp = DATA_FILE.with_suffix(".tmp")   # data.tmp
            print(f"[DEBUG] Записую у тимчасовий файл {tmp}", file=sys.stderr)
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            tmp.replace(DATA_FILE)
            print(f"[DEBUG] Замінив {tmp} → {DATA_FILE}", file=sys.stderr)
    except Exception as e:
        print("[ERROR] save_data failed:", e, file=sys.stderr)
        raise

from pathlib import Path
import json
from filelock import FileLock

# Абсолютний шлях до data.json поруч із цим скриптом
BASE_DIR  = Path(__file__).resolve().parent
DATA_FILE = BASE_DIR / "data.json"
LOCK_FILE = BASE_DIR / "data.lock"

def load_data() -> dict:
    """
    Зчитує JSON-дані з DATA_FILE під блокуванням.
    Якщо файл не існує, повертає порожній словник.
    """
    with FileLock(str(LOCK_FILE)):
        if not DATA_FILE.exists():
            return {}
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)


def save_data(data: dict) -> None:
    """
    Пише словник у DATA_FILE під блокуванням через тимчасовий файл для атомарності.
    """
    with FileLock(str(LOCK_FILE)):
        tmp = DATA_FILE.with_suffix(".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        tmp.replace(DATA_FILE)

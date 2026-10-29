"""Raw message ledger: every message in and out, append-only, one JSONL file per day.

The ledger is the single source of truth for her memory; anything built later (notes, search
indexes) must be rebuildable from it.
"""

import datetime
import json
import time
import zoneinfo
from pathlib import Path


class Ledger:
    def __init__(self, root: Path, timezone: str):
        self.root = root
        self.zone = zoneinfo.ZoneInfo(timezone)
        self.root.mkdir(parents=True, exist_ok=True)

    def write(self, row: dict) -> None:
        now = time.time()
        day = datetime.datetime.fromtimestamp(now, self.zone).strftime("%Y-%m-%d")
        with (self.root / f"{day}.jsonl").open("a", encoding="utf-8") as file:
            file.write(json.dumps({"t": round(now, 3), **row}, ensure_ascii=False) + "\n")

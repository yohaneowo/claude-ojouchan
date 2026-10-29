"""Daily spend for Claude calls, computed from each response's token usage."""

import datetime
import json
import time
import zoneinfo
from pathlib import Path

# USD per million tokens. Cache writes use the 5-minute TTL (1.25x input).
# Haiku 5.5 doubles its prices above 100K prompt tokens; our prompts stay far below that.
PRICES = {
    "claude-sonnet-5-5": {"input": 2.0, "output": 10.0, "cache_read": 0.20, "cache_write": 2.50},
    "claude-haiku-5-5": {"input": 0.10, "output": 0.50, "cache_read": 0.01, "cache_write": 0.125},
}
# An unknown model is charged at Sonnet prices so the cap errs on the safe side.
FALLBACK = PRICES["claude-sonnet-5-5"]


class BudgetExceeded(Exception):
    pass


class Spend:
    def __init__(self, root: Path, cap_usd: float, timezone: str):
        self.root = root
        self.cap = cap_usd
        self.zone = zoneinfo.ZoneInfo(timezone)
        self.root.mkdir(parents=True, exist_ok=True)
        self.day = self.today()
        self.total = self.load(self.day)

    def today(self) -> str:
        return datetime.datetime.now(self.zone).strftime("%Y-%m-%d")

    def file(self, day: str) -> Path:
        return self.root / f"usage-{day[:7]}.jsonl"

    def load(self, day: str) -> float:
        total = 0.0
        path = self.file(day)
        if path.exists():
            for line in path.read_text(encoding="utf-8").splitlines():
                try:
                    row = json.loads(line)
                except ValueError:
                    continue
                if row.get("day") == day:
                    total += row.get("usd", 0.0)
        return total

    def spent(self) -> float:
        day = self.today()
        if day != self.day:
            self.day, self.total = day, 0.0
        return self.total

    def over(self) -> bool:
        return self.spent() >= self.cap

    def check(self) -> None:
        if self.over():
            raise BudgetExceeded(f"daily budget of ${self.cap:.2f} is used up")

    def record(self, model: str, usage) -> float:
        """Record one response. `usage` is the Anthropic SDK usage object of that response."""
        price = PRICES.get(model, FALLBACK)
        tokens = {
            "input": getattr(usage, "input_tokens", 0) or 0,
            "cache_write": getattr(usage, "cache_creation_input_tokens", 0) or 0,
            "cache_read": getattr(usage, "cache_read_input_tokens", 0) or 0,
            "output": getattr(usage, "output_tokens", 0) or 0,
        }
        usd = sum(tokens[kind] * price[kind] for kind in tokens) / 1_000_000
        self.spent()
        self.total += usd
        row = {"t": round(time.time(), 3), "day": self.day, "model": model, **tokens, "usd": round(usd, 6)}
        with self.file(self.day).open("a", encoding="utf-8") as file:
            file.write(json.dumps(row) + "\n")
        return usd

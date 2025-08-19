"""Lightweight logging utility for ArgosEnv (FUP-10).

Provides:
- Configurable log levels (DEBUG < INFO < WARN < ERROR)
- Optional JSON line output (log_format='json') for structured consumption
- Graceful no-op when message level below configured threshold

Rationale: Avoid pulling in Python's full logging configuration complexity for
this small project while enabling a quiet / reduced output mode in CI and tests.
"""
from __future__ import annotations
import json
import sys
import datetime as _dt
from typing import Any, Dict

_LEVEL_ORDER = {"DEBUG": 10, "INFO": 20, "WARN": 30, "ERROR": 40}


class SimpleLogger:
    def __init__(self, level: str = "INFO", log_format: str = "text"):
        level = level.upper()
        if level not in _LEVEL_ORDER:
            raise ValueError(f"Unknown log level '{level}'")
        if log_format not in ("text", "json"):
            raise ValueError("log_format must be 'text' or 'json'")
        self.level = level
        self.log_format = log_format

    def _enabled(self, level: str) -> bool:
        return _LEVEL_ORDER[level] >= _LEVEL_ORDER[self.level]

    def _emit(self, level: str, message: str, **fields: Any):
        if not self._enabled(level):
            return
        ts = _dt.datetime.now(_dt.timezone.utc).isoformat().replace("+00:00", "Z")
        if self.log_format == "json":
            record: Dict[str, Any] = {"ts": ts, "level": level, "msg": message}
            if fields:
                record.update(fields)
            sys.stdout.write(json.dumps(record, ensure_ascii=False) + "\n")
        else:
            extra = " ".join(f"{k}={v}" for k, v in fields.items()) if fields else ""
            sys.stdout.write(
                f"[{ts}] {level}: {message}{(' ' + extra) if extra else ''}\n"
            )
        sys.stdout.flush()

    # Convenience API
    def debug(self, msg: str, **fields: Any):
        self._emit("DEBUG", msg, **fields)

    def info(self, msg: str, **fields: Any):
        self._emit("INFO", msg, **fields)

    def warn(self, msg: str, **fields: Any):
        self._emit("WARN", msg, **fields)

    def error(self, msg: str, **fields: Any):
        self._emit("ERROR", msg, **fields)


def get_logger(level: str = "INFO", log_format: str = "text") -> SimpleLogger:
    """Module-level helper for quick, default logger (INFO/text)"""
    return SimpleLogger(level=level, log_format=log_format)

"""Logging primitives.

Contract (important for AI agents):

* ALL logs go to **stderr** -- never pollute stdout.
* ``json_lines=True`` switches stderr to one JSON object per line
  (NDJSON) for programmatic monitoring.
* ``log_file`` optionally mirrors every record to a file.
"""
from __future__ import annotations

import json
import sys
import time
from typing import IO, TextIO

_RESET = "\033[0m"
_BOLD = "\033[1m"
_DIM = "\033[2m"
_GREEN = "\033[32m"
_YELLOW = "\033[33m"
_RED = "\033[31m"
_CYAN = "\033[36m"


class Logger:
    """Tiny leveled logger writing to stderr with optional color/NDJSON."""

    def __init__(
        self,
        *,
        quiet: bool = False,
        colors: bool | None = None,
        json_lines: bool = False,
        log_file: str | None = None,
        stream: TextIO | None = None,
    ) -> None:
        self.quiet = quiet
        self.json_lines = json_lines
        self.stream: IO = stream or sys.stderr
        if colors is None:
            colors = hasattr(self.stream, "isatty") and self.stream.isatty()
        self.colors = colors and not json_lines
        self.log_file = open(log_file, "a", encoding="utf-8") if log_file else None

    # ----------------------------------------------------------------- core
    def _emit(self, level: str, msg: str) -> None:
        if self.quiet and level not in ("error", "warn"):
            return
        ts = time.strftime("%H:%M:%S")
        if self.log_file:
            self.log_file.write(f"{ts} {level.upper():5} {msg}\n")
            self.log_file.flush()
        if self.json_lines:
            record = {"ts": ts, "level": level, "msg": msg}
            self.stream.write(json.dumps(record, ensure_ascii=False) + "\n")
        elif level == "raw":
            self.stream.write(msg + "\n")
        else:
            color, glyph = {
                "info": ("", "  "),
                "debug": (_DIM, "  "),
                "warn": (_YELLOW, "! "),
                "error": (_RED, "x "),
                "success": (_GREEN, "+ "),
            }.get(level, ("", "  "))
            if self.colors and color:
                self.stream.write(f"{ts} {_DIM}|{_RESET} {color}{glyph}{msg}{_RESET}\n")
            else:
                self.stream.write(f"{ts} | {glyph}{msg}\n")
        self.stream.flush()

    # ----------------------------------------------------------------- API
    def info(self, msg: str) -> None:
        self._emit("info", msg)

    def success(self, msg: str) -> None:
        self._emit("success", msg)

    def warn(self, msg: str) -> None:
        self._emit("warn", msg)

    def error(self, msg: str) -> None:
        self._emit("error", msg)

    def debug(self, msg: str) -> None:
        self._emit("debug", msg)

    def raw(self, msg: str) -> None:
        """Unformatted line (used for result tables), honors quiet=False only."""
        self._emit("raw", msg)

    def stage(self, name: str, detail: str = "") -> None:
        """Loud stage banner so humans always know where the pipeline is."""
        if self.quiet:
            return
        suffix = f"  {_DIM}{detail}{_RESET}" if (detail and self.colors) else (f"  {detail}" if detail else "")
        if self.colors:
            self.stream.write(f"\n{_BOLD}{_CYAN}== {name} =={_RESET}{suffix}\n")
        else:
            self.stream.write(f"\n== {name} == {detail}\n" if detail else f"\n== {name} ==\n")
        self.stream.flush()

    def close(self) -> None:
        if self.log_file:
            try:
                self.log_file.close()
            except Exception:
                pass
            self.log_file = None

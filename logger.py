# logger.py
"""Project-wide logging helpers.

Milestone 1 (doc/issues.md Abschnitt 5): Performance-Optimierung nach Profiling-Analyse
→ HighPerformanceLogHandler (RAM-Pufferung) reduziert I/O-Overhead bei vielen Log-Einträgen.
"""

from __future__ import annotations

import atexit
import logging
import os
import threading
from pathlib import Path
from typing import BinaryIO, Literal

from config import CONFIG_MODEL, SimulationConfig


# Logger level types
LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]


class HighPerformanceLogHandler(logging.Handler):
    """Buffered file logger.

    Writes log lines into an in-memory byte buffer and flushes them to disk when:
    - buffer size exceeds `max_bytes`, or
    - `flush()` / `close()` is called.

    Rationale: Avoid per-record syscalls for very chatty simulations.
    """

    def __init__(
        self,
        log_file: str | os.PathLike[str],
        *,
        file_mode: Literal["w", "a"] = "w",
        max_bytes: int = 50 * 1024 * 1024,
    ) -> None:
        super().__init__()
        if max_bytes <= 0:
            raise ValueError("max_bytes must be > 0")

        self.log_file = str(log_file)
        self.file_mode = file_mode
        self.max_bytes = int(max_bytes)
        self._buffer = bytearray()
        self._lock = threading.RLock()
        self.flush_count = 0
        self._closed = False

        # Open eagerly so the file exists immediately and we can validate paths.
        mode = "wb" if file_mode == "w" else "ab"
        self._stream: BinaryIO = open(self.log_file, mode)

    @property
    def buffered_bytes(self) -> int:
        return len(self._buffer)

    def emit(self, record: logging.LogRecord) -> None:
        try:
            msg = self.format(record)
        except Exception as exc:  # pragma: no cover - format errors are exceptional
            raise RuntimeError("Failed to format log record") from exc

        line = (msg + "\n").encode("utf-8", errors="replace")

        with self._lock:
            # Large single record: flush existing buffer and write directly.
            if len(line) >= self.max_bytes:
                self._flush_unlocked()
                self._stream.write(line)
                self._stream.flush()
                self.flush_count += 1
                return

            self._buffer.extend(line)
            if len(self._buffer) >= self.max_bytes:
                self._flush_unlocked()

    def _flush_unlocked(self) -> None:
        if not self._buffer:
            return
        self._stream.write(self._buffer)
        self._stream.flush()
        self.flush_count += 1
        self._buffer.clear()

    def flush(self) -> None:
        with self._lock:
            self._flush_unlocked()

    def close(self) -> None:
        with self._lock:
            # Idempotent close: pytest (and atexit) may call close multiple times.
            if self._closed:
                return
            self._flush_unlocked()
            self._stream.close()
            self._closed = True
            super().close()


def setup_logger(
    *,
    level: str | None = None,
    log_file: str | None = None,
    log_format: str | None = None,
    file_mode: Literal["w", "a"] = "w",
    config: SimulationConfig | None = None,
    use_high_performance_logging: bool | None = None,
    high_performance_log_buffer_mb: int | None = None,
) -> logging.Logger:
    """Configure and return a logger instance based on configuration parameters."""

    cfg = config or CONFIG_MODEL

    # Get configuration from CONFIG with defaults
    config_level = (level or cfg.logging_level).upper()
    config_file = log_file or cfg.log_file
    config_format = log_format or cfg.log_format

    # Ensure the log directory exists (fresh checkouts often miss /output).
    log_path = Path(config_file)
    if log_path.parent and str(log_path.parent) != ".":
        log_path.parent.mkdir(parents=True, exist_ok=True)

    # Convert string level to logging constant
    level_map: dict[str, int] = {
        "DEBUG": logging.DEBUG,
        "INFO": logging.INFO,
        "WARNING": logging.WARNING,
        "ERROR": logging.ERROR,
        "CRITICAL": logging.CRITICAL,
    }
    numeric_level = level_map.get(config_level, logging.DEBUG)

    enable_hp = (
        bool(cfg.use_high_performance_logging)
        if use_high_performance_logging is None
        else bool(use_high_performance_logging)
    )
    buffer_mb = (
        int(cfg.high_performance_log_buffer_mb)
        if high_performance_log_buffer_mb is None
        else int(high_performance_log_buffer_mb)
    )
    max_bytes = max(1, buffer_mb) * 1024 * 1024

    logger = logging.getLogger()  # root logger
    logger.setLevel(numeric_level)

    # Remove existing handlers to avoid duplicate logging when setup_logger is called multiple times.
    for handler in list(logger.handlers):
        logger.removeHandler(handler)
        handler.close()

    formatter = logging.Formatter(config_format)

    if enable_hp:
        handler: logging.Handler = HighPerformanceLogHandler(
            config_file,
            file_mode=file_mode,
            max_bytes=max_bytes,
        )
        handler.setFormatter(formatter)
        handler.setLevel(numeric_level)
        logger.addHandler(handler)
        atexit.register(handler.close)
    else:
        fh = logging.FileHandler(config_file, mode=file_mode, encoding="utf-8")
        fh.setFormatter(formatter)
        fh.setLevel(numeric_level)
        logger.addHandler(fh)
        atexit.register(fh.close)

    return logger


def log(message: str, level: LogLevel = "DEBUG") -> None:
    """Log a message at the specified level."""
    match level.upper():
        case "INFO":
            logging.info(message)
        case "WARNING":
            logging.warning(message)
        case "ERROR":
            logging.error(message)
        case "CRITICAL":
            logging.critical(message)
        case _:
            logging.debug(message)

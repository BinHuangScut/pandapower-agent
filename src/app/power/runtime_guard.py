from __future__ import annotations

import io
import logging
import warnings
from contextlib import contextmanager, redirect_stderr, redirect_stdout
from dataclasses import dataclass, field
from typing import Iterator


@dataclass(slots=True)
class SuppressedRuntimeOutput:
    warning_messages: list[str] = field(default_factory=list)
    stdout: str = ""
    stderr: str = ""


def _trim_text(value: str, limit: int = 400) -> str:
    text = value.strip()
    if len(text) <= limit:
        return text
    return f"{text[: limit - 3]}..."


def suppressed_runtime_metadata(captured: SuppressedRuntimeOutput) -> dict[str, object]:
    meta: dict[str, object] = {}
    if captured.warning_messages:
        meta["warning_count"] = len(captured.warning_messages)
        meta["warning_preview"] = captured.warning_messages[:3]
    if captured.stdout.strip():
        meta["stdout_preview"] = _trim_text(captured.stdout)
    if captured.stderr.strip():
        meta["stderr_preview"] = _trim_text(captured.stderr)
    return meta


def _iter_exception_chain(exc: BaseException) -> Iterator[BaseException]:
    current: BaseException | None = exc
    seen: set[int] = set()
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        yield current
        current = current.__cause__ or current.__context__


def is_pandapower_related_exception(exc: BaseException) -> bool:
    for item in _iter_exception_chain(exc):
        module = str(getattr(item.__class__, "__module__", "")).lower()
        if "pandapower" in module:
            return True

        tb = item.__traceback__
        while tb is not None:
            filename = str(tb.tb_frame.f_code.co_filename).lower()
            if "pandapower" in filename:
                return True
            tb = tb.tb_next

        if "pandapower" in str(item).lower():
            return True
    return False


@contextmanager
def silence_library_output() -> Iterator[SuppressedRuntimeOutput]:
    captured = SuppressedRuntimeOutput()
    loggers = ["pandapower", "numba"]
    logger_states: list[tuple[logging.Logger, int, bool]] = []
    for name in loggers:
        logger = logging.getLogger(name)
        logger_states.append((logger, logger.level, logger.propagate))
        logger.setLevel(logging.CRITICAL + 1)
        logger.propagate = False

    stdout_buffer = io.StringIO()
    stderr_buffer = io.StringIO()
    with warnings.catch_warnings(record=True) as warning_records:
        warnings.simplefilter("always")
        try:
            with redirect_stdout(stdout_buffer), redirect_stderr(stderr_buffer):
                yield captured
        finally:
            for logger, level, propagate in logger_states:
                logger.setLevel(level)
                logger.propagate = propagate
            captured.warning_messages = [str(w.message) for w in warning_records]
            captured.stdout = stdout_buffer.getvalue()
            captured.stderr = stderr_buffer.getvalue()

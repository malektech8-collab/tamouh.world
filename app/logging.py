"""
Loguru logging configuration for the AI Resume SaaS Engine.

Call configure_logging(settings) once at application startup (app/main.py).
Afterwards, import logger from loguru anywhere in the codebase.

Log format:
  - Console: human-readable coloured text (development)
  - File:    newline-delimited JSON with structured fields (all environments)

Usage:
    from loguru import logger

    logger.info("Job started", job_id=job_id, user_id=user_id)
    logger.bind(trace_id=trace_id).warning("LLM retry", attempt=n)
"""

import sys
from pathlib import Path
from loguru import logger


def configure_logging(settings) -> None:
    """
    Configure loguru sinks based on application settings.

    Removes the default loguru handler and installs:
    - A console sink (coloured text, level INFO or from settings)
    - A rotating file sink (JSON, 10 MB / file, 14 days retention)

    Args:
        settings: The pydantic Settings instance from app.config.
    """
    # Remove loguru's default stderr handler
    logger.remove()

    log_level = getattr(settings, "LOG_LEVEL", "INFO").upper()
    log_dir = Path(getattr(settings, "LOG_DIR", "logs"))
    log_format = getattr(settings, "LOG_FORMAT", "json").lower()

    # ── Console sink ────────────────────────────────────────────────────────
    if log_format == "text":
        console_fmt = (
            "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>{name}</cyan>:<cyan>{line}</cyan> — "
            "<level>{message}</level>"
            "{extra}"
        )
    else:
        console_fmt = (
            "{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | "
            "{name}:{line} — {message} | {extra}"
        )

    logger.add(
        sys.stderr,
        level=log_level,
        format=console_fmt,
        colorize=(log_format == "text"),
        backtrace=True,
        diagnose=False,  # Disable variable values in tracebacks (security)
    )

    # ── File sink (JSON) ─────────────────────────────────────────────────────
    # serialize=True tells loguru to produce newline-delimited JSON automatically.
    # This avoids a bug where a format-callable returning JSON strings with { }
    # causes loguru to interpret those braces as str.format_map placeholders.
    # All fields bound via logger.bind() (trace_id, job_id, …) appear under
    # the "record.extra" key in loguru's JSON envelope.
    log_dir.mkdir(parents=True, exist_ok=True)

    logger.add(
        log_dir / "app_{time:YYYY-MM-DD}.log",
        level=log_level,
        serialize=True,     # loguru handles JSON serialisation — safe, no format_map issues
        rotation="10 MB",
        retention="14 days",
        compression="gz",
        backtrace=True,
        diagnose=False,
        enqueue=True,       # Non-blocking writes (important for async routes)
    )

    logger.info(
        "Logging configured",
        level=log_level,
        log_dir=str(log_dir),
        format=log_format,
    )

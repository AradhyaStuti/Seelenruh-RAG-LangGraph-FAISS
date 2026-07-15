"""Structured logging: human-readable in dev, JSON in prod. Sentry optional (set SENTRY_DSN)."""
import logging
import sys

from config import SEELENRUH_ENV, LOG_LEVEL, SENTRY_DSN

_IS_PROD = SEELENRUH_ENV == "prod"

try:
    import structlog

    def _configure_structlog() -> None:
        shared_processors = [
            structlog.contextvars.merge_contextvars,
            structlog.stdlib.add_log_level,
            structlog.stdlib.add_logger_name,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
        ]
        renderer = (
            structlog.processors.JSONRenderer()
            if _IS_PROD
            else structlog.dev.ConsoleRenderer(colors=True)
        )
        structlog.configure(
            processors=[
                *shared_processors,
                structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
            ],
            wrapper_class=structlog.stdlib.BoundLogger,
            context_class=dict,
            logger_factory=structlog.stdlib.LoggerFactory(),
            cache_logger_on_first_use=True,
        )
        formatter = structlog.stdlib.ProcessorFormatter(
            processor=renderer,
            foreign_pre_chain=shared_processors,
        )
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(formatter)
        root = logging.getLogger()
        root.handlers.clear()
        root.addHandler(handler)
        root.setLevel(getattr(logging, LOG_LEVEL.upper(), logging.INFO))

    _configure_structlog()

    def get_logger(name: str):
        return structlog.get_logger(name)

    _STRUCTLOG = True

except ImportError:
    # structlog not installed — fall back to stdlib logging with a simple format
    logging.basicConfig(
        stream=sys.stdout,
        level=getattr(logging, LOG_LEVEL.upper(), logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    def get_logger(name: str):
        return logging.getLogger(name)

    _STRUCTLOG = False

# Sentry integration (optional)
if SENTRY_DSN:
    try:
        import sentry_sdk
        from sentry_sdk.integrations.fastapi import FastApiIntegration
        from sentry_sdk.integrations.starlette import StarletteIntegration

        sentry_sdk.init(
            dsn=SENTRY_DSN,
            integrations=[StarletteIntegration(), FastApiIntegration()],
            traces_sample_rate=0.05,
            environment=SEELENRUH_ENV,
            send_default_pii=False,
        )
        _log = get_logger("sentry")
        _log.info("Sentry initialised", environment=SEELENRUH_ENV)
    except ImportError:
        logging.getLogger("logger").warning(
            "SENTRY_DSN set but sentry-sdk not installed — pip install sentry-sdk"
        )

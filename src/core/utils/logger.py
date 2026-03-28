import sys
import logging
from qgis.core import Qgis, QgsMessageLog

PLUGIN_LOG_LABEL = "RemoteDB"


class QGISLogHandler(logging.Handler):
    def emit(self, record):
        try:
            msg = self.format(record)
            level = record.levelno
            qgis_level = (
                Qgis.MessageLevel.Critical
                if level >= logging.ERROR
                else Qgis.MessageLevel.Warning if level >= logging.WARNING else Qgis.MessageLevel.Info
            )
            QgsMessageLog.logMessage(msg, PLUGIN_LOG_LABEL, qgis_level)
        except Exception:
            self.handleError(record)


def get_plugin_logger(name="qgis.remote_db_plugin", level=logging.DEBUG):
    logger = logging.getLogger(name)
    if not logger.hasHandlers():
        logger.setLevel(level)

        # StreamHandler for Python Console (only if sys.stderr is available)
        try:
            console_handler = logging.StreamHandler(sys.stderr)
            console_formatter = logging.Formatter(
                "%(name)s - %(levelname)s - %(message)s"
            )
            console_handler.setFormatter(console_formatter)
            logger.addHandler(console_handler)
        except Exception as e:
            # Fails silently if sys.stderr is unavailable
            print(f"Failed to add console handler: {e}")

        # QGIS Message Log Handler
        qgis_handler = QGISLogHandler()
        qgis_formatter = logging.Formatter("%(levelname)s - %(message)s")
        qgis_handler.setFormatter(qgis_formatter)
        logger.addHandler(qgis_handler)

    return logger


PLUGIN_LOGGER = get_plugin_logger("qgis.remote_db_plugin", level=logging.INFO)


class _MessagePrefixFilter(logging.Filter):
    """Prepends a fixed prefix to every log record message."""

    def __init__(self, prefix):
        super().__init__()
        self._prefix = prefix

    def filter(self, record):
        record.msg = f"{self._prefix} {record.getMessage()}"
        record.args = ()
        return True


def get_sshtunnel_logger(base_logger):
    """Return a concrete logger compatible with sshtunnel internals."""
    logger = logging.getLogger("qgis.remote_db_plugin.sshtunnel")
    logger.setLevel(base_logger.level)
    logger.propagate = False

    if not logger.handlers:
        for handler in base_logger.handlers:
            logger.addHandler(handler)

    if not any(isinstance(f, _MessagePrefixFilter) for f in logger.filters):
        logger.addFilter(_MessagePrefixFilter("[sshtunnel.py]"))

    return logger


SSHTUNNEL_LOGGER = get_sshtunnel_logger(PLUGIN_LOGGER)

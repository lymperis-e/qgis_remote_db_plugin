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
                Qgis.Critical
                if level >= logging.ERROR
                else Qgis.Warning if level >= logging.WARNING else Qgis.Info
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

import threading

from qgis.PyQt.QtCore import QObject, QTimer, pyqtSignal

CONNECT_TIMEOUT_SECONDS = 10


class ConnectionOperationRunner(QObject):
    """Runs connect/disconnect operations in background threads with timeout control."""

    operationFinished = pyqtSignal(str, bool, str)

    def __init__(self, connection, parent=None):
        super().__init__(parent)
        self.connection = connection

        self._state_lock = threading.Lock()
        self._active_operation = None
        self._active_operation_id = 0

        self._watchdog = QTimer(self)
        self._watchdog.setSingleShot(True)
        self._watchdog.timeout.connect(self._on_watchdog_timeout)

    def has_active_operation(self):
        with self._state_lock:
            return self._active_operation is not None

    def start_connect(self):
        operation_id = self._begin_operation("connect")
        if operation_id is None:
            return False

        # Extra safety net in case worker completion is delayed/lost.
        self._watchdog.start((CONNECT_TIMEOUT_SECONDS + 1) * 1000)

        threading.Thread(
            target=self._run_connect_operation,
            args=(operation_id,),
            daemon=True,
        ).start()
        return True

    def start_disconnect(self):
        operation_id = self._begin_operation("disconnect")
        if operation_id is None:
            return False

        self._watchdog.stop()
        threading.Thread(
            target=self._run_disconnect_operation,
            args=(operation_id,),
            daemon=True,
        ).start()
        return True

    def _begin_operation(self, operation):
        with self._state_lock:
            if self._active_operation is not None:
                return None

            self._active_operation = operation
            self._active_operation_id += 1
            return self._active_operation_id

    def _finish_operation_if_current(self, operation_id):
        with self._state_lock:
            if operation_id != self._active_operation_id:
                return None

            operation = self._active_operation
            self._active_operation = None
            return operation

    def _run_connect_operation(self, operation_id):
        try:
            self._connect_with_timeout()
            self._emit_result(operation_id, True, "")
        except Exception as exc:
            self._emit_result(operation_id, False, str(exc))

    def _run_disconnect_operation(self, operation_id):
        try:
            self.connection.disconnect()
            self._emit_result(operation_id, True, "")
        except Exception as exc:
            self._emit_result(operation_id, False, str(exc))

    def _connect_with_timeout(self):
        connect_error = {"exception": None}

        def _connect_target():
            try:
                self.connection.connect()
            except Exception as exc:
                connect_error["exception"] = exc

        connect_thread = threading.Thread(target=_connect_target, daemon=True)
        connect_thread.start()
        connect_thread.join(timeout=CONNECT_TIMEOUT_SECONDS)

        if connect_thread.is_alive():
            # If connect eventually completes, ensure we do not keep a stale tunnel.
            def _cleanup_late_connect():
                connect_thread.join()
                try:
                    if self.connection.is_connected:
                        self.connection.disconnect()
                except Exception:
                    pass

            threading.Thread(target=_cleanup_late_connect, daemon=True).start()
            raise TimeoutError(
                f"Connection establishment timed out after {CONNECT_TIMEOUT_SECONDS} seconds"
            )

        if connect_error["exception"] is not None:
            raise connect_error["exception"]

    def _emit_result(self, operation_id, success, message):
        operation = self._finish_operation_if_current(operation_id)
        if operation is None:
            return

        self._watchdog.stop()
        self.operationFinished.emit(operation, success, message)

    def _on_watchdog_timeout(self):
        with self._state_lock:
            if self._active_operation != "connect":
                return
            operation_id = self._active_operation_id

        operation = self._finish_operation_if_current(operation_id)
        if operation is None:
            return

        self.operationFinished.emit(
            "connect",
            False,
            f"Connection establishment timed out after {CONNECT_TIMEOUT_SECONDS} seconds",
        )

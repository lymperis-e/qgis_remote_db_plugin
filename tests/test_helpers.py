import sys
import time
import types
from enum import Flag
from pathlib import Path


class StubForwarder:
    """Simple forwarder test double used by Connection tests."""

    fail_next_start = False
    start_delay_seconds = 0
    instances = []

    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs
        self.started = False
        self.stopped = False
        StubForwarder.instances.append(self)

    def start(self):
        if StubForwarder.start_delay_seconds > 0:
            time.sleep(StubForwarder.start_delay_seconds)

        if StubForwarder.fail_next_start:
            StubForwarder.fail_next_start = False
            raise RuntimeError("start failed")
        self.started = True

    def stop(self):
        self.stopped = True

    @classmethod
    def reset(cls):
        cls.fail_next_start = False
        cls.start_delay_seconds = 0
        cls.instances = []


class DummyQMessageBox:
    class StandardButton(Flag):
        Yes = 1
        No = 0

    @staticmethod
    def question(*args, **kwargs):
        return DummyQMessageBox.No


def install_qgis_stub():
    """Install a minimal qgis module tree expected by dependency checks."""

    if "qgis" in sys.modules:
        return

    qgis = types.ModuleType("qgis")
    pyqt = types.ModuleType("qgis.PyQt")
    qtwidgets = types.ModuleType("qgis.PyQt.QtWidgets")
    core = types.ModuleType("qgis.core")

    class Qgis:
        Info = 0
        Warning = 1
        Critical = 2

    class QgsMessageLog:
        @staticmethod
        def logMessage(*args, **kwargs):
            return None

    qtwidgets.QMessageBox = DummyQMessageBox
    core.Qgis = Qgis
    core.QgsMessageLog = QgsMessageLog
    pyqt.QtWidgets = qtwidgets
    qgis.PyQt = pyqt
    qgis.core = core

    sys.modules["qgis"] = qgis
    sys.modules["qgis.core"] = core
    sys.modules["qgis.PyQt"] = pyqt
    sys.modules["qgis.PyQt.QtWidgets"] = qtwidgets


def install_sshtunnel_stub():
    """Install a module that provides SSHTunnelForwarder for src.core.Connection."""

    module_name = "src.core.sshtunnel.sshtunnel"
    module = types.ModuleType(module_name)
    module.SSHTunnelForwarder = StubForwarder
    sys.modules[module_name] = module


def install_sshconf_stub(read_ssh_config_impl=None):
    """Install a stub sshconf module used by src.core.utils.ssh_config."""

    module = types.ModuleType("sshconf")

    def _default_reader(path):
        class ParsedConfig:
            def hosts(self):
                return []

            def host(self, host_name):
                return {}

        return ParsedConfig()

    module.read_ssh_config = read_ssh_config_impl or _default_reader
    sys.modules["sshconf"] = module


def ensure_project_root_on_path():
    """Make sure tests can import the src package when discovered from tests/."""

    root = str(Path(__file__).resolve().parent.parent)
    if root not in sys.path:
        sys.path.insert(0, root)

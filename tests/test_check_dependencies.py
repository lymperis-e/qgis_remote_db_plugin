import importlib
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from test_helpers import ensure_project_root_on_path, install_qgis_stub


ensure_project_root_on_path()
install_qgis_stub()

check_deps_module = importlib.import_module("src.core.dependencies.check_dependencies")


class TestCheckDependencies(unittest.TestCase):
    def test_version_satisfies_supports_comparators(self):
        self.assertTrue(check_deps_module._version_satisfies("2.13.0", ">=2.12.0"))
        self.assertTrue(check_deps_module._version_satisfies("2.13.0", "2.13.0"))
        self.assertFalse(check_deps_module._version_satisfies("2.11.0", ">=2.12.0"))

    def test_check_skips_prompt_when_requirements_satisfied(self):
        with patch.object(
            check_deps_module.importlib, "import_module", return_value=object()
        ), patch.object(
            check_deps_module.importlib_metadata, "version", return_value="2.13.0"
        ), patch.object(
            check_deps_module.QMessageBox,
            "question",
            return_value=check_deps_module.QMessageBox.No,
        ) as question_mock:
            check_deps_module.check([("paramiko", ">=2.12.0")])

        question_mock.assert_not_called()

    def test_check_prompts_when_installed_version_is_too_low(self):
        with patch.object(
            check_deps_module.importlib, "import_module", return_value=object()
        ), patch.object(
            check_deps_module.importlib_metadata, "version", return_value="2.10.0"
        ), patch.object(
            check_deps_module.QMessageBox,
            "question",
            return_value=check_deps_module.QMessageBox.No,
        ) as question_mock:
            check_deps_module.check([("paramiko", ">=2.12.0")])

        question_mock.assert_called_once()

    def test_check_installs_with_version_spec_when_user_accepts(self):
        with patch.object(
            check_deps_module.importlib, "import_module", side_effect=ImportError()
        ), patch.object(
            check_deps_module.QMessageBox,
            "question",
            return_value=check_deps_module.QMessageBox.Yes,
        ), patch.object(
            check_deps_module, "find_pip_executable", return_value="pip"
        ), patch.object(
            check_deps_module.subprocess,
            "run",
            return_value=SimpleNamespace(stdout="installed"),
        ) as run_mock:
            check_deps_module.check([("paramiko", ">=2.12.0")])

        run_mock.assert_called_once_with(
            ["pip", "install", "paramiko>=2.12.0"],
            capture_output=True,
            text=True,
            check=True,
        )


if __name__ == "__main__":
    unittest.main()

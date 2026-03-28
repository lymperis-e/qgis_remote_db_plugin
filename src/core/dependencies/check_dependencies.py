from typing import List, Optional, Tuple, Union
import os
import sys
import importlib
from ..utils.logger import PLUGIN_LOGGER
from qgis.PyQt.QtWidgets import QMessageBox
import subprocess

try:
    from importlib import metadata as importlib_metadata
except ImportError:  # pragma: no cover
    import importlib_metadata  # type: ignore

try:
    from packaging.version import Version
except Exception:  # pragma: no cover
    Version = None


Requirement = Union[str, Tuple[str, str], dict]


def _parse_requirement(requirement: Requirement) -> Tuple[str, Optional[str]]:
    if isinstance(requirement, str):
        return requirement, None

    if isinstance(requirement, (tuple, list)):
        if len(requirement) != 2:
            raise ValueError(
                "Tuple/list dependency requirements must have exactly 2 values: (name, version_spec)"
            )
        return str(requirement[0]), str(requirement[1])

    if isinstance(requirement, dict):
        name = requirement.get("name") or requirement.get("package")
        version_spec = requirement.get("version") or requirement.get("version_spec")

        if not name:
            raise ValueError(
                "Dictionary dependency requirements must include a 'name' or 'package' key"
            )

        return str(name), str(version_spec) if version_spec else None

    raise TypeError(
        "Unsupported dependency requirement type. Use str, (name, version_spec), or dict."
    )


def _normalize_version_spec(version_spec: Optional[str]) -> Optional[str]:
    if not version_spec:
        return None

    value = str(version_spec).strip()
    if not value:
        return None

    operators = ("==", ">=", "<=", "!=", ">", "<")
    if value.startswith(operators):
        return value

    return f"=={value}"


def _version_satisfies(installed: str, version_spec: str) -> bool:
    normalized = _normalize_version_spec(version_spec)
    if not normalized:
        return True

    operator = "=="
    required = normalized
    for candidate in ("==", ">=", "<=", "!=", ">", "<"):
        if normalized.startswith(candidate):
            operator = candidate
            required = normalized[len(candidate) :].strip()
            break

    if Version is None:
        if operator == "==":
            return installed == required
        if operator == "!=":
            return installed != required
        return False

    try:
        installed_v = Version(installed)
        required_v = Version(required)
    except Exception:
        if operator == "==":
            return installed == required
        if operator == "!=":
            return installed != required
        return False

    if operator == "==":
        return installed_v == required_v
    if operator == "!=":
        return installed_v != required_v
    if operator == ">=":
        return installed_v >= required_v
    if operator == "<=":
        return installed_v <= required_v
    if operator == ">":
        return installed_v > required_v
    if operator == "<":
        return installed_v < required_v

    return False


def _to_pip_requirement(name: str, version_spec: Optional[str]) -> str:
    normalized = _normalize_version_spec(version_spec)
    if not normalized:
        return name
    return f"{name}{normalized}"


def find_pip_executable():
    """
    Find the pip executable path based on the current Python environment.
    """
    candidate_filenames = ["pip", "pip3"]
    if sys.platform == "win32" or os.name == "nt":
        # On Windows, we might have pip.exe or pip3.exe
        candidate_filenames = [f"{filename}.exe" for filename in candidate_filenames]

    # Determine the pip directory based on the current Python environment
    pip_dir = (
        os.path.join(sys.prefix, "Scripts")
        if sys.platform == "win32"
        else os.path.join(sys.prefix, "bin")
    )

    # Check each candidate filename
    tried: List[str] = []
    for filename in candidate_filenames:
        path = os.path.join(pip_dir, filename)
        if os.path.isfile(path):
            return path

        tried.append(path)

    raise FileNotFoundError(
        "pip executable not found in the current Python environment. Tried: \n"
        + ", \n".join(tried)
    )


def check(required_packages: List[Requirement]):
    """
    Check and optionally install missing dependencies.

    Supported requirement formats:
    - "paramiko"
    - ("paramiko", ">=2.12")
    - {"name": "paramiko", "version": "2.12.0"}
    """
    missing_requirements = []
    for requirement in required_packages:
        package, version_spec = _parse_requirement(requirement)
        pip_requirement = _to_pip_requirement(package, version_spec)

        try:
            importlib.import_module(package)
        except ImportError:
            missing_requirements.append((pip_requirement, pip_requirement))
            continue

        if version_spec:
            try:
                installed_version = importlib_metadata.version(package)
            except importlib_metadata.PackageNotFoundError:
                missing_requirements.append((pip_requirement, pip_requirement))
                continue

            if not _version_satisfies(installed_version, version_spec):
                display_requirement = (
                    f"{pip_requirement} (installed: {installed_version})"
                )
                missing_requirements.append((pip_requirement, display_requirement))

    # If any required packages are missing, prompt user to install them
    if missing_requirements:
        message = "The following Python packages are required to use this plugin:\n\n"
        message += "\n".join([item[1] for item in missing_requirements])
        message += "\n\nWould you like to install them now?"

        reply = QMessageBox.question(
            None,
            "Missing Dependencies",
            message,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if reply == QMessageBox.StandardButton.No:
            return

        for pip_requirement, _display in missing_requirements:
            # Use subprocess to capture output
            try:
                pip_path = find_pip_executable()
                PLUGIN_LOGGER.info(f"Installing {pip_requirement} using {pip_path}...")
                result = subprocess.run(
                    [pip_path, "install", pip_requirement],
                    capture_output=True,
                    text=True,
                    check=True,
                )
                PLUGIN_LOGGER.info(f"Successfully installed {pip_requirement}")
                if result.stdout:
                    PLUGIN_LOGGER.debug(result.stdout)
            except subprocess.CalledProcessError as e:
                PLUGIN_LOGGER.error(f"Failed to install {pip_requirement}")
                PLUGIN_LOGGER.error(e.stderr)

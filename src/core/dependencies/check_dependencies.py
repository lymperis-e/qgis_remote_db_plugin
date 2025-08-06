from typing import List
import os, sys, importlib
from qgis.PyQt.QtWidgets import QMessageBox
import subprocess


def find_pip_executable():
    """
    Find the pip executable path based on the current Python environment.
    """
    candidate_filenames = ["pip", "pip3"]
    if sys.platform == "win32" or os.name == "nt":
        # On Windows, we might have pip.exe or pip3.exe
        candidate_filenames = [f"{filename}.exe" for filename in candidate_filenames]

    # Determine the pip directory based on the current Python environment
    pip_dir = os.path.join(sys.prefix, "Scripts") if sys.platform == "win32" else os.path.join(sys.prefix, "bin")

    # Check each candidate filename
    tried: List[str] = []
    for filename in candidate_filenames:
        path = os.path.join(pip_dir, filename)
        if os.path.isfile(path):
            return path
        
        tried.append(path)
        
    raise FileNotFoundError("pip executable not found in the current Python environment. Tried: \n" + ", \n".join(tried))


def check(required_packages):
    # Check if required packages are installed
    missing_packages = []
    for package in required_packages:
        try:
            importlib.import_module(package)
        except ImportError:
            missing_packages.append(package)

    # If any required packages are missing, prompt user to install them
    if missing_packages:
        message = "The following Python packages are required to use this plugin:\n\n"
        message += "\n".join(missing_packages)
        message += "\n\nWould you like to install them now?"

        reply = QMessageBox.question(
            None,
            "Missing Dependencies",
            message,
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )

        if reply == QMessageBox.No:
            return

        for package in missing_packages:
            # Use subprocess to capture output
            try:
                pip_path = find_pip_executable()
                print(f"Installing {package} using {pip_path}...")
                result = subprocess.run(
                    [pip_path, "install", package],
                    capture_output=True,
                    text=True,
                    check=True
                )
                print(f"Successfully installed {package}")
                print(result.stdout)
            except subprocess.CalledProcessError as e:
                print(f"Failed to install {package}")
                print(e.stderr)

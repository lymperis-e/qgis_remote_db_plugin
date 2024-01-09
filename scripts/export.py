"""
Creates a plugin release .zip, and copies the build over to the QGIS plugins folder.

Copyright (c) Efstathios Lymperis (geo.elymperis@gmail.com)

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
THE SOFTWARE.

"""
import os
import shutil
import zipfile
import subprocess
import sys


def clear_directory(path):
    if os.path.exists(path):
        # Clear the directory if it exists
        for item in os.listdir(path):
            item_path = os.path.join(path, item)
            if os.path.isdir(item_path):
                shutil.rmtree(item_path)
            else:
                os.remove(item_path)


def clear_or_create_directory(path):
    if os.path.exists(path):
        clear_directory(path)
    else:
        # Create the directory if it doesn't exist
        os.makedirs(path)


def copy_files(src_dir, dest_dir, exclude_list):
    clear_or_create_directory(dest_dir)

    for item in os.listdir(src_dir):
        src_item = os.path.join(src_dir, item)
        dest_item = os.path.join(dest_dir, item)

        # Check if the item should be excluded
        if any(exclude_item in src_item for exclude_item in exclude_list):
            continue

        if os.path.isdir(src_item):
            # Recursively copy subdirectories
            shutil.copytree(src_item, dest_item)
        else:
            # Copy individual files
            shutil.copy2(src_item, dest_item)


def create_release(plugin_name, src_dir, dest_dir, exclude_list):
    """
    Creates a plugin release .zip.

    Args:
        plugin_name (str): The name of the plugin.
        src_dir (str): The source directory.
        dest_dir (str): The destination directory.
        exclude_list (list): A list of files to exclude.
    """
    # Create the release directory
    clear_or_create_directory(dest_dir)

    # Copy the files over to the release directory
    copy_files(src_dir, dest_dir, exclude_list)

    # Create the release zip file
    release_dir = os.path.dirname(dest_dir)
    zip_file = os.path.join(release_dir, f"{plugin_name}.zip")
    print(f"Creating release zip file at {zip_file}...")

    with zipfile.ZipFile(zip_file, "w", zipfile.ZIP_DEFLATED) as zip:
        for root, dirs, files in os.walk(dest_dir):
            for file in files:
                zip.write(
                    os.path.join(root, file),
                    os.path.relpath(
                        os.path.join(root, file), os.path.join(dest_dir, "..")
                    ),
                )
    print("Release zip file created successfully.")


def copy_release_to_qgis_plugins(src_dir, dest_dir):
    """
    Copies the release to the QGIS plugins folder.
    """
    print(f"Copying release to {dest_dir}...")

    # Clear the directory if it exists
    if os.path.exists(dest_dir):
        for item in os.listdir(dest_dir):
            item_path = os.path.join(dest_dir, item)
            if os.path.isdir(item_path):
                shutil.rmtree(item_path)
            else:
                os.remove(item_path)
    else:
        # Create the directory if it doesn't exist
        os.makedirs(dest_dir)

    for item in os.listdir(src_dir):
        src_item = os.path.join(src_dir, item)
        dest_item = os.path.join(dest_dir, item)

        if os.path.isdir(src_item):
            # Recursively copy subdirectories
            shutil.copytree(src_item, dest_item)
        else:
            # Copy individual files
            shutil.copy2(src_item, dest_item)
    print("Release copied successfully.")


def get_qgis_plugins_dir() -> str:
    """
    Returns the QGIS plugins directory for the current platform.
    """
    platform = sys.platform
    print(f"Platform: {platform}")

    if platform == "win32":
        qgis_plugins_dir = os.path.join(
            os.environ["USERPROFILE"],
            "AppData",
            "Roaming",
            "QGIS",
            "QGIS3",
            "profiles",
            "default",
            "python",
            "plugins",
        )

    # linux
    elif platform == "linux":
        qgis_plugins_dir = os.path.join(
            os.environ["HOME"],
            ".local",
            "share",
            "QGIS",
            "QGIS3",
            "profiles",
            "default",
            "python",
            "plugins",
        )

    # macos
    elif platform == "darwin":
        qgis_plugins_dir = os.path.join(
            os.environ["HOME"],
            "Library",
            "Application Support",
            "QGIS",
            "QGIS3",
            "profiles",
            "default",
            "python",
            "plugins",
        )

    else:
        raise Exception(f"Unsupported platform: {platform}")

    return qgis_plugins_dir


def main():
    """
    Creates a plugin release .zip, and copies the build over to the QGIS plugins folder.
    """
    plugin_name = "remote_db"
    script_dir = os.path.dirname(os.path.abspath(__file__))
    root_dir = os.path.dirname(script_dir)
    src_dir = os.path.join(root_dir, "src")
    dest_dir = os.path.join(root_dir, "release", plugin_name)
    exclude_list = [
        "Makefile",
        ".git",
        ".vscode",
        "release",
        "scripts",
        "pb_tool.cfg",
        "*.pyc",
        "pylintrc",
        "*.bat",
        ".gitignore",
        ".gitattributes",
        "access_token",
    ]

    print(f"Copying files from {src_dir} to {dest_dir}...")

    create_release(plugin_name, src_dir, dest_dir, exclude_list)

    # Copy the release to the QGIS plugins folder
    qgis_plugins_dir = os.path.join(
        get_qgis_plugins_dir(),
        plugin_name,
    )
    copy_release_to_qgis_plugins(dest_dir, qgis_plugins_dir)

    print("Files copied successfully.")

    # Clear & remove the release directory
    clear_directory(dest_dir)
    os.rmdir(dest_dir)

    # Open the QGIS plugins folder
    subprocess.Popen(f'explorer "{qgis_plugins_dir}"')


if __name__ == "__main__":
    main()

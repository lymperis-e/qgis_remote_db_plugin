import os
import shutil


def clear_or_create_directory(path):
    if os.path.exists(path):
        # Clear the directory if it exists
        for item in os.listdir(path):
            item_path = os.path.join(path, item)
            if os.path.isdir(item_path):
                shutil.rmtree(item_path)
            else:
                os.remove(item_path)
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


if __name__ == "__main__":
    script_dir = os.path.dirname(os.path.abspath(__file__))
    root_dir = os.path.dirname(script_dir)
    src_dir = os.path.join(root_dir, "src")
    dest_dir = os.path.join(root_dir, "release", "remote_db")
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
    ]

    print(f"Copying files from {src_dir} to {dest_dir}...")

    copy_files(src_dir, dest_dir, exclude_list)
    print("Files copied successfully.")

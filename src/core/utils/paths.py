import os

BACKUPS_FOLDERNAME = ".backups"


def unique_path(folder, prefix, suffix):
    """Returns folder/prefix+suffix, or folder/prefix.N+suffix if that already exists."""
    candidate = os.path.join(folder, prefix + suffix)
    counter = 1
    while os.path.exists(candidate):
        candidate = os.path.join(folder, f"{prefix}.{counter}{suffix}")
        counter += 1
    return candidate


def unique_backup_path(settings_folder, prefix, suffix):
    """Like unique_path, inside settings_folder/.backups (created if missing)."""
    backups_folder = os.path.join(settings_folder, BACKUPS_FOLDERNAME)
    os.makedirs(backups_folder, exist_ok=True)
    return unique_path(backups_folder, prefix, suffix)

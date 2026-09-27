import json
import locale
import os
import shutil
import sqlite3

from ..utils.logger import PLUGIN_LOGGER
from ..utils.paths import unique_backup_path

LEGACY_CONNECTIONS_FILENAME = "connections.json"
LEGACY_BACKUP_PREFIX = "connections.old"
LEGACY_BACKUP_SUFFIX = ".json.bk"
UNNAMED_CONNECTION = "Unnamed connection"

# Errors caused by a single bad entry; anything else aborts the whole migration
_ENTRY_ERRORS = (
    TypeError,
    ValueError,
    OverflowError,
    sqlite3.IntegrityError,
    sqlite3.InterfaceError,
)


class LegacyConnectionsFile:
    """
    Backward compatibility with the connections.json format used by older versions.
    """

    def __init__(self, settings_folder):
        self.SETTINGS_FOLDER = settings_folder
        self.PATH = os.path.join(settings_folder, LEGACY_CONNECTIONS_FILENAME)

    def exists(self):
        return os.path.isfile(self.PATH)

    def read_connections(self):
        """
        Returns the connection entries (dicts) of the file.
        Raises if the file cannot be parsed.
        """
        return [entry for entry in self._read_entries() if isinstance(entry, dict)]

    def migrate_to(self, database):
        """
        Imports the file into `database`, then moves it to .backups/connections.old.json.bk.
        The file is only renamed after every imported connection has been committed
        and verified. Never raises.
        """
        if not self.exists():
            return

        PLUGIN_LOGGER.info(
            "Found legacy connections file '%s', migrating it to the connections database.",
            self.PATH,
        )

        try:
            entries = self._read_entries()
        except Exception as e:
            PLUGIN_LOGGER.error(
                "Could not read legacy connections file '%s' (%s). "
                "It was left untouched; fix it and press refresh to retry.",
                self.PATH,
                e,
            )
            return

        stored_names = []
        failed = 0
        try:
            with database.transaction() as db:
                for index, entry in enumerate(entries):
                    try:
                        stored_names.append(self._import_entry(database, db, entry))
                    except _ENTRY_ERRORS as e:
                        failed += 1
                        PLUGIN_LOGGER.error(
                            "Legacy connection #%d could not be migrated: %s",
                            index + 1,
                            e,
                        )
            missing = [name for name in stored_names if not database.contains(name)]
        except Exception as e:
            PLUGIN_LOGGER.error(
                "Migration of '%s' failed (%s). The file was left untouched.",
                self.PATH,
                e,
            )
            return

        if missing:
            PLUGIN_LOGGER.error(
                "Migration could not be verified for connections %s. "
                "'%s' was left untouched.",
                missing,
                self.PATH,
            )
            return

        if failed and not stored_names:
            PLUGIN_LOGGER.error(
                "None of the connections in '%s' could be migrated. "
                "The file was left untouched.",
                self.PATH,
            )
            return

        PLUGIN_LOGGER.info(
            "Migrated %d connection(s) to '%s'.",
            len(stored_names),
            database.DATABASE_FILE,
        )
        if failed:
            PLUGIN_LOGGER.warning(
                "%d invalid legacy connection(s) were skipped; they are still "
                "available in the backup file.",
                failed,
            )
        self._backup()

    # ---------------------------------------------------------------- private

    @staticmethod
    def _import_entry(database, db, entry):
        if not isinstance(entry, dict):
            raise TypeError(f"expected an object, got {type(entry).__name__}")
        if entry.get("name") in (None, ""):
            entry = {**entry, "name": UNNAMED_CONNECTION}
        return database.import_parameters(db, entry)

    @staticmethod
    def _decode(raw):
        encodings = ["utf-8-sig"]
        try:
            encodings.append(locale.getpreferredencoding(False))
        except Exception:
            pass
        encodings.append("latin-1")  # never fails, last resort
        for encoding in encodings:
            try:
                return raw.decode(encoding)
            except (UnicodeDecodeError, LookupError):
                continue
        return raw.decode("utf-8", errors="replace")

    def _read_entries(self):
        """
        Returns the raw list of entries. Raises if the file cannot be parsed,
        so that it is left untouched.
        """
        with open(self.PATH, "rb") as f:
            text = self._decode(f.read())

        if not text.strip():
            return []

        data = json.loads(text)
        if isinstance(data, dict):
            if "connections" not in data:
                raise ValueError("missing the 'connections' key")
            data = data["connections"]
        if data is None:
            return []
        if not isinstance(data, list):
            raise TypeError(
                f"'connections' should be a list, got {type(data).__name__}"
            )
        return data

    def _backup(self):
        try:
            backup = unique_backup_path(
                self.SETTINGS_FOLDER, LEGACY_BACKUP_PREFIX, LEGACY_BACKUP_SUFFIX
            )
        except OSError as e:
            PLUGIN_LOGGER.warning(
                "Could not create the backups folder (%s). '%s' will be imported "
                "again next time; already imported connections are skipped.",
                e,
                self.PATH,
            )
            return
        try:
            os.rename(self.PATH, backup)
            PLUGIN_LOGGER.info("Legacy connections file was moved to '%s'.", backup)
            return
        except OSError as e:
            PLUGIN_LOGGER.warning(
                "Could not rename legacy connections file to '%s' (%s). "
                "Trying copy & delete instead.",
                backup,
                e,
            )
        try:
            if not os.path.exists(backup):
                shutil.copy2(self.PATH, backup)
            os.remove(self.PATH)
            PLUGIN_LOGGER.info("Legacy connections file was moved to '%s'.", backup)
        except OSError as e:
            PLUGIN_LOGGER.warning(
                "Could not move legacy connections file '%s' (%s). It will be imported "
                "again next time; already imported connections are skipped.",
                self.PATH,
                e,
            )

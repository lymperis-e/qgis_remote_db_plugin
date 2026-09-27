import contextlib
import json
import os
import sqlite3

from ..utils.logger import PLUGIN_LOGGER
from ..utils.paths import unique_backup_path
from .legacy_connections import LegacyConnectionsFile

DATABASE_FILENAME = "connections.db"
CORRUPT_DB_BACKUP_PREFIX = "connections.corrupt"
CORRUPT_DB_BACKUP_SUFFIX = ".db.bk"
SCHEMA_VERSION = 1

_COLUMNS = (
    ("name", "TEXT NOT NULL UNIQUE"),
    ("host", "TEXT"),
    ("ssh_port", "INTEGER"),
    ("username", "TEXT"),
    ("password", "TEXT"),
    ("id_file", "TEXT"),
    ("pkey_password", "TEXT"),
    ("ssh_proxy", "TEXT"),
    ("ssh_proxy_enabled", "INTEGER"),
    ("remote_bind_address", "TEXT"),
    ("remote_port", "INTEGER"),
    ("local_port", "INTEGER"),
)
_COLUMN_NAMES = tuple(column for column, _ in _COLUMNS)
_BOOLEAN_COLUMNS = frozenset({"ssh_proxy_enabled"})
_INTEGER_COLUMNS = frozenset({"ssh_port", "remote_port", "local_port"})
_SQLITE_INT_MIN = -(2**63)
_SQLITE_INT_MAX = 2**63 - 1


class DuplicateNameError(ReferenceError):
    def __init__(self, name):
        super().__init__(
            f"A connection with this name({name}) already exists. Please choose a different one"
        )


def _to_text(value):
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False, default=str)


def _to_int_or_none(value):
    """Return value as an int that fits in SQLite, or None if not possible."""
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, float):
        if not value.is_integer():
            return None
        value = int(value)
    elif isinstance(value, str):
        try:
            value = int(value.strip())
        except ValueError:
            return None
    if isinstance(value, int) and _SQLITE_INT_MIN <= value <= _SQLITE_INT_MAX:
        return value
    return None


def _to_db_value(column, value):
    """Convert a parameter value to something sqlite3 can always bind."""
    if value is None:
        return None
    if column in _BOOLEAN_COLUMNS:
        # Only real bools/ints are coerced, so the truthiness of odd legacy values is kept
        if isinstance(value, (bool, int)) and _to_int_or_none(value) is not None:
            return int(value)
        return _to_text(value)
    if column in _INTEGER_COLUMNS:
        as_int = _to_int_or_none(value)
        if as_int is not None:
            return as_int
        if isinstance(value, float):
            return value
    return _to_text(value)


class SettingsDatabase:
    """
    SQLite storage for connection parameters.
    """

    def __init__(self, settings_folder):
        self.SETTINGS_FOLDER = settings_folder
        self.DATABASE_FILE = os.path.join(settings_folder, DATABASE_FILENAME)
        self.legacy_file = LegacyConnectionsFile(settings_folder)

    # ---------------------------------------------------------------- public

    def initialize(self):
        """
        Ensures the database exists and imports any legacy connections.json.
        Never raises: problems are logged so the plugin can always start.
        """
        try:
            os.makedirs(self.SETTINGS_FOLDER, exist_ok=True)
            self._ensure_schema()
        except Exception as e:
            PLUGIN_LOGGER.error(
                "Could not initialize connections database '%s': %s",
                self.DATABASE_FILE,
                e,
            )
            return False
        self.legacy_file.migrate_to(self)
        return True

    def load_parameters(self):
        """
        Returns the parameters of every stored connection. Never raises; falls back
        to the legacy connections.json (read-only) if the database is unusable.
        """
        try:
            with self._connect() as db:
                rows = db.execute("SELECT * FROM connections ORDER BY id").fetchall()
            return [self._row_to_parameters(row) for row in rows]
        except Exception as e:
            PLUGIN_LOGGER.error("Could not read connections database: %s", e)

        if self.legacy_file.exists():
            try:
                connections = self.legacy_file.read_connections()
                PLUGIN_LOGGER.warning(
                    "Using connections from '%s' instead.", self.legacy_file.PATH
                )
                return connections
            except Exception as e:
                PLUGIN_LOGGER.error("Could not read legacy connections file: %s", e)
        return []

    def insert(self, parameters):
        values, extra = self._to_db_record(parameters)
        try:
            with self._connect() as db, db:
                self._insert(db, values, extra)
        except sqlite3.IntegrityError:
            raise DuplicateNameError(values["name"])

    def update(self, name, parameters):
        """Replaces the connection stored as `name`, inserting it if missing."""
        values, extra = self._to_db_record(parameters)
        assignments = ", ".join(f"{column} = ?" for column in _COLUMN_NAMES)
        try:
            with self._connect() as db, db:
                cursor = db.execute(
                    f"UPDATE connections SET {assignments} WHERE name = ?",
                    [values[column] for column in _COLUMN_NAMES] + [name],
                )
                if cursor.rowcount == 0:
                    self._insert(db, values, extra)
        except sqlite3.IntegrityError:
            raise DuplicateNameError(values["name"])

    def delete(self, name):
        with self._connect() as db, db:
            db.execute("DELETE FROM connections WHERE name = ?", (name,))

    def contains(self, name):
        with self._connect() as db:
            row = db.execute(
                "SELECT 1 FROM connections WHERE name = ?", (name,)
            ).fetchone()
        return row is not None

    @contextlib.contextmanager
    def transaction(self):
        """Yields a connection; commits on success, rolls back on error."""
        with self._connect() as db, db:
            yield db

    def import_parameters(self, db, parameters):
        """
        Inserts `parameters` within transaction `db`. If the name is taken by an
        identical connection it is skipped (makes re-imports idempotent), otherwise a
        numbered suffix is added. Returns the name under which it is stored.
        """
        values, extra = self._to_db_record(parameters)
        base_name = values["name"]

        candidate = base_name
        counter = 1
        while True:
            row = db.execute(
                "SELECT id FROM connections WHERE name = ?", (candidate,)
            ).fetchone()
            if row is None:
                self._insert(db, {**values, "name": candidate}, extra)
                if candidate != base_name:
                    PLUGIN_LOGGER.warning(
                        "Connection '%s' was imported as '%s' "
                        "because that name was already taken.",
                        base_name,
                        candidate,
                    )
                return candidate
            if self._row_matches(db, row["id"], values, extra):
                return candidate
            counter += 1
            candidate = f"{base_name} ({counter})"

    # ---------------------------------------------------------------- schema

    @contextlib.contextmanager
    def _connect(self):
        db = sqlite3.connect(self.DATABASE_FILE, timeout=10)
        try:
            db.row_factory = sqlite3.Row
            yield db
        finally:
            db.close()

    def _create_schema(self):
        columns_sql = ",\n".join(f"{name} {kind}" for name, kind in _COLUMNS)
        with self._connect() as db:
            db.execute(
                "CREATE TABLE IF NOT EXISTS connections (\n"
                "id INTEGER PRIMARY KEY AUTOINCREMENT,\n"
                f"{columns_sql},\n"
                "extra TEXT\n"
                ")"
            )
            version = db.execute("PRAGMA user_version").fetchone()[0]
            if version == 0:
                db.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
            elif version > SCHEMA_VERSION:
                PLUGIN_LOGGER.warning(
                    "Connections database schema version (%s) is newer than "
                    "this plugin supports (%s).",
                    version,
                    SCHEMA_VERSION,
                )

    def _ensure_schema(self):
        try:
            self._create_schema()
        except sqlite3.OperationalError:
            # Locked / unreadable file: not corruption, never move the file aside
            raise
        except sqlite3.DatabaseError as e:
            backup = unique_backup_path(
                self.SETTINGS_FOLDER, CORRUPT_DB_BACKUP_PREFIX, CORRUPT_DB_BACKUP_SUFFIX
            )
            PLUGIN_LOGGER.error(
                "Connections database '%s' is unreadable (%s). "
                "It was moved to '%s' and a new one was created.",
                self.DATABASE_FILE,
                e,
                backup,
            )
            os.rename(self.DATABASE_FILE, backup)
            for sidecar in ("-journal", "-wal", "-shm"):
                if os.path.exists(self.DATABASE_FILE + sidecar):
                    os.rename(self.DATABASE_FILE + sidecar, backup + sidecar)
            self._create_schema()

    # ---------------------------------------------------------------- records

    @staticmethod
    def _to_db_record(parameters):
        values = {
            column: _to_db_value(column, parameters.get(column))
            for column in _COLUMN_NAMES
        }
        if values["name"] is None:
            values["name"] = ""
        extra_params = {k: v for k, v in parameters.items() if k not in _COLUMN_NAMES}
        extra = (
            json.dumps(extra_params, sort_keys=True, ensure_ascii=False, default=str)
            if extra_params
            else None
        )
        return values, extra

    @staticmethod
    def _insert(db, values, extra):
        columns = ", ".join(_COLUMN_NAMES)
        placeholders = ", ".join("?" for _ in range(len(_COLUMN_NAMES) + 1))
        db.execute(
            f"INSERT INTO connections ({columns}, extra) VALUES ({placeholders})",
            [values[column] for column in _COLUMN_NAMES] + [extra],
        )

    @staticmethod
    def _row_matches(db, row_id, values, extra):
        compared = [column for column in _COLUMN_NAMES if column != "name"]
        conditions = " AND ".join(f"{column} IS ?" for column in compared)
        row = db.execute(
            f"SELECT 1 FROM connections WHERE id = ? AND {conditions} AND extra IS ?",
            [row_id] + [values[column] for column in compared] + [extra],
        ).fetchone()
        return row is not None

    @staticmethod
    def _row_to_parameters(row):
        parameters = {}
        if row["extra"]:
            try:
                extra = json.loads(row["extra"])
                if isinstance(extra, dict):
                    parameters.update(extra)
            except ValueError:
                PLUGIN_LOGGER.warning(
                    "Ignoring unreadable extra parameters of connection '%s'.",
                    row["name"],
                )
        for column in _COLUMN_NAMES:
            value = row[column]
            # NULL columns are omitted so Connection falls back to its defaults
            if value is None:
                continue
            if column in _BOOLEAN_COLUMNS and isinstance(value, int):
                value = bool(value)
            parameters[column] = value
        return parameters

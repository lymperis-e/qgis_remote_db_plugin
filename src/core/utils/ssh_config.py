"""
Reads the current user's OpenSSH client config (~/.ssh/config on Linux, macOS and
Windows) and converts its hosts to connection parameters. Standard library only;
nothing in the config (e.g. ProxyCommand, Match exec) is ever executed.
"""

import fnmatch
import getpass
import glob
import os
import re
from dataclasses import dataclass, field

from .logger import PLUGIN_LOGGER

DEFAULT_REMOTE_PORT = 5432
FIRST_LOCAL_PORT = 5433
MAX_INCLUDE_DEPTH = 16  # same limit as OpenSSH
_MULTI_VALUE_KEYWORDS = frozenset({"identityfile", "localforward"})
_LINE_RE = re.compile(r"([^\s=]+)(?:\s*=\s*|\s+)(.*)")
_LOCALHOST_NAMES = frozenset({"localhost", "ip6-localhost"})


@dataclass
class DetectedHost:
    parameters: dict
    warnings: list = field(default_factory=list)
    # Reason why the host cannot be imported, None if it can
    problem: str = None

    @property
    def importable(self):
        return self.problem is None


def ssh_directory():
    # expanduser uses %USERPROFILE% on Windows, which is where Win32-OpenSSH looks
    return os.path.join(os.path.expanduser("~"), ".ssh")


def default_ssh_config_path():
    return os.path.join(ssh_directory(), "config")


def _local_username():
    try:
        return getpass.getuser()
    except Exception:
        return os.environ.get("USERNAME") or os.environ.get("USER") or ""


# ------------------------------------------------------------------ parsing


def _split_args(text):
    """Splits on whitespace, honouring double quotes. Backslashes are literal."""
    args, current, quoted, has_token = [], [], False, False
    for char in text:
        if char == '"':
            quoted = not quoted
            has_token = True
        elif char.isspace() and not quoted:
            if has_token:
                args.append("".join(current))
                current, has_token = [], False
        else:
            current.append(char)
            has_token = True
    if has_token:
        args.append("".join(current))
    return args


def _parse_line(line):
    line = line.strip()
    if not line or line.startswith("#"):
        return None
    match = _LINE_RE.match(line)
    if not match:
        return None
    args = _split_args(match.group(2))
    # Trailing comments are allowed by OpenSSH
    for index, arg in enumerate(args):
        if arg.startswith("#"):
            args = args[:index]
            break
    return match.group(1).lower(), args


def _read_lines(path):
    with open(path, "r", encoding="utf-8-sig", errors="replace") as f:
        return f.read().splitlines()


def _parse_file(path, blocks, condition, depth, chain):
    """
    Appends (condition, options) blocks to `blocks`. A condition is None (always
    applies), or a list of Host patterns. Unsupported Match blocks get condition False.
    """
    real_path = os.path.realpath(path)
    if depth > MAX_INCLUDE_DEPTH or real_path in chain:
        PLUGIN_LOGGER.warning("Ignoring recursive SSH config Include of '%s'.", path)
        return
    chain = chain | {real_path}

    current = (condition, [])
    blocks.append(current)
    for line in _read_lines(path):
        parsed = _parse_line(line)
        if parsed is None:
            continue
        keyword, args = parsed

        if keyword == "host":
            current = (args, [])
            blocks.append(current)
        elif keyword == "match":
            is_all = [arg.lower() for arg in args] == ["all"]
            current = (None if is_all else False, [])
            blocks.append(current)
        elif keyword == "include":
            for pattern in args:
                for included in _expand_include(pattern):
                    _parse_file(included, blocks, current[0], depth + 1, chain)
            # Lines after the Include keep applying to the enclosing block
            current = (current[0], [])
            blocks.append(current)
        elif args:
            current[1].append((keyword, args))


def _expand_include(pattern):
    pattern = os.path.expanduser(pattern)
    if not os.path.isabs(pattern):
        pattern = os.path.join(ssh_directory(), pattern)
    return [path for path in sorted(glob.glob(pattern)) if os.path.isfile(path)]


def _pattern_matches(name, pattern):
    # ssh patterns only know * and ?, so [ must not be a character class
    pattern = pattern.lower().replace("[", "[[]")
    return fnmatch.fnmatchcase(name.lower(), pattern)


def _host_matches(alias, patterns):
    matched = False
    for pattern in patterns:
        if pattern.startswith("!"):
            if _pattern_matches(alias, pattern[1:]):
                return False
        elif _pattern_matches(alias, pattern):
            matched = True
    return matched


def _is_literal_alias(pattern):
    return not any(char in pattern for char in "*?!")


class SSHConfig:
    def __init__(self, blocks):
        self._blocks = blocks

    @classmethod
    def from_file(cls, path):
        blocks = []
        _parse_file(path, blocks, None, 0, frozenset())
        return cls(blocks)

    def aliases(self):
        """Concrete (non-wildcard) Host names, in file order."""
        seen, aliases = set(), []
        for condition, _ in self._blocks:
            if not condition:
                continue
            for pattern in condition:
                if _is_literal_alias(pattern) and pattern not in seen:
                    seen.add(pattern)
                    aliases.append(pattern)
        return aliases

    def lookup(self, alias):
        """Options for `alias`. As in OpenSSH, the first obtained value wins."""
        options = {}
        for condition, block_options in self._blocks:
            if condition is False:
                continue
            if condition is not None and not _host_matches(alias, condition):
                continue
            for keyword, args in block_options:
                if keyword in _MULTI_VALUE_KEYWORDS:
                    options.setdefault(keyword, []).append(args)
                elif keyword not in options:
                    options[keyword] = args
        return options


# --------------------------------------------------------------- conversion


def _expand_tokens(value, tokens):
    return re.sub(r"%(.)", lambda m: tokens.get(m.group(1), m.group(0)), value)


def _split_host_port(text):
    """'host:port', 'host/port', '[ipv6]:port' or 'port' -> (host, port)."""
    if text.startswith("["):
        host, _, rest = text[1:].partition("]")
        return host, rest.lstrip(":/")
    for separator in (":", "/"):
        if separator in text:
            host, _, port = text.rpartition(separator)
            return host, port
    return "", text


def _normalize_address(host):
    if host.lower() in _LOCALHOST_NAMES or host in ("", "*", "::1"):
        return "127.0.0.1"
    return host


def _parse_local_forward(args):
    """Returns (local_port, remote_host, remote_port) or None if unsupported."""
    if len(args) < 2:
        return None
    _, local_port = _split_host_port(args[0])
    remote_host, remote_port = _split_host_port(args[1])
    try:
        return int(local_port), _normalize_address(remote_host), int(remote_port)
    except ValueError:
        return None  # e.g. unix sockets


def _next_free_port(used_ports):
    port = FIRST_LOCAL_PORT
    while port in used_ports:
        port += 1
    return port


def _first_value(options, keyword, default=""):
    args = options.get(keyword)
    return args[0] if args else default


def to_connection_parameters(alias, options, used_local_ports):
    """
    Converts the looked-up options of `alias` into connection parameters.
    Returns (parameters, warnings). Adds the chosen local port to `used_local_ports`.
    """
    warnings = []
    local_user = _local_username()
    home = os.path.expanduser("~")

    hostname = _expand_tokens(
        _first_value(options, "hostname", alias), {"h": alias, "%": "%"}
    )
    username = _first_value(options, "user", local_user)

    port_value = _first_value(options, "port", "22")
    try:
        ssh_port = int(port_value)
    except ValueError:
        warnings.append(f"invalid Port '{port_value}', using 22")
        ssh_port = 22

    tokens = {
        "d": home,
        "u": local_user,
        "r": username,
        "h": hostname,
        "p": str(ssh_port),
        "n": alias,
        "%": "%",
    }
    id_file = ""
    for args in options.get("identityfile", []):
        candidate = os.path.normpath(
            os.path.expanduser(_expand_tokens(args[0], tokens))
        )
        if os.path.isfile(candidate):
            id_file = candidate
            break
    else:
        if options.get("identityfile"):
            warnings.append("none of its IdentityFile keys exist")

    forward = None
    for args in options.get("localforward", []):
        forward = _parse_local_forward(args)
        if forward:
            break
    if forward:
        local_port, remote_bind_address, remote_port = forward
    else:
        local_port = _next_free_port(used_local_ports)
        remote_bind_address, remote_port = "127.0.0.1", DEFAULT_REMOTE_PORT
    used_local_ports.add(local_port)

    for keyword in ("proxyjump", "proxycommand"):
        value = _first_value(options, keyword)
        if value and value.lower() != "none":
            warnings.append(
                f"{keyword} is not supported, the connection was imported without it"
            )

    parameters = {
        "name": alias,
        "host": hostname,
        "ssh_port": ssh_port,
        "remote_bind_address": remote_bind_address,
        "remote_port": remote_port,
        "local_port": local_port,
        "username": username,
        "password": None,  # Bandit Security Analysis flags empty str as possible hardcoded password
        "id_file": id_file,
        "pkey_password": None,  # Bandit Security Analysis flags empty str as possible hardcoded password
        "ssh_proxy": "",
        "ssh_proxy_enabled": False,
    }
    return parameters, warnings


def load_from_ssh_config(config_path=None, used_local_ports=()):
    """
    Returns (list of (parameters, warnings)) for every concrete Host in the config.
    Returns an empty list if the config file does not exist.
    Raises OSError if it exists but cannot be read.
    """
    config_path = config_path or default_ssh_config_path()
    if not os.path.isfile(config_path):
        PLUGIN_LOGGER.info("No SSH config found at '%s'.", config_path)
        return []

    config = SSHConfig.from_file(config_path)
    used_ports = set(used_local_ports)
    results = [
        to_connection_parameters(alias, config.lookup(alias), used_ports)
        for alias in config.aliases()
    ]
    PLUGIN_LOGGER.info(
        "Found %d host(s) in SSH config '%s'.", len(results), config_path
    )
    return results

import os

from ..Connection import IConnection, Connection
from ..install_packages.check_dependencies import check


DEPENDENCIES_EXIST = False
try:
    from sshconf import read_ssh_config

    DEPENDENCIES_EXIST = True
except Exception as e:
    try:
        check(["paramiko", "sshconf"])
    finally:
        from sshconf import read_ssh_config

        DEPENDENCIES_EXIST = True


def parse_ssh_config(ssh_config_file):
    # Initialize an empty dictionary to store the configuration settings
    ssh_config = dict()
    parsed_config = read_ssh_config(ssh_config_file)

    for host in parsed_config.hosts():
        ssh_config[host] = parsed_config.host(host)

    return ssh_config


def convert_to_connection_params(ssh_config):
    connections = []

    for host, config in ssh_config.items():
        connection = IConnection(
            name=host,
            host=config.get("hostname", ""),
            ssh_port=config.get("port", 22),
            username=config.get("user", ""),
            # id_file=config.get("identityfile", ""),
            # pkey_password=config.get("identityfile", ""),
            ssh_proxy=config.get("proxycommand", ""),
            ssh_proxy_enabled=config.get("proxycommand", False),
            password=config.get("password", "changeme"),
            remote_bind_address=config.get("remote_bind_address", "127.0.0.1"),
            remote_port=config.get("remote_port", 5432),
            local_port=config.get("local_port", 5433),
            is_connected=False,
        )

        connections.append(connection)

    return connections


def load_from_ssh_config():
    # try:
    config_file = os.path.expanduser("~/.ssh/config")
    ssh_config = parse_ssh_config(config_file)
    params_array = convert_to_connection_params(ssh_config)

    print(f"Found SSH config file at {config_file}")
    print(ssh_config)
    print(params_array)

    return params_array

    # return ssh_config
    # except Exception as e:
    #    print(e)
    #    return None

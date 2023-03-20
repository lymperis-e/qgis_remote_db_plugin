import os


from .install_packages.check_dependencies import check

DEPENDENCIES_EXIST = False
try:
    from .sshtunnel.sshtunnel import SSHTunnelForwarder
    DEPENDENCIES_EXIST = True
except:
    try:
        check(['sshtunnel'])
    finally:
        from .sshtunnel.sshtunnel import SSHTunnelForwarder
        DEPENDENCIES_EXIST = True




class Connection:
    
    def __init__(self, connection_params):
        
        self.parameters = connection_params

        self.name        = connection_params["name"]
        self.host        = connection_params["host"]
        self.ssh_port    = connection_params["ssh_port"]
        self.user        = connection_params["username"]
        self.password    = connection_params["password"]
        self.remote_port = connection_params["remote_port"]
        self.local_port  = connection_params["local_port"]

        self._server = self._get_server()
        self.is_connected = False


    def _get_server(self):
        tunnel_server = SSHTunnelForwarder(
            self.host,
            ssh_password=self.password,
            ssh_username=self.user,
            remote_bind_address=('127.0.0.1', self.remote_port),
            local_bind_address=('0.0.0.0',self.local_port),
            ssh_port=self.ssh_port
        )
        return tunnel_server
    
    def connect(self):
        if self._server:
            try:
                self._server.start()
                self.is_connected = True
                
            except Exception as e:
                self.is_connected = False
                print(e)

    def disconnect(self):
        if self._server:
            self._server.stop()
            self.is_connected = False

import netsnmp


class SNMP:
    """
        Wrap class for snmp library.
        netsnmp official library has an odd syntax for me and there is another library available in pip3 with a better
        one. But in case we may need to change this to another one, this class should minimize the amount of rework.
    """
    host = ''
    version = 2
    community = 'public'
    sessao = None
    _mapa = {1: '1', 2: '2c', 3: '3'}

    def __init__(self, host, community='public', version=2):
        self.community = community
        self.version = self._mapa[version]
        # para IPv6, é preciso indicar o transporte explicitamente.
        # há uma função no SNMP que tenta descobrir se o nome de host é FQDN, socket, etc
        # e atribuir o devido transporte (udp, tcp, unix socket, etc)
        # Para simplificar, o transporte é adicionado aqui para não bugar a camada de cima
        self.host = 'udp6:[{}]'.format(host) if ':' in host else host

    def start(self):
        try:
            self.sessao = netsnmp.SNMPSession(self.host, self.community)
        except:
            print("Session err for {}".format(self.host))
            raise

    def bind(self, oids):
        if isinstance(oids, str):
            oids_var = netsnmp.VarList(netsnmp.Varbind(oids, 0))
        else:
            oids_var = netsnmp.VarList(*[netsnmp.Varbind(v, 0) for v in oids])
        return oids_var

    def get(self, oids_var):
        return self.sessao.get(oids_var)

    def getnext(self, oids_var):
        return self.sessao.getnext(oids_var)

    def walk(self, oids_var):
        return self.sessao.walk(oids_var)

    # type_var must be one of several letters provided by snmpset -h
    def set(self, oids_var, value, type_var):
        return self.sessao.set(oids_var, value, type_var)



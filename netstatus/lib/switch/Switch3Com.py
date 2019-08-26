from .Switch import Switch


class Switch3Com(Switch):
    @classmethod
    def is_compatible(cls, descr):
        parte1, parte2 = descr.split(' ')[0:2]
        if parte1.lower() == '3com':
            return True
        return False

# ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~


class Switch3Com4500G(Switch3Com):
    @classmethod
    def is_compatible(cls, descr):
        s = descr.split(' ')
        if len(s) > 2:
            parte1, parte2, parte3  = s[0:3]
            if parte2.lower() == 'switch' and parte3 == '4500G':
                return True
        return False

    def __init__(self, host, community='public', version=2):
        super().__init__(host, community, version)
        self._portas_tipo = {}

    # função extra para carregar informações das portas específicas para cada tipo de switch
    # e que não deveriam interferir nas coisas de get_ports(), nem suas variáveis correlatas
    def _get_portas_tipo(self):
        macs = self.sessao.walk(self._ifVLANType)
        for (oid, _type, value) in macs:
            port = oid.strip().split('.')[-1]
            self._portas_tipo[port] = int(value)

    # .1.3.6.1.4.1.43.45.1.2.23.1.1.3.1.2.[port]   hwifHybridTaggedVlanListLow
    # .1.3.6.1.4.1.43.45.1.2.23.1.1.3.1.3.[port]   hwifHybridTaggedVlanListHigh
    # .1.3.6.1.4.1.43.45.1.2.23.1.5.1.3.1.6.[port] hwifVLANTrunkAllowListLow
    # .1.3.6.1.4.1.43.45.1.2.23.1.5.1.3.1.7.[port] hwifVLANTrunkAllowListHigh
    # .1.3.6.1.4.1.43.45.1.2.23.1.1.1.1.5.[port]   hwifVLANType    #   {vLANTrunk(1), access(2), hybrid(3), fabric(4)
    # Problema: 
    #   Campos de leitura e escrita estão separados por modalidade trunk/access/híbrido. 
    #   Vai ser bem complexo fazer set com esse aqui.
    def set_vlan_tag(self, port, vlan):
        if type(port) is not int:
            port = int(port)
        if type(vlan) is not str:
            vlan = str(vlan)
        if self._portas_tipo == {}:
            self._get_portas_tipo()
        # if access port, returns error because setting pvid is enough
        if self._portas_tipo[port] == 2:
            return 2
        # case there is fabric port somewhere...
        if self._portas_tipo[port] == 4:
            return 4

        return 0

# ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~


class Switch3Com7900(Switch3Com):
    @classmethod
    def is_compatible(cls, descr):
        s = descr.split(' ')
        if len(s) > 1:
            parte1, parte2 = s[0:2]
            if parte2[0:4] == 'S790':
                return True
        return False

    def __init__(self, host, community='public', version=2):
        super().__init__(host, community, version)



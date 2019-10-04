import re
  
from .switchlib import mask_bigendian
from .Switch import Switch
from .switchlib import *


class SwitchExtreme(Switch):
    @classmethod
    def is_compatible(cls, descr):
        parte1 = descr.split(' ')[0]
        if parte1 == 'ExtremeXOS':
            return True
        return False

    def __init__(self, host, community='public', version=2):
        super().__init__(host, community, version)
        self._mask = mask_bigendian


class SwitchExtremeX440(SwitchExtreme):
    """ Needs the latest firmware, at least 16.x, with SNMP enabled """
    @classmethod
    def is_compatible(cls, descr):
        parte1, parte2 = descr.split(' ')[0:2]
        parte2 = parte2.split('-')[0][1:]
        if parte1 == 'ExtremeXOS' and parte2 == 'X440':
            return True
        return False

    def __init__(self, host, community='public', version=2):
        super().__init__(host, community, version)
        self._oids_vlans = {
            'vlans': '.1.3.6.1.4.1.1916.1.2.1.2.1.10',
            'tagged': '.1.3.6.1.4.1.1916.1.2.6.1.1.1',
            'untagged': '.1.3.6.1.4.1.1916.1.2.6.1.1.2',
        }
        self._oids_poe['poempower'] = '.1.3.6.1.4.1.1916.1.27.2.1.1.6.1'

    def _vlans_list(self):
        return tuple(sorted([v[netsnmp.VALUE] for v in self.sessao.walk(self._oids_vlans['vlans'])]))

    def _snmp_ports_stp(self, port):
        port = self._map_bport_ifidx(int(port))
        super()._snmp_ports_stp(port)



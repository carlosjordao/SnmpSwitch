from .switchlib import _mask_littleendian
from .Switch import Switch


class SwitchHH3C(Switch):
    """
    MIB default: hh3c
    Common class for several HP switches.
    Expected kind of string:
        HP Comware Platform Software, Software Version 5.20.99 Release 2222P11
        HP A5120-24G-PoE+ EI Switch with 2 Interface Slots
        Copyright (c) 2010-2018 Hewlett Packard Enterprise Development LP
    """

    @classmethod
    def is_compatible(cls, descr):
        parte1, parte2 = descr.split(' ')[0:2]
        if parte1[0:2] == 'HP':
            return True
        return False

    def __init__(self, host, community='public', version=2):
        super().__init__(host, community, version)
        self._oids_vlans = {
            'vlans': '.1.3.6.1.4.1.25506.8.35.2.1.1.1.1',
            'tagged': '.1.3.6.1.4.1.25506.8.35.2.1.1.1.17',
            'untagged': '.1.3.6.1.4.1.25506.8.35.2.1.1.1.18',
        }
        self._oids_poe = {
            'poeadmin': '.1.3.6.1.2.1.105.1.1.1.',
            'poempower': '.1.3.6.1.4.1.25506.2.14.1.1.3',
            'poesuffix': '4',
        }
        self._ifVLANType = '.1.3.6.1.4.1.25506.8.35.1.1.1.5'  # hh3cifVLANType
        self._oids_ifexists_intvlan = '.1.3.6.1.4.1.25506.8.35.2.1.1.1.7'  # hh3cExistInterface
        self._oids_intvlan = (
            '.1.3.6.1.4.1.25506.8.35.2.1.2.1.3',  # hh3cdot1qVlanIpAddress - "IP address of interface."
            '.1.3.6.1.4.1.25506.8.35.2.1.2.1.4',  # hh3cdot1qVlanIpAddressMask - "IP address mask of interface."
            '.1.3.6.1.4.1.25506.8.35.2.1.2.1.5',  # hh3cVlanInterfaceAdminStatus -
                                                  # "Status of VLAN virtual interfaces." (up/down, 1/2)
        )
        # hh3cExistInterface, 1/2 = true/false for each vlan if there is int vlan
        self._oids_ifexists_intvlan = '.1.3.6.1.4.1.25506.8.35.2.1.1.1.7'

# -----------------


class SwitchHH3C_J9850A(SwitchHH3C):
    @classmethod
    def is_compatible(cls, descr):
        parte1, parte2 = descr.split(' ')[0:2]
        parte2a = parte2.split('-')[0]
        if parte1[0:2] == 'HP' and parte2a == 'J9850A':
            return True
        return False

    def __init__(self, host, community='public', version=2):
        super().__init__(host, community, version)
        self._mascara = _mask_littleendian
        self._oids_poe['poesuffix'] = '1'
        self._fab_var = '1'
        self._oids_vlans = {
            'vlans': '.1.3.6.1.2.1.17.7.1.4.2.1.3.0'
            , 'tagged': '.1.3.6.1.2.1.17.7.1.4.3.1.2'
            , 'untagged': '.1.3.6.1.2.1.17.7.1.4.3.1.4'
        }

    # gambiarra até resolver o problema da descoberta correta do uplink
    def _lldp_filter_é_uplink(self, lporta, arr):
        return True

# -----------------


class SwitchHH3C_V1910(SwitchHH3C):
    @classmethod
    def is_compatible(cls, descr):
        parte1, parte2 = descr.split(' ')[0:2]
        parte2a = parte2.split('-')[0]
        if parte1[0:2] == 'HP' and parte2a == 'V1910':
            return True
        return False

    def __init__(self, host, community='public', version=2):
        super().__init__(host, community, version)
        self._oids_poe['poesuffix'] = '1'
        self._fab_var = '1'

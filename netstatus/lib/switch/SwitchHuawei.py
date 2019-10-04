from .Switch import Switch


class SwitchHuawei(Switch):
    """
    Main class for all Huawei switch family.
    Specific models will need adjust as in any vendor family, but the major differences compared to
    the Switch class should be in here.
    """
    @classmethod
    def is_compatible(cls, descr):
        """
        Checks if the switch is Huawei.
        Expected string template from Huawei:
             S5720-28X-PWR-SI-AC
             Huawei Versatile Routing Platform Software
             VRP (R) software,Version 5.170 (S5720 V200R010C00SPC600)
             Copyright (C) 2007 Huawei Technologies Co., Ltd.
        :param descr:
        :return:
        """
        parte1, parte2 = descr.split('\n')[0:2]
        if parte2[0:6] == 'Huawei':
            return True
        return False

    def __init__(self, host, community='public', version=2):
        super().__init__(host, community, version)
        self._fab_var = '1'
        self._oids_vlans = {
            # Using hwL2VlanDescr because it has a shorter list of VLANs, with the only one created in the switch
            'vlans':    '.1.3.6.1.4.1.2011.5.25.42.3.1.1.1.1.2',
            'tagged':   '.1.3.6.1.2.1.17.7.1.4.3.1.2',
            'untagged': '.1.3.6.1.2.1.17.7.1.4.3.1.4',
        }
        self._oids_poe = {
            'poeadmin':  '1.3.6.1.4.1.2011.5.25.195.3.1',
            'poempower': '1.3.6.1.4.1.2011.5.25.195.3.1.10',
            'poesuffix': '',
        }
        # hwL2IfPortType
        self._ifVLANType = '.1.3.6.1.4.1.2011.5.25.42.1.1.1.3.1.3'

    def get_geral(self):
        super().get_geral()
        self.model = self.descr.split(' ')[0]

    def _conv_poe_status(self, poe_status):
        """ Change on/off to 1/0. Used with POE settings. This issue is specific for the Huawei MIB. """
        return 1 if poe_status == 'on' else 0


class SwitchHuaweiS5700(SwitchHuawei):
    """
    Subclass for S5700 switch family from Huawei.
    Adjusts some specific parameter in this model, as _fab_var, used to composing some OIDs
    """
    @classmethod
    def is_compatible(cls, descr):
        parte1, parte2 = descr.split('\n')[0:2]
        if parte1[0:3] == 'S57':
            return True
        return False

    def __init__(self, host, community='public', version=2):
        super().__init__(host, community, version)
        self._fab_var = '67108867'



import re

from .switchlib import _mask_littleendian
from .Switch import Switch
from .switchlib import *


class SwitchDLINK(Switch):
    """
    This class is strongly based on DGS-3420-28PC. It may need to refactored to support different models as subclasses.
    The _dlink_series and _dlink_model exists because some parts of DLINK MIB tree use such values in the middle of
    their OID, so different models may end up configuring a correct value for itself.
    """
    _dlink_series = '119'
    _dlink_model = '3'

    @classmethod
    def is_compatible(cls, descr):
        parte1 = descr.split(' ')[0]
        if parte1[0:3] == 'DGS':
            return True
        return False

    def __init__(self, host, community='public', version=2):
        super().__init__(host, community, version)
        self._mascara = _mask_littleendian
        self._fab_var = '1'
        self._oids_vlans = {
            'vlans': '.1.3.6.1.2.1.17.7.1.4.2.1.3',
            'tagged': '.1.3.6.1.2.1.17.7.1.4.3.1.2',
            'untagged': '.1.3.6.1.2.1.17.7.1.4.3.1.4',
        }
        self._oids_poe = {
            'poeadmin': '.1.3.6.1.4.1.171.12.24.3.1.1.2',
            'poempower': '.1.3.6.1.4.1.171.12.24.4.1.1',
        }
        self._ifVLANType = '.1.3.6.1.2.1.17.7.1.4.3.1.4'
        self._oids_intvlan = (
            # swL3IpCtrlIpAddr - "IP address of interface."
            '.1.3.6.1.4.1.171.11.{}.{}.3.2.1.3.1.3'.format(self._dlink_series, self._dlink_model),
            # swL3IpCtrlIpSubnetMask - "IP address mask of interface."
            '.1.3.6.1.4.1.171.11.{}.{}.3.2.1.3.1.4'.format(self._dlink_series, self._dlink_model),
            # swL3IpCtrlAdminState - "Admin Status of VLAN virtual interfaces." (enable/disable, 1/2)
            '.1.3.6.1.4.1.171.11.{}.{}.3.2.1.3.1.9'.format(self._dlink_series, self._dlink_model),
        )
        self._oids_ifexists_intvlan = '.1.3.6.1.4.1.171.11.{}.{}.3.2.1.3.1.1'.format(self._dlink_series,
                                                                                     self._dlink_model)

    # poe_admin poe_status poe_class   poe_mpower
    #   swPoEPortCtrlState (1,2,3 = other, enable, disable)
    #   swpoEPortInfoLedStatus (1,2,3 = on, off, error)
    #   swPoEPortInfoClass
    #   swPoEPortInfoPower
    def _oid_poe(self, porta):
        return ['{}.{}'.format(self._oids_poe['poeadmin'], porta)] + \
               ['{}.{}.{}'.format(self._oids_poe['poempower'], v, porta) for v in ('7', '2', '3')]

    def _remap(self, var_dict, value):
        return var_dict[value] if value in var_dict else value

    poe_admin_mapping = {'1': '-1', '2': '1', '3': '2'}

    def _snmp_ports_poe(self, port):
        """
        Remap the values received by the switch from POE admin status to ones we prefer to use.
        :param port:
        :return: the POE values changed.
        """
        ret = super()._snmp_ports_poe(port)
        tmp = self._remap(self.poe_admin_mapping, ret[0][netsnmp.VALUE])
        ret[0] = (ret[0][0], ret[0][1], tmp)
        return ret

    def _snmp_ports_vtype(self, port):
        """
        This function is used to identify access port. 3Com, HPN, Huawei has an equivalent entry.
        As it is not found in this d-link, it will be overwritten to return a void value.
        :param port: not used in here.
        :return: undefined value to not break the caller (get_port_ether()).
        """
        return [['', '', '0']]

    # Aqui depende novamente da configuração no switch. Convencionou-se que o nome
    # da interface vlan (3Com / HPN não tem nome) seja criado com o número da VLAN
    # associada, já que é muito trabalhoso achar, neste modelo, a vlan associada a
    # esse IP. 
    def get_intvlan(self):
        for (_oid, _type, _value) in self.sessao.walk(self._oids_ifexists_intvlan):

            oidid = _oid[len(self._oids_ifexists_intvlan) + 1:]
            try:
                _value = _value.strip('"')
                if _value == 'System':
                    vlan = 1
                else:
                    vlan = int(_value)
            except:
                # D-LINK interfaces are strings (names). Default is 'System'
                continue

            # getting ip, netmask and status
            values = snmp_values(self.sessao.get([v + '.' + oidid for v in self._oids_intvlan]))

            # ignoring disabled intvlan (System can not be erased)
            if values[0] == '0.0.0.0' or values[2] == '2':
                continue
            self.intvlan[vlan] = tuple(values)

    _regex_ifdesc = re.compile("^D-Link .* (Port [^ ]+) .*")

    def _format_ifdesc(self, ifdesc):
        res = self._regex_ifdesc.search(ifdesc)
        try:
            return res.group(1)
        except:
            return ifdesc

# ------------------------ ~ ------------------------

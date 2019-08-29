import os
import unittest
from netstatus.lib.snmp import PseudoSnmp
from netstatus.lib.switchfactory import SwitchFactory
from netstatus.lib.switch.switchlib import *


@unittest.skipUnless(os.path.isfile(PseudoSnmp.path + '/' + 'HPE-JG977A.snmpwalk'),
                     'file HPE-JG977A.snmpwalk not found')
class TestSwitch(unittest.TestCase):
    """
    All different models supported should have a method here.
    """

    def test_load_hpe_jg977a(self):
        self.session = PseudoSnmp('HPE-JG977A.snmpwalk')
        self.session.start()
        # check using basic snmp function used by factory
        self.assertEqual(self.session.get('.1.3.6.1.2.1.1.5.0'), [('.1.3.6.1.2.1.1.5.0', 'STRING', '"SWD-XXXXX-59"')])

        self.switch = SwitchFactory.factory(host=self.session)
        # this is a important check. Wrong classes will mess up everything
        self.assertEqual(self.switch.__class__.__name__, 'SwitchHH3C')
        # expected baseport. Shouldn't be a problem now because everything is automatized
        self.assertEqual(self.switch._map_baseport_ifindex, {i: i for i in range(1, 29)})

        # should check all data load() calls and see if everything ou switch gets is right.
        # just checking raw access to data
        self.switch.get_geral()
        # checking every field as we refactored this method.
        self.assertEqual(self.switch.physical, '5130EI')
        self.assertEqual(self.switch.soft_version, '7.1.070 Release 3208P15')
        self.assertEqual(self.switch.serial, 'BR5BHCJ01W')
        self.assertEqual(self.switch.vendor, 'HPE')
        self.assertEqual(self.switch.model, 'JG977A')
        self.assertEqual(self.switch.mac, '48:0f:cf:d0:79:69')
        self.assertEqual(self.switch.stp, 24)
        self.assertEqual(self.switch.descr, 'HPE Comware Platform Software, Software Version 7.1.070, Release '
                                            '3208P15\nHPE 5130 24G PoE+ 4SFP+ EI BR Switch\nCopyright (c) 2010-2018 '
                                            'Hewlett Packard Enterprise Development LP')
        self.assertEqual(self.switch.name, 'SWD-XXXXX-59')

        self.switch.get_vlans()
        self.assertEqual(self.switch.vlans, ('1', '2', '20', '77'))
        self.assertEqual(self.switch.vtagged, {'1': (0, 0, 0, 0), '2': (255, 255, 251, 0),
                                               '20': (0, 0, 128, 0), '77': (0, 0, 132, 0)})
        self.assertEqual(self.switch.vuntagged, {'1': (255, 255, 251, 15), '2': (0, 0, 0, 0),
                                                 '20': (0, 0, 4, 0), '77': (0, 0, 0, 0)})

        # the check below has some privates mib
        check_ports_v1 = {
            1: ['1', '2', '1', '1', '2', '1', '0', '3'],
            2: ['1', '2', '1', '1', '2', '1', '0', '3'],
            3: ['1', '2', '1', '1', '2', '1', '0', '3'],
            4: ['1', '5', '1', '1', '3', '3', '2300', '3'],
            5: ['1', '2', '1', '1', '2', '1', '0', '3'],
            6: ['1', '2', '1', '1', '2', '1', '0', '3'],
            7: ['1', '2', '1', '1', '2', '1', '0', '3'],
            8: ['1', '2', '1', '1', '2', '1', '0', '3'],
            9: ['1', '2', '1', '1', '2', '1', '0', '3'],
            10: ['1', '5', '1', '1', '3', '3', '2700', '3'],
            11: ['1', '2', '1', '1', '2', '1', '0', '3'],
            12: ['1', '2', '1', '1', '2', '1', '0', '3'],
            13: ['1', '2', '1', '1', '2', '1', '0', '3'],
            14: ['1', '2', '1', '1', '2', '1', '0', '3'],
            15: ['1', '2', '1', '1', '2', '1', '0', '3'],
            16: ['1', '2', '1', '1', '2', '1', '0', '3'],
            17: ['1', '2', '1', '1', '2', '1', '0', '3'],
            18: ['1', '2', '1', '1', '2', '1', '0', '3'],
            19: ['1', '5', '20', '1', '3', '4', '9100', '1'],
            20: ['1', '5', '1', '1', '3', '3', '2700', '3'],
            21: ['1', '2', '1', '1', '2', '1', '0', '3'],
            22: ['1', '2', '1', '1', '2', '1', '0', '3'],
            23: ['1', '5', '1', '1', '2', '1', '0', '3'],
            24: ['1', '5', '1', '2', '1', '1', '0', '1'],
            25: ['1', '2', '1', -1, -1, -1, -1, '2'],
            26: ['1', '2', '1', -1, -1, -1, -1, '2'],
            27: ['1', '2', '1', -1, -1, -1, -1, '2'],
            28: ['1', '2', '1', -1, -1, -1, -1, '2'],
        }
        for port in range(1, 29):
            i = str(port)
            oidlist = self.switch._snmp_ports_stp(i)
            oidlist += self.switch._snmp_ports_poe(i)
            oidlist += self.switch._snmp_ports_vtype(i)
            valores = [x for x in snmp_values(oidlist, filter=True)]
            self.assertEqual(valores, check_ports_v1[port])

        oid_iftype = '.1.3.6.1.2.1.2.2.1.3.1'
        _oid, _type, _value = self.switch.sessao.get(oid_iftype)[0]
        self.assertEqual((_type, _value), ('INTEGER', '6'))

        check_ports_v2 = {
            1: {'speed': 1000, 'duplex': 1, 'admin': 1, 'oper': 2, 'lastchange': 2395, 'discards_in': 0,
                'discards_out': 0, 'oct_in': 0, 'oct_out': 0, 'stp_admin': 1, 'stp_state': 2,
                'poe_admin': 1, 'poe_detection': 2, 'poe_class': 1, 'poe_mpower': 0, 'mac_count': 0,
                'pvid': '1', 'tagged': ['2'], 'untagged': ['1'],
                'nome': 'GigabitEthernet1/0/1', 'alias': 'GigabitEthernet1/0/1 Interface'},
            4: {'speed': 100, 'duplex': 3, 'admin': 1, 'oper': 1, 'lastchange': 5450, 'discards_in': 0,
                'discards_out': 0,
                'oct_in': 19359121, 'oct_out': 4414161744, 'stp_admin': 1, 'stp_state': 5, 'poe_admin': 1,
                'poe_detection': 3,
                'poe_class': 3, 'poe_mpower': 2300, 'mac_count': 0, 'pvid': '1', 'tagged': ['2'], 'untagged': ['1'],
                'nome': 'GigabitEthernet1/0/4', 'alias': 'GigabitEthernet1/0/4 Interface'},
            9: {'speed': 1000, 'duplex': 1, 'admin': 1, 'oper': 2, 'lastchange': 114228910, 'discards_in': 0,
                'discards_out': 0, 'oct_in': 6765367, 'oct_out': 182469974, 'stp_admin': 1, 'stp_state': 2,
                'poe_admin': 1,
                'poe_detection': 2, 'poe_class': 1, 'poe_mpower': 0, 'mac_count': 0, 'pvid': '1', 'tagged': ['2'],
                'untagged': ['1'], 'nome': 'GigabitEthernet1/0/9', 'alias': 'GigabitEthernet1/0/9 Interface'},
            10: {'speed': 100, 'duplex': 3, 'admin': 1, 'oper': 1, 'lastchange': 5388, 'discards_in': 0,
                 'discards_out': 20470,
                 'oct_in': 361550873, 'oct_out': 6101823208, 'stp_admin': 1, 'stp_state': 5, 'poe_admin': 1,
                 'poe_detection': 3,
                 'poe_class': 3, 'poe_mpower': 2700, 'mac_count': 0, 'pvid': '1', 'tagged': ['2'],
                 'untagged': ['1'], 'nome': 'GigabitEthernet1/0/10', 'alias': 'GigabitEthernet1/0/10 Interface'},
            20: {'speed': 100, 'duplex': 3, 'admin': 1, 'oper': 1, 'lastchange': 419138582, 'discards_in': 0,
                 'discards_out': 111003, 'oct_in': 1059458972, 'oct_out': 2297722365, 'stp_admin': 1, 'stp_state': 5,
                 'poe_admin': 1, 'poe_detection': 3, 'poe_class': 3, 'poe_mpower': 2700, 'mac_count': 0, 'pvid': '1',
                 'tagged': ['2'], 'untagged': ['1'], 'nome': 'GigabitEthernet1/0/20',
                 'alias': 'GigabitEthernet1/0/20 Interface'},
            23: {'speed': 10, 'duplex': 3, 'admin': 1, 'oper': 1, 'lastchange': 650126671, 'discards_in': 0,
                 'discards_out': 0, 'oct_in': 67513745, 'oct_out': 5571968174, 'stp_admin': 1, 'stp_state': 5,
                 'poe_admin': 1,
                 'poe_detection': 2, 'poe_class': 1, 'poe_mpower': 0, 'mac_count': 0, 'pvid': '1', 'tagged': ['2'],
                 'untagged': ['1'], 'nome': 'GigabitEthernet1/0/23', 'alias': 'GigabitEthernet1/0/23 Interface'},
            24: {'speed': 1000, 'duplex': 3, 'admin': 1, 'oper': 1, 'lastchange': 5543, 'discards_in': 0,
                 'discards_out': 0,
                 'oct_in': 467624022, 'oct_out': 1614149960, 'stp_admin': 1, 'stp_state': 5, 'poe_admin': 2,
                 'poe_detection': 1,
                 'poe_class': 1, 'poe_mpower': 0, 'mac_count': 0, 'pvid': '1', 'tagged': ['2', '20', '77'],
                 'untagged': ['1'],
                 'nome': 'GigabitEthernet1/0/24', 'alias': 'GigabitEthernet1/0/24 Interface'},
            27: {'speed': 4294, 'duplex': 1, 'admin': 1, 'oper': 2, 'lastchange': 2395, 'discards_in': 0,
                 'discards_out': 0,
                 'oct_in': 0, 'oct_out': 0, 'stp_admin': 1, 'stp_state': 2, 'poe_admin': -1, 'poe_detection': -1,
                 'poe_class': -1, 'poe_mpower': -1, 'mac_count': 0, 'pvid': '1', 'tagged': '', 'untagged': '',
                 'nome': 'Ten-GigabitEthernet1/0/27', 'alias': 'Ten-GigabitEthernet1/0/27 Interface'},
            28: {'speed': 4294, 'duplex': 1, 'admin': 1, 'oper': 2, 'lastchange': 2395, 'discards_in': 0,
                 'discards_out': 0,
                 'oct_in': 0, 'oct_out': 0, 'stp_admin': 1, 'stp_state': 2, 'poe_admin': -1, 'poe_detection': -1,
                 'poe_class': -1, 'poe_mpower': -1, 'mac_count': 0, 'pvid': '1', 'tagged': '', 'untagged': '',
                 'nome': 'Ten-GigabitEthernet1/0/28', 'alias': 'Ten-GigabitEthernet1/0/28 Interface'}
        }
        self.switch.get_ports()
        for k in check_ports_v2.keys():
            self.assertEqual(self.switch.portas[k], check_ports_v2[k])

        self.switch.get_lldp_neighbor()
        self.assertEqual(self.switch.lldp[24], {'locportdesc': 'GigabitEthernet1/0/24 Interface', 'chassissubtype': '4',
                                                'portsubtype': '5', 'rport': '21', 'remportdesc': 'SWD-59',
                                                'remsysname': 'SWA-XXXX-59', 'capsupported': '(', 'capenable': 40,
                                                'rmac': '48:0f:cf:d0:41:d1'})
        self.assertEqual(self.switch.uplink, (24,))

        self.switch.get_mac_list()
        self.assertEqual(self.switch.macs[0], (10, '00:15:65:34:94:50', 2))


if __name__ == '__main__':
    unittest.main()

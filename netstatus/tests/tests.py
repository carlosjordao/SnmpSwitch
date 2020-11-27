import os
import unittest

from netsnmp._api import SNMPError
from django.test.client import RequestFactory

from netstatus.lib.switch import switchlib, Switch
from netstatus.lib.switch.SwitchHH3C import SwitchHH3C
from netstatus.settings import Settings
from netstatus.lib.snmp import PseudoSnmp
from netstatus.lib.switchfactory import SwitchFactory
from netstatus.lib.switch.switchlib import *
from netstatus.views.probe import *


class TestSwitch(unittest.TestCase):
    """
    Test several different states, configurations and functions.
    """

    def test_app_configuration(self):
        self.assertTrue(hasattr(Settings, 'LLDP_IS_UPLINK_EXTRA'))
        self.assertTrue(hasattr(Settings, 'MANAGEMENT_VLAN'))
        self.assertIsNotNone(getattr(switchlib, Settings.LLDP_IS_UPLINK_EXTRA, None),
                             'LLDP_IS_UPLINK_EXTRA should be defined in switchlib')
        if Settings.SWITCH_ALIAS:
            l = lambda: 0
            self.assertEqual(Settings.SWITCH_ALIAS.__name__, l.__name__,
                             'SWITCH_ALIAS should be a lambda expression or None')

    def test_factory(self):
        descr = 'HPE Comware Platform Software, Software Version 7.1.070, Release 3208P15\n' \
                'HPE 5130 24G PoE+ 4SFP+ EI BR Switch\n' \
                'Copyright (c) 2010-2018 Hewlett Packard Enterprise Development LP'
        switch = SwitchFactory._type(descr, Switch.Switch)
        self.assertEqual(switch.__name__, 'SwitchHH3C')

        descr = 'HPE Comware Platform Software, Software Version 5.20.99, Release 2112P05\n' \
                'HPE 3600-24-PoE+ v2 EI Switch\n' \
                'Copyright (c) 2010-2018 Hewlett Packard Enterprise Development LP'
        switch = SwitchFactory._type(descr, Switch.Switch)
        self.assertEqual(switch.__name__, 'SwitchHH3C')

        descr = 'HPE V1910-24G-PoE (170W) Switch Software Version 5.20, Release 1519P03 \n' \
                'Copyright(c) 2010-2017 Hewlett Packard Enterprise Development, L.P.'
        switch = SwitchFactory._type(descr, Switch.Switch)
        self.assertEqual(switch.__name__, 'SwitchHH3C_V1910')

        descr = 'HP J9850A Switch 5406Rzl2, revision KB.16.04.0008, ROM KB.16.01.0006 ' \
                '(/ws/swbuildm/rel_ukiah_qaoff/code/build/bom(swbuildm_rel_ukiah_qaoff_rel_ukiah))'
        switch = SwitchFactory._type(descr, Switch.Switch)
        self.assertEqual(switch.__name__, 'SwitchHH3C_J9850A')

        descr = 'HP Comware Platform Software, Software Version 5.20.99 Release 2222P11 \n' \
                'HP A5120-24G-PoE+ EI Switch with 2 Interface Slots \n' \
                'Copyright (c) 2010-2018 Hewlett Packard Enterprise Development LP'
        switch = SwitchFactory._type(descr, Switch.Switch)
        self.assertEqual(switch.__name__, 'SwitchHH3C')

        descr = 'S5720-28X-PWR-SI-AC\n' \
                'Huawei Versatile Routing Platform Software\n' \
                'VRP (R) software,Version 5.170 (S5720 V200R010C00SPC600)\n' \
                'Copyright (C) 2007 Huawei Technologies Co., Ltd.'
        switch = SwitchFactory._type(descr, Switch.Switch)
        self.assertEqual(switch.__name__, 'SwitchHuaweiS5700')

        descr = 'DGS-3420-28PC Gigabit Ethernet Switch'
        switch = SwitchFactory._type(descr, Switch.Switch)
        self.assertEqual(switch.__name__, 'SwitchDLINK')

        descr = '3Com Switch 4500G PWR 24-Port Software Version 3Com OS V5.02.00s168p20'
        switch = SwitchFactory._type(descr, Switch.Switch)
        self.assertEqual(switch.__name__, 'Switch3Com4500G')

        descr = 'ExtremeXOS (X440-24p-10G) version 15.3.1.4 v1531b4-patch1-19 by release-manager on Fri Sep 20 14:57:37 EDT 2013'
        switch = SwitchFactory._type(descr, Switch.Switch)
        self.assertEqual(switch.__name__, 'SwitchExtremeX440')


    def test_vlans_hh3c(self):
        switch = SwitchHH3C('')
        switch.vlans = ('1', '2', '20', '77')
        switch.vtagged = {'1': (0, 0, 0, 0), '2': (255, 255, 251, 0),
                          '20': (0, 0, 128, 0), '77': (0, 0, 132, 0)}
        switch.vuntagged = {'1': (255, 255, 251, 15), '2': (0, 0, 0, 0),
                            '20': (0, 0, 4, 0), '77': (0, 0, 0, 0)}
        check = {1: (['2'], ['1']),
                 2: (['2'], ['1']),
                 3: (['2'], ['1']),
                 4: (['2'], ['1']),
                 5: (['2'], ['1']),
                 6: (['2'], ['1']),
                 7: (['2'], ['1']),
                 8: (['2'], ['1']),
                 9: (['2'], ['1']),
                 10: (['2'], ['1']),
                 11: (['2'], ['1']),
                 12: (['2'], ['1']),
                 13: (['2'], ['1']),
                 14: (['2'], ['1']),
                 15: (['2'], ['1']),
                 16: (['2'], ['1']),
                 17: (['2'], ['1']),
                 18: (['2'], ['1']),
                 19: (['77'], ['20']),
                 20: (['2'], ['1']),
                 21: (['2'], ['1']),
                 22: (['2'], ['1']),
                 23: (['2'], ['1']),
                 24: (['2', '20', '77'], ['1']),
                 25: ([], ['1']),
                 26: ([], ['1']),
                 27: ([], ['1']),
                 28: ([], ['1']),
                 }
        for i in range(1, 29):
            self.assertEqual(switch._vlans_ports(i), check[i], 'failed vlans for port {}'.format(i))


class TestSwitchLoad(unittest.TestCase):
    """
    Full run of all switch properties and data usually loaded and consumed by Models and Views.
    """

    @unittest.skipUnless(os.path.isfile(PseudoSnmp.path + '/' + 'HPE-JG977A.snmpwalk'),
                         'file HPE-JG977A.snmpwalk not found')
    def test_load_hpe_jg977a(self):
        session = PseudoSnmp('HPE-JG977A.snmpwalk')
        session.start()
        # check using basic snmp function used by factory
        # self.assertEqual(session.get('.1.3.6.1.2.1.1.5.0'), [('.1.3.6.1.2.1.1.5.0', 'STRING', '"SWD-XXXXX-59"')])

        switch = SwitchFactory.factory(host=session)
        # this is a important check. Wrong classes will mess up everything
        self.assertEqual(switch.__class__.__name__, 'SwitchHH3C')
        # expected baseport. Shouldn't be a problem now because everything is automatized
        self.assertEqual(switch._map_baseport_ifindex, {i: i for i in range(1, 29)})

        # should check all data load() calls and see if everything ou switch gets is right.
        # just checking raw access to data
        switch.get_geral()
        # checking every field as we refactored this method.
        self.assertEqual(switch.physical, '5130EI')
        self.assertEqual(switch.soft_version, '7.1.070 Release 3208P15')
        self.assertEqual(switch.vendor, 'HPE')
        self.assertEqual(switch.model, 'JG977A')
        self.assertEqual(switch.mac, 'aa:bb:cc:dd:ee:ff')
        self.assertEqual(switch.stp, 24)
        self.assertEqual(switch.descr, 'HPE Comware Platform Software, Software Version 7.1.070, Release '
                                       '3208P15\nHPE 5130 24G PoE+ 4SFP+ EI BR Switch\nCopyright (c) 2010-2018 '
                                       'Hewlett Packard Enterprise Development LP')
        # self.assertEqual(switch.name, 'SWD-XXXXX-59')

        switch.get_vlans()
        self.assertEqual(switch.vlans, ('1', '2', '20', '77'))
        self.assertEqual(switch.vtagged, {'1': (0, 0, 0, 0), '2': (255, 255, 251, 0),
                                          '20': (0, 0, 128, 0), '77': (0, 0, 132, 0)})
        self.assertEqual(switch.vuntagged, {'1': (255, 255, 251, 15), '2': (0, 0, 0, 0),
                                            '20': (0, 0, 4, 0), '77': (0, 0, 0, 0)})

        #self.assertEqual(switch._mask.__name__, 'mask_bigendian')
        self.assertEqual(switch._mask.__name__, 'mask_littleendian')

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
            oidlist = switch._snmp_ports_stp(i)
            oidlist += switch._snmp_ports_poe(i)
            oidlist += switch._snmp_ports_vtype(i)
            valores = [x for x in snmp_values(oidlist, filter_=True)]
            self.assertEqual(valores, check_ports_v1[port], "port (stp, poe, vtype) failed on {}".format(port))

        oid_iftype = '.1.3.6.1.2.1.2.2.1.3.1'
        _oid, _type, _value = switch.sessao.get(oid_iftype)[0]
        self.assertEqual((_type, _value), ('INTEGER', '6'))

        switch.get_ports()

        check_tag = {
            1: [['2'], ['1'], '1'],
            2: [['2'], ['1'], '1'],
            3: [['2'], ['1'], '1'],
            4: [['2'], ['1'], '1'],
            5: [['2'], ['1'], '1'],
            6: [['2'], ['1'], '1'],
            7: [['2'], ['1'], '1'],
            8: [['2'], ['1'], '1'],
            9: [['2'], ['1'], '1'],
            10: [['2'], ['1'], '1'],
            11: [['2'], ['1'], '1'],
            12: [['2'], ['1'], '1'],
            13: [['2'], ['1'], '1'],
            14: [['2'], ['1'], '1'],
            15: [['2'], ['1'], '1'],
            16: [['2'], ['1'], '1'],
            17: [['2'], ['1'], '1'],
            18: [['2'], ['1'], '1'],
            19: [['77'], ['20'], '20'],
            20: [['2'], ['1'], '1'],
            21: [['2'], ['1'], '1'],
            22: [['2'], ['1'], '1'],
            23: [['2'], ['1'], '1'],
            24: [['2', '20', '77'], ['1'], '1'],
            25: [[], [], '1'],
            26: [[], [], '1'],
            27: [[], [], '1'],
            28: [[], [], '1'],
        }
        for k in switch.portas.keys():
            i = switch.portas[k]
            self.assertEqual([i['tagged'], i['untagged'], i['pvid']], check_tag[k],
                             'failed vlans for port {}'.format(k))

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
                 'poe_class': -1, 'poe_mpower': -1, 'mac_count': 0, 'pvid': '1', 'tagged': [], 'untagged': [],
                 'nome': 'Ten-GigabitEthernet1/0/27', 'alias': 'Ten-GigabitEthernet1/0/27 Interface'},
            28: {'speed': 4294, 'duplex': 1, 'admin': 1, 'oper': 2, 'lastchange': 2395, 'discards_in': 0,
                 'discards_out': 0,
                 'oct_in': 0, 'oct_out': 0, 'stp_admin': 1, 'stp_state': 2, 'poe_admin': -1, 'poe_detection': -1,
                 'poe_class': -1, 'poe_mpower': -1, 'mac_count': 0, 'pvid': '1', 'tagged': [], 'untagged': [],
                 'nome': 'Ten-GigabitEthernet1/0/28', 'alias': 'Ten-GigabitEthernet1/0/28 Interface'}
        }
        for k in check_ports_v2.keys():
            self.assertEqual(switch.portas[k], check_ports_v2[k])

        switch.get_lldp_neighbors()
        self.assertEqual(switch.lldp[24], {'locportdesc': 'GigabitEthernet1/0/24 Interface', 'chassissubtype': '4',
                                           'portsubtype': '5', 'rport': '21', 'remportdesc': 'SWD-59',
                                           'remsysname': 'SWA-XXXX-59', 'capsupported': '(', 'capenable': 40,
                                           'rmac': '01:02:03:04:05:06'})
        self.assertEqual(switch.uplink, (24,))

        switch.get_mac_list()
        self.assertEqual(switch.macs[2], (10, '00:01:01:01:01:01', 2))


    @unittest.skipUnless(os.path.isfile(PseudoSnmp.path + '/' + '3Com-3CR17771-91.snmpwalk'),
                         'file 3Com-3CR17771-91.snmpwalk not found')
    def test_load_hpe_a3600(self):
        session = PseudoSnmp('3Com-3CR17771-91.snmpwalk')
        session.start()
        switch = SwitchFactory.factory(host=session)
        self.assertNotEqual(switch, None)
        switch.get_geral()
        switch.get_vlans()
        self.assertEqual(switch.vlans, ('1', '10', '182', '2', '20', '202', '222', '242', '55', '77', '900', '998'))
        self.assertEqual(switch.vtagged, {'1': (0, 0, 0, 0, 0, 0, 0, 0, 0),
                                          '10': (0, 64, 137, 15, 0, 0, 0, 0, 0),
                                          '182': (0, 64, 137, 15, 0, 0, 0, 0, 0),
                                          '2': (127, 191, 251, 15, 0, 0, 0, 0, 0),
                                          '20': (0, 64, 201, 15, 0, 0, 0, 0, 0),
                                          '202': (0, 64, 137, 15, 0, 0, 0, 0, 0),
                                          '222': (0, 64, 137, 15, 0, 0, 0, 0, 0),
                                          '242': (0, 64, 137, 15, 0, 0, 0, 0, 0),
                                          '55': (0, 64, 201, 15, 0, 0, 0, 0, 0),
                                          '77': (0, 64, 203, 15, 0, 0, 0, 0, 0),
                                          '900': (0, 64, 137, 15, 0, 0, 0, 0, 0),
                                          '998': (0, 64, 137, 15, 0, 0, 0, 0, 0),
                                          })
        self.assertEqual(switch.vuntagged, {'1': (127, 191, 253, 15, 0, 0, 0, 0, 0),
                                            '10': (0, 0, 0, 0, 0, 0, 0, 0, 0),
                                            '182': (0, 0, 0, 0, 0, 0, 0, 0, 0),
                                            '2': (128, 64, 0, 0, 0, 0, 0, 0, 0),
                                            '20': (0, 0, 2, 0, 0, 0, 0, 0, 0),
                                            '202': (0, 0, 0, 0, 0, 0, 0, 0, 0),
                                            '222': (0, 0, 0, 0, 0, 0, 0, 0, 0),
                                            '242': (0, 0, 0, 0, 0, 0, 0, 0, 0),
                                            '55': (0, 0, 0, 0, 0, 0, 0, 0, 0),
                                            '77': (0, 0, 0, 0, 0, 0, 0, 0, 0),
                                            '900': (0, 0, 0, 0, 0, 0, 0, 0, 0),
                                            '998': (0, 0, 0, 0, 0, 0, 0, 0, 0)})
        check = {
            1: (['2'], ['1']),
            2: (['2'], ['1']),
            3: (['2'], ['1']),
            4: (['2'], ['1']),
            5: (['2'], ['1']),
            6: (['2'], ['1']),
            7: (['2'], ['1']),
            8: ([], ['2']),
            9: (['2'], ['1']),
            10: (['2'], ['1']),
            11: (['2'], ['1']),
            12: (['2'], ['1']),
            13: (['2'], ['1']),
            14: (['2'], ['1']),
            15: (['10', '182', '20', '202', '222', '242', '55', '77', '900', '998'], ['2']),
            16: (['2'], ['1']),
            17: (['10', '182', '2', '20', '202', '222', '242', '55', '77', '900', '998'], ['1']),
            18: (['2', '77'], ['20']),
            19: ([], ['1']),
            20: (['10', '182', '2', '20', '202', '222', '242', '55', '77', '900', '998'], ['1']),
            21: (['2'], ['1']),
            22: (['2'], ['1']),
            23: (['2', '20', '55', '77'], ['1']),
            24: (['10', '182', '2', '20', '202', '222', '242', '55', '77', '900', '998'], ['1']),
            25: (['10', '182', '2', '20', '202', '222', '242', '55', '77', '900', '998'], ['1']),
            26: (['10', '182', '2', '20', '202', '222', '242', '55', '77', '900', '998'], ['1']),
            27: (['10', '182', '2', '20', '202', '222', '242', '55', '77', '900', '998'], ['1']),
            28: (['10', '182', '2', '20', '202', '222', '242', '55', '77', '900', '998'], ['1']),
        }
        for i in range(1, 29):
            self.assertEqual(switch._vlans_ports(i), check[i], 'failed vlans for port {}'.format(i))

    @unittest.skipUnless(os.path.isfile(PseudoSnmp.path + '/' + 'Extreme-X440.snmpwalk'),
                         'file Extreme-X440.snmpwalk not found')
    def test_load_extreme_x440(self):
        session = PseudoSnmp('Extreme-X440.snmpwalk')
        session.start()
        switch = SwitchFactory.factory(host=session)
        switch.load()

        self.assertEqual(switch.mac, "00:04:96:99:ea:c5")
        self.assertEqual(switch.vlans, ('1', '2', '20', '4095', '55', '77'))



class TestSwitchInspect(unittest.TestCase):
    """
    Full run of all switch properties and data usually loaded and consumed by Models and Views.
    """
    def test_interface(self):
        # when no file exists
        rf = RequestFactory()
        # check invalid files
        self.assertRaises(ValueError, inspect_service, request=rf.get('/inspect/HP/public?mock=1'), target="HP", community="public")
        # check invalid hosts
        output = inspect_service(request=rf.get('/probe/HP/public'), target="HP", community="public")
        self.assertEqual(True, output.content.startswith(b"ERROR"))

    @unittest.skipUnless(os.path.isfile(PseudoSnmp.path + '/' + 'HPE-JG977A.snmpwalk'),
                         'file HPE-JG977A.snmpwalk not found')
    def test_inspect_hpe_jg977a(self):
        rf = RequestFactory()
        output = inspect_service(rf.get('/inspect/HPE-JG977A.snmpwalk/public?mock=1'), "HPE-JG977A.snmpwalk", "public")
        self.assertEqual(False, output.content.startswith(b"ERROR"))
        self.assertEqual(output.status_code, 200)


if __name__ == '__main__':
    unittest.main()

import logging
import math
import sys

import netsnmp

from netstatus.lib.snmp import SNMP
from netstatus.settings import Settings
from netstatus.lib.switch import switchlib
from .switchlib import *

"""
    Switch is the main class used to get all main attributes of a switch: vlan, ports states, serial number, etc.
    As softly based on 3Com 4500G / Comware series, other types of switches must extend this class and overwrite 
    the needed OIDs. 
    Most vendors don't implement IETF version of interesting parts of MIB tree, like POE, VLAN, interface vlan. 
    Even some models don't implement all proprietary tree from a manufacturer.
    Therefore, we need to go deep and guess how it works for each model and vendor. 
    This class is not that big, but everything with OIDs are pretty much painful, specially when you need to support
    several vendors and models. Most data has different types of representation and need to be converted to a common
    standard.

    Examples of common types of OIDs to be changed:
        _oids_intvlan
            # hwdot1qVlanIpAddress - "IP address of interface."
            .1.3.6.1.4.1.43.45.1.2.23.1.2.1.2.1.3
            # hwdot1qVlanIpAddressMask - "IP address mask of interface."
            .1.3.6.1.4.1.43.45.1.2.23.1.2.1.2.1.4
            # hwVlanInterfaceAdminStatus - "Status of VLAN virtual interfaces." (up/down, 1/2)
            .1.3.6.1.4.1.43.45.1.2.23.1.2.1.2.1.5
        _oids_vlans 
            'vlans':    '.1.3.6.1.4.1.43.45.1.2.23.1.2.1.1.1.1',
            'tagged':   '.1.3.6.1.4.1.43.45.1.2.23.1.2.1.1.1.17',
            'untagged': '.1.3.6.1.4.1.43.45.1.2.23.1.2.1.1.1.18',
        _ifVLANType (trunk, hybrid, access) - not all implement this variant, as it doesn't appear in the IETF version.
            .1.3.6.1.4.1.43.45.1.2.23.1.1.1.1.5
        _oids_ifexists_intvlan
            .1.3.6.1.4.1.43.45.1.2.23.1.2.1.1.1.7'  # 1/2 = true/false for each vlan
"""
# todo: change this to a configuration file / table
SWITCH_MANAGED_VLAN = 20


class Switch:
    """
     Mother class. Basically all main functions stays here because only few
     OIDs varies for each model / vendor, thus just a few adjustments are
     enough to get rid of those differences, which are made in the subclass
     implementation, including setup new OIDs values and function redefinition
    """
    # basic information from a switch which are usually available without specific MIB tree
    _oids_geral = {
        'name':     '.1.3.6.1.2.1.1.5.0',
        'descr':    '.1.3.6.1.2.1.1.1.0',
        'uptime':   '.1.3.6.1.2.1.1.3.0',
        'mac':      '.1.3.6.1.2.1.17.1.1.0',
        'stp':      '.1.3.6.1.2.1.17.2.7.0',
    }
    # _fab_var is added to the end of _oids_fab. Sometimes, we don't need to change all the OIDs,
    # just the last part where this switch model stores some of its data.
    _fab_var = '2'
    _oids_fab = {
        'physical':     '.1.3.6.1.2.1.47.1.1.1.1.7.',   # entPhysicalName
        'soft_version': '.1.3.6.1.2.1.47.1.1.1.1.10.',  # software version
        'serial':       '.1.3.6.1.2.1.47.1.1.1.1.11.',  # serial number
        'vendor':       '.1.3.6.1.2.1.47.1.1.1.1.12.',  # manufacturer / vendor #  entPhysicalMfgName
        'model':        '.1.3.6.1.2.1.47.1.1.1.1.13.',  # model
    }
    _oids_vlans = {
        'vlans':    '.1.3.6.1.4.1.43.45.1.2.23.1.2.1.1.1.1',
        'tagged':   '.1.3.6.1.4.1.43.45.1.2.23.1.2.1.1.1.17',
        'untagged': '.1.3.6.1.4.1.43.45.1.2.23.1.2.1.1.1.18',
    }
    _oids_poe = {
        'poeadmin': '.1.3.6.1.2.1.105.1.1.1.',
        'poempower': '.1.3.6.1.4.1.43.45.1.10.2.14.1.1.3',
        'poesuffix': '1',
    }
    management_vlan = Settings.MANAGEMENT_VLAN
    _map_baseport_ifindex = {}

    @classmethod
    def is_compatible(cls, descr):
        return True

    def __init__(self, host, community='public', version=2):
        # default for 3Com / HP (HPN)
        self._mask = mask_bigendian
        self.comunidadew = 'private'
        self.ip = ''  # future: get it from interface vlan
        self.portas = {}
        self.vlans = []
        self.vtagged = {}
        self.vuntagged = {}
        self.intvlan = {}
        self.macs = ()
        self.macs_filtered = ()
        self.ip_mac = {}
        self.lldp = {}
        self.uplink = ()
        self.name = ''
        self.soft_version = ''
        self.serial = ''
        self.vendor = ''
        self.model = ''
        self.physical = ''
        self.mac = ''
        self.stp = 0

        if not host:
            return

        if isinstance(host, str):
            self.host = host
            self.comunidade = community
            self.sessao = SNMP(host, community, version)
            self.sessao.start()

        if isinstance(host, SNMP):
            self.sessao = host
            self.host = host.host
            self.comunidade = host.community

        # this index is per switch model, so a class attribute should be fine.
        if not self._map_baseport_ifindex:
            self.map_baseport()

    def set_start(self, comunidadew='private', version=2, force=False):
        """
        Create a second SNMP session for writing into the switch.
        Only uses the same session connection if both community are equal
        :param comunidadew:
        :param version: usually 2. Only change this if really needs to.
        :param force:
        :return:
        """
        if self.sessaow is not None and not force:
            return
        if self.comunidade == comunidadew:
            self.sessaow = self.sessao
            return
        self.comunidadew = comunidadew
        self.sessaow = SNMP(self.host, comunidadew, version)
        self.sessaow.start()

    def _map_bport_ifidx(self, port):
        return self._map_baseport_ifindex[port] if port in self._map_baseport_ifindex else port

    def map_baseport(self):
        """
        Get the relation baseport <-> ifIndex. Used to access some vlans, pvid and other data index as baseport instead
        ifIndex. Most smalls switches has a relation 1:1 (baseport = 1, ifIndex = 1). Go through the
        dot1dBasePortIfIndex OID

        :return: nothing. Sets the object variable _map_baseport_ifindex
        """
        oid_portifindex = '.1.3.6.1.2.1.17.1.4.1.2'
        self._map_baseport_ifindex = {}
        for (_poid, _type, _ifindex) in self.sessao.walk(oid_portifindex):
            bidx = _poid.split('.')[-1]
            self._map_baseport_ifindex[int(_ifindex)] = int(bidx)

    def get_geral(self):
        """
        Get basic info of this snmp equipment and uses the name in the OID dictionary as object attribute.
        """
        tmp = {}
        for k, v in self._oids_fab.items():
            tmp[k] = v + self._fab_var
        for k, v in self._oids_geral.items():
            tmp[k] = v
        oids = list(tmp.values())
        values = snmp_values(self.sessao.get(oids))

        for x, y in list(zip(tmp.keys(), values)):
            setattr(self, x, y)
        self.mac = format_mac(self.mac)
        self.stp = int(self.stp)

    def load(self):
        """
        Load every interesting characteristics, usually separated into several different methods,
         except the mac-ip list.
        """
        self.get_geral()
        self.get_vlans()
        logging.debug('-- self.vtagged: ' + str(self.vtagged))
        logging.debug('-- self.vuntagged: ' + str(self.vuntagged))

        self.get_ports()
        logging.debug('-- ports: ' + str(self.portas))

        self.get_lldp_neighbors()
        logging.debug(('-- after get_lldP_neighbor(): ', self.lldp))
        logging.debug(('   +---> uplinks: ', self.uplink))

        self.get_mac_list()
        logging.debug(('-- mac list: ', *self.macs))

    # mapa de vlans tagged (egress) e untagged. O mapa usa basePort como referência
    def get_vlans(self):
        """
        Get Egress (or Tagged) and Untagged vlans from switch as dictionaries.
        Tagged vlans for a port are obtained later, with _vlans_ports()
        Some switches has egress portlist instead (has both tagged and untagged)
        Problems: each switch store vlans in different OIDs, you need to dig out that info.
        Some switches brings the vlan list out of order or the value into the OID body instead the VALUE part of the
        request. Huawei switches store all possible vlans, even if not created, so we need to filter out that too.
        :return: set tagged and untagged vlans as dictionary vlan (key) = tuple(integer,)
        """
        self.vlans = tuple(sorted([v[netsnmp.OID].split('.')[-1] for v in self.sessao.walk(self._oids_vlans['vlans'])]))
        self.vtagged = {}
        self.vuntagged = {}

        logging.debug('-- VLANS: ' + ','.join(self.vlans))
        """
        Vlans are represented as a byte string where the bit position means the port.
        This will be converted to a dictionary where key = vlan number  and  value is a tuple with ports as integer
        Filters out vlans not created.
        Be careful with lots of GET message in the same request. If the response becomes too big, SNMP server returns
        error to us.
        x = temp; helps creating the OIDs for each VLAN
        y = OID 
        z = dictionary, last OID part = Value cleaned
        k = VLAN number
        v = hex string (bytes = 2 char separated by spaces). Each bit represents a port
        w = a 'v' part converted to integer.
        """
        self.vtagged = {
            k: tuple(int(w, 16) for w in v.strip().replace('\n', '').split(' '))
            for z in (snmp_values_dict(self.sessao.get(y)) for y in
                      [self._oids_vlans['tagged'] + '.' + x for x in self.vlans]) for k, v in z.items()
        }
        self.vuntagged = {
            k: tuple(int(w, 16) for w in v.strip().replace('\n', '').split(' '))
            for z in (snmp_values_dict(self.sessao.get(y)) for y in
                      [self._oids_vlans['untagged'] + '.' + x for x in self.vlans]) for k, v in z.items()
        }

    def _vlans_ports(self, port):  # , pvid):
        """
        Get VLANS associate to a port. Need to call get_vlans() before this one.
        There are list of vlans with ports, this way the port will be searched to discover the vlans
        :param port: the switch port
        :return: tuple with tagged and untagged vlans as string each
        """
        vtag = []
        vuntag = []
        for j in self.vlans:
            t = self.portlist(self.vtagged[j], port)
            u = self.portlist(self.vuntagged[j], port)
            if t > 0 and u == 0:
                vtag += [j]
            if u > 0:
                vuntag += [j]
        return vtag, vuntag

    def portlist(self, portlist, port):
        """
        Tells if the port has a vlan or not.
        Interprets PortList, which each bit represents a port. A switch may use little endian or big endian to store
        this data.

        rfc2674-qbridge.mib
        DESCRIPTION
            "Each octet within this value specifies a set of eight ports, with the first octet specifying ports 1
            through 8, the second octet specifying ports 9 through 16, etc.
            Within each octet, the most significant bit represents the lowest numbered port, and the least significant
            bit represents the highest numbered port.  Thus, each port of the bridge is represented by a single bit
            within the value of this object.  If that bit has a value of '1' then that port is included in the set of
            ports; the port is not included if its bit has a value of '0'."
        """
        nport = int(port) - 1
        if nport < 0:
            return 0
        idx = nport // 8
        mask = self._mask(nport)  # set in __init__
        return portlist[idx] & mask if idx < len(portlist) else 0

    #       dot1dStpPortEnable                dot1dStpPortState,
    #       (1,2 = ena, disable)              (1=disabled, 2=blocking, 3=listening, 4=learning, 5=forwarding, 6=broken)
    #               stp_admin                       stp_state                   stp_pvid
    _oids_stp = ('.1.3.6.1.2.1.17.2.15.1.4.', '.1.3.6.1.2.1.17.2.15.1.3.', '.1.3.6.1.2.1.17.7.1.4.5.1.1.')

    def _snmp_ports_stp(self, port):
        port = str(port)
        oidlist = [v + port for v in self._oids_stp]
        ret = []
        for i in oidlist:
            ret += self.sessao.get(i)
        return ret

    # Data: INTEGER {vLANTrunk(1), access(2), hybrid(3), fabric(4)}
    _ifVLANType = '.1.3.6.1.4.1.43.45.1.2.23.1.1.1.1.5'

    def _snmp_ports_vtype(self, port):
        port = str(port)
        oidlist = ['.'.join([self._ifVLANType, port])]
        ret = []
        for i in oidlist:
            ret += self.sessao.get(i)
        return ret

    # poe_admin poe_status poe_class   poe_mpower
    def _oid_poe(self, port):
        port = str(port)
        return [self._oids_poe['poeadmin'] + v + '.' + self._oids_poe['poesuffix'] + '.' + port for v in
                ('3', '6', '10')] \
               + [self._oids_poe['poempower'] + '.' + self._oids_poe['poesuffix'] + '.' + port]

    def _snmp_ports_poe(self, port):
        """
        Get poe_admin, poe_status, poe_class, poe_mpower.
        Splitted into 2 methods: the first creates the OIDs, which changes among switches.
        The second gets them. Some (D-LINK) may overwrite this to change the returned value or something else.
        :param port: switch port, as string
        :return:
        """
        oidlist = self._oid_poe(port)
        return self.sessao.get(oidlist)

    # Testa se a port é uma Interface VLAN
    # Significado de cada um desses valores:
    # https://www.iana.org/assignments/ianaiftype-mib/ianaiftype-mib
    @staticmethod
    def _is_port_intvlan(iftype):
        # l3ipvlan = 136, ipForward = 142 (DLINK)
        return True if iftype in (136, 142) else False

    @staticmethod
    def _is_port_ether(iftype):
        # ethernetCsmacd = 6, gigabitEthernet = 117
        return True if iftype in (117, 6) else False

    # preferência por filtrar apenas portas ethernet (ignorar int. vlans e outras interfaces)
    def get_ports(self):
        """
        Get the switches ports, filtering to get only ether type - sometimes interface vlan appear here, it depends
        on the switch.
        :return: set a dictionary indexed by port number
        """
        # Checking with ifType if the port is ethernet type (may be interface vlan or anything else).
        # avoids calling get_port_ether() for non ethernet type.
        oid_iftype = '.1.3.6.1.2.1.2.2.1.3'
        for (_oid, _type, _value) in self.sessao.walk(oid_iftype):
            porta = int(_oid[(len(oid_iftype) + 1):])
            iftype = int(_value)

            if self._is_port_ether(iftype):  # and port in self._map_baseport_ifindex:
                self.portas[porta] = self.get_port_ether(porta)

    _oids_intvlan = (
        '.1.3.6.1.4.1.43.45.1.2.23.1.2.1.2.1.3',  # hwdot1qVlanIpAddress - "IP address of interface."
        '.1.3.6.1.4.1.43.45.1.2.23.1.2.1.2.1.4',  # hwdot1qVlanIpAddressMask - "IP address mask of interface."
        '.1.3.6.1.4.1.43.45.1.2.23.1.2.1.2.1.5',  # hwVlanInterfaceAdminStatus -
        # "Status of VLAN virtual interfaces." (up/down, 1/2)
    )
    _oids_ifexists_intvlan = '.1.3.6.1.4.1.43.45.1.2.23.1.2.1.1.1.7'  # 1/2 = true/false for each vlan

    def get_intvlan(self):
        for (_oid, _type, _value) in self.sessao.walk(self._oids_ifexists_intvlan):
            if _value == '2':
                continue
            vlan = _oid[len(self._oids_ifexists_intvlan) + 1:]
            valores = snmp_values(self.sessao.get([v + '.' + vlan for v in self._oids_intvlan]))
            # interface vlan set up but without IP. It may happen if you enters it and forget to undo it
            if valores[0] == '0.0.0.0':
                continue
            self.intvlan[int(vlan)] = tuple(valores)

    def get_port_ether(self, porta):
        """
        Get internet / ethernet ports (not interface vlan or other types)
        :param porta: must be int
        :return:
        """
        # some functions need this as integer, so we will do it only once.
        i = str(porta)

        # Order of OIDs:
        # ifdesc ifmtu ifspeed ifphys ifadmin ifoper iflast ifindis ifoutdis 
        oidlist = ['.1.3.6.1.2.1.2.2.1.' + v + '.' + i for v in ('2', '4', '5', '6', '7', '8', '9', '13', '19')]
        # ifduplex ifalias  ifHCInOctets ifHCOutOctets, ifInOctets, ifOutOctets
        oidlist += ['.1.3.6.1.2.1.10.7.2.1.19.' + i, '.1.3.6.1.2.1.31.1.1.1.18.' + i,
                    '.1.3.6.1.2.1.31.1.1.1.6.' + i, '.1.3.6.1.2.1.31.1.1.1.10.' + i,
                    '.1.3.6.1.2.1.2.2.1.10.' + i, '.1.3.6.1.2.1.2.2.1.16.' + i]
        result = self.sessao.get(oidlist)

        values = snmp_values(result, filter_=True)
        ifdesc, ifmtu, ifspeed, ifphys, ifadmin, ifoper, iflast, ifindis, \
        ifoutdis, ifduplex, ifalias, ifhcinoct, ifhcoutoct, ifinoct, ifoutoct = values
        ifinoct  = ifhcinoct if ifinoct < ifhcinoct else ifinoct
        ifoutoct = ifhcoutoct if ifoutoct < ifhcoutoct else ifoutoct
        # Specific things for each vendor / model. Uses separated methods for easier overload.
        result = self._snmp_ports_stp(i)
        result += self._snmp_ports_poe(i)
        result += self._snmp_ports_vtype(i)
        values = snmp_values(result, filter_=True)
        stp_admin, stp_state, stp_pvid, poe_admin, poe_status, poe_class, poe_mpower, vtype = values
        del result, oidlist, values

        ifspeed = int(ifspeed)
        ifspeedn = int(ifspeed / 1000000) if ifspeed > 0 else ifspeed
        # \-- iflast, when the interface last changed, format TimeTicks =  0:00:00.00
        iflast = int(sum([part * base for part, base in
                          zip((86400, 3600, 60, 1), map(float, iflast.split(':')))]) * 100)
        # Some switches are too much verbose on interface description. Altough the max length check should be done by
        # other class, it won't know how handle the information contained here except trunking the string to a certain
        # length.
        # So, specially for D-LINKs, any subclass should rewrite this description to best fit its purpose of describing
        # the port.
        ifdesc = self._format_ifdesc(ifdesc)

        vtag = []
        vuntag = []
        # 2 = port access, vtag and vuntag are not applicable.
        if vtype != '2':
            vtag, vuntag = self._vlans_ports(porta)
            if len(vtag) > 4090:  # probably trunking port with 'permit vlan all' and all vlans created.
                vtag = [4095, ]

        logging.debug('-- port {} ({}), vtag = "{}", vuntag = "{}"'.format(str(porta), str(ifdesc), vtag, vuntag))
        return {
            'speed': ifspeedn,
            'duplex': int(ifduplex),
            'admin': int(ifadmin),
            'oper': int(ifoper),
            'lastchange': iflast,
            'discards_in': int(ifindis),
            'discards_out': int(ifoutdis),
            'oct_in': int(ifinoct),
            'oct_out': int(ifoutoct),
            'stp_admin': int(stp_admin),
            'stp_state': int(stp_state),
            'poe_admin': int(poe_admin),
            'poe_detection': self._conv_poe_status(poe_status),
            'poe_class': int(poe_class),
            'poe_mpower': int(poe_mpower),
            'mac_count': 0,
            'pvid': stp_pvid,
            'tagged': vtag,
            'untagged': vuntag,
            # data: will be defined somewhere else.
            'nome': ifdesc,
            'alias': ifalias,
        }

    def _conv_poe_status(self, poe_status):
        return int(poe_status)

    _oid_macs = ('.1.3.6.1.2.1.17.7.1.2.2.1.2',)

    def get_mac_list(self, filterLLDP=True):
        """
        Get a MAC list. Based on Q-BRIDGE-MIB :: dot1qTpFdbPort
        :param filterLLDP: don't store macs in uplinks
        :return: ((porta, mac, vlan),)
        """
        macs = self.sessao.walk(self._oid_macs)
        logging.debug("macs = {}".format(macs))
        for (oid, _type, port) in macs:
            oid = oid.strip().split('.')
            # logging.debug("oid + port = {}  ++  {}".format(oid, port))
            port = self._map_bport_ifidx(int(port))
            if filterLLDP and port in self.uplink:
                continue
            # get VLAN and MAC from OID
            vlan = int(oid[14])
            mac = '{:02x}:{:02x}:{:02x}:{:02x}:{:02x}:{:02x}'.format(*(int(v) for v in oid[15:]))
            # blacklist or configuration like static, interface vlan, etc
            if port == 0:
                self.macs_filtered += ((port, mac, vlan),)
            else:
                self.macs += ((port, mac, vlan),)

    def _lldp_is_uplink(self, lport, lldp_port):
        """
            Filters out lldp ports which aren't switches, like voips and wireless routers.
            You may not need this kind of filter. This checks some possible configurations like POE on, PVID and
            cabenable characteristics. This may not work in every environment or get overwritten.
            Returns: True if switch, False if something else.

                lldpRemSysCapEnabled (.1.0.8802.1.1.2.1.4.1.1.12)
                    SYNTAX  BITS {
                            other(0),
                            repeater(1),
                            bridge(2),
                            wlanAccessPoint(3),
                            router(4),
                            telephone(5),
                            docsisCableDevice(6),
                            stationOnly(7)
                    }

        """
        # if "00" (hex), then is voip or something without routing capabilites.
        # basically, 0 = other, 36 = bridge & phone (Yealink), &4 = bridge
        logging.debug("[{} / {}] lldp_filter_is_uplink: port {} :: capenable = {:d}".
                      format(self.name, self.host, lport, lldp_port['capenable']))
        # VOIP or without routing capability
        if lldp_port['capenable'] == 0 or lldp_port['capenable'] == 36 or lldp_port['capenable'] & 4 == 1:
            logging.debug("--           +-----> capenable condition: returning FALSE")
            return False
        # guessing any voip with external power source.
        if lldp_port['portsubtype'] == '3' and lldp_port['chassissubtype'] == '5':
            logging.debug("--> [{} / {}] lldp_filter_is_uplink: poe port {} :: subtype/chassi = 3/5".
                          format(self.name, self.host, lport))
            return False
        # delegating to a dynamic function able to do custom checks.
        extra_uplink_test = getattr(switchlib, Settings.LLDP_IS_UPLINK_EXTRA) if Settings.LLDP_IS_UPLINK_EXTRA else None
        return extra_uplink_test(self, lport, lldp_port) if extra_uplink_test else False

    # mudanças para detectar melhor o que há na outra ponta
    # lldpRemChassisId
    _oids_lldp_mac = '.1.0.8802.1.1.2.1.4.1.1.5'
    _oids_lldp = {
        'chassissubtype':   '.1.0.8802.1.1.2.1.4.1.1.4',
        'portsubtype':      '.1.0.8802.1.1.2.1.4.1.1.6',
        'rport':            '.1.0.8802.1.1.2.1.4.1.1.7',
        'remportdesc':      '.1.0.8802.1.1.2.1.4.1.1.8',
        'remsysname':       '.1.0.8802.1.1.2.1.4.1.1.9',
        'capsupported':     '.1.0.8802.1.1.2.1.4.1.1.11',
        'capenable':        '.1.0.8802.1.1.2.1.4.1.1.12',
    }
    _oids_lldp_local = {
        'locportdesc': '.1.0.8802.1.1.2.1.3.7.1.4',
    }

    def get_lldp_neighbors(self):
        """
        Get neighbors through LLDP.
        :return: [{lport: {rmac, rporta, locportdesc, remsysname, remportdesc}},]
        """
        self.lldp = {}
        logging.debug("--> : [{} / {}] LLDP: self.lldp {}.".format(self.name, self.host, str(self.lldp)))
        neighbors = self.sessao.walk(self._oids_lldp_mac)
        for (oid, tipo, _rmac) in neighbors:
            oid = oid.replace(self._oids_lldp_mac, '').split('.')
            # Some devices register the port multiple times, only differs by a temporal key in the OID.
            # We need to filter that.
            lport = int(oid[2])
            logging.debug("[{} / {}] LLDP: port {}.".format(self.name, self.host, lport))
            if lport in self.lldp:
                logging.debug(
                    "--> NOTE: [{} / {}] LLDP: port {} already registered.".format(self.name, self.host, lport))
                continue
            snmpId = oid[1]
            # other data needed to identify the relation with neighbors
            res = {}
            for k, oid in self._oids_lldp_local.items():
                logging.debug("{} = {}".format(k, self.sessao.get('.'.join((oid, str(lport))))[0][2]))
                res[k] = snmp_values(self.sessao.get('.'.join((oid, str(lport)))))[0]

            for k, oid in self._oids_lldp.items():
                # D-LINK gives some errors, so we need to do some adjusts
                res[k] = snmp_values(self.sessao.getnext('.'.join((oid, snmpId, str(lport)))))[0]

            """
            lldpRemPortIdSubtype
            interfaceAlias(1), portComponent(2), macAddress(3), networkAddress(4), 
            interfaceName(5), agentCircuitId(6), local(7)

            LldpChassisIdSubtype
            1 = chassisComponent (entPhysicalAlias)
            2 = interfaceAlias (ifAlias)
            3 = portComponent (entPhysicalAlias - backplane)
            4 = macAddress
            5 = networkAddress (IP de uma interface)
            6 = interfacename (ifName)
            7 = local
            """
            logging.debug("get_lldp_neighbor: chassissubtype = {}".format(res['chassissubtype']))
            if res['chassissubtype'] == '4':
                rmac = format_mac(_rmac)

            elif res['chassissubtype'] == '5':
                logging.debug('--            +++----->  _rmac = "{}"'.format(_rmac))
                # VOIPs Yealink let the field _oids_lldp_mac empty.
                # They set chassissubtype as networkAddress, but don't put any other type of information.
                # However: rport e portsubtype has the MAC data of the remote port.
                if _rmac == '""':
                    logging.debug("--> NOTE: [{} / {}] LLDP: lport {}: rmac is null.".
                                  format(self.name, self.host, lport))
                    continue
                rmac = '{:d}.{:d}.{:d}.{:d}'.format(*[int(v, 16) for v in _rmac.strip(' "').split(' ')[-4:]])

            elif res['chassissubtype'] == '7':
                # Ignoring local ports this time. We need to find a device for that to test this.
                # usually local ports are not numeric and we storage only numbers for ports.
                continue
            else:
                rmac = _rmac.strip()

            try:
                if len(res['capenable']) > 1:
                    res['capenable'] = int(res['capenable'].strip(), 16)
                else:
                    res['capenable'] = ord(res['capenable'])
            except:
                pass
            """
             -- RPORT -> the port of our neighbor

             values for LldpPortIdSubtype (only few implemented):
             1 = interfaceAlias (ifAlias)
             2 = portComponent (entPhysicalAlias)
             3 = macAddress (port mac, we can guess, for switches, the last byte will be the port number. Should work
                    for switches with up 48 ports. 
             4 = networkAddress
             5 = interfaceName (ifName)
             6 = agentCircuitId
             7 = local
            """
            logging.debug('portsubtype = {}'.format(res['portsubtype']))
            if res['portsubtype'] == '5':  # HP / 3Com
                tmp = res['rport'].split('/')
                if tmp[0][-1] == '1':
                    rporta = tmp[2]
                else:
                    # multi layer switch
                    rporta = ''.join((tmp[0][-1], tmp[2].zfill(2)))
            elif res['portsubtype'] == '3':  # DLINK / VOIPs
                rporta = str(int(res['rport'].rstrip().split(' ')[-1], 16) + 1)
            else:
                rporta = res['rport']

            res['rport'] = rporta
            res['rmac'] = rmac
            self.lldp[lport] = res
            try:
                if self._lldp_is_uplink(str(lport), res):
                    self.uplink += (lport,)
            except Exception as e:
                logging.debug('-- #### Uplink Exception #### ', e)
                self.uplink += (lport,)
        return self.lldp

    # ipNetToMediaPhysAddress - ipv4
    _oids_ip2mac = '.1.3.6.1.2.1.4.22.1.2'

    def get_ip_mac(self):
        for (_oid, _type, _value) in self.sessao.walk(self._oids_ip2mac):
            # It may be a MAC-ADDRESS string that has valid characteres.
            # This happens when listing MACS stored in switches. We may 
            # need use HINT from MIB tree to figure out this more correctly
            # specially with other OIDs.
            # print("-- mac ({}): {}".format(_type, _value))
            if _type == "STRING":
                mac = '{:02x}:{:02x}:{:02x}:{:02x}:{:02x}:{:02x}'.format(*(ord(v) for v in _value.strip('"')))
            else:
                # print("-- mac before ({}): {}".format(_type, _value))
                mac = ':'.join(_value.strip('" ').lower().split(' '))
                # print("-- mac after ({}): {}".format(_type, _value))
            # regroup the last 4 digits from OID, which is the IP. The 5º is the port, no interest right now.
            ip = '.'.join(_oid.split('.')[-4::])
            logging.debug("-- ip == mac :: {} == {}".format(ip, mac))
            self.ip_mac[mac] = ip


    # Setando variáveis pré-definidas no switch. 
    # É bem limitado, além de ter que anotar o tipo de dado que irá para aquele OID.
    # assumindo casos 1 e 2, que tem OID simples.
    _set_vars = {
        'pvid': {'oid': '.1.3.6.1.2.1.17.7.1.4.5.1.1', 'param': True, 'value_type': 'u', 'alias': 'dot1qPvid'},
        'admin': {'oid': '.1.3.6.1.2.1.2.2.1.7', 'param': True, 'value_type': 'u', 'alias': 'ifAdminStatus'},
    }

    def _set(self, func, param, value):
        try:
            oid = self._set_vars[func]['oid']
        except:
            raise Exception('Função {} não existe'.format(func))

        if self._set_vars[func]['param']:
            if not param:
                raise Exception('Função {} precisa de parâmetros'.format(func))
            if type(param) is not str:
                param = str(param)
            oid = oid + '.' + param

        if self.sessaow is None:
            raise Exception('Sessão de escrita não inicializada')
        self.sessaow.set(oid, value, self._set_vars[func]['value_type'])

    # TODO: desenvolver funções que gravam (write) no SNMP, alterando as configurações do switch.
    # abaixo há alguns exemplos, mas não foram testados. 

    # essas serão as funções públicas param são para aqueles casos que há coisas a acrescentar no final do OID. São 3
    # situações: aquelas que não precisam, as que precisam, e aquelas que precisam mas envolvem variáveis no meio,
    # como na família LLDP.
    def set_param(self, func, param, value):
        self._set(func, param, value)

    def set(self, func, value):
        self._set(func, False, value)

    def set_pvid(self, porta, value):
        if value > 4095 or value < 0:
            raise Exception('set_pvid: pvid fora dos limites')
        self._set('pvid', porta, value)

    # Shutdown da port. Valores: 1, 2, 3 :: up, down, testing
    def set_admin(self, porta, value):
        if value not in (1, 2, 3):
            raise Exception('set_admin: valor de status incorreto')
        self._set('admin', porta, value)

    def _format_ifdesc(self, ifdesc):
        return ifdesc

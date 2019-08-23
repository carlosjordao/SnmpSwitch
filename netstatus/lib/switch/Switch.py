import logging
import math

from netstatus.lib.snmp import SNMP
from netstatus.lib.switch.switchlib import _mask_bigendian
from .switchlib import *

"""
    Switch is the main class used to get all main attributes of a switch: vlan, ports states, serial number, etc.
    Softly based on 3Com 4500G series, other types of switches must extend this class and overwrite the needed features.
    Most vendors don't implement ISO version of interesting MIB tree, like POE, VLAN, interface vlan. We need to 
    go deep and guess how it works for each model and vendor. 
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
        # hwifVLANType
        _ifVLANType
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
    # todo: refactor this
    # basic information from a switch which are usually available without specific MIB tree
    _oids_geral = {
        'nome': '.1.3.6.1.2.1.1.5.0',
        'descr': '.1.3.6.1.2.1.1.1.0',
        'uptime': '.1.3.6.1.2.1.1.3.0',
        'mac': '.1.3.6.1.2.1.17.1.1.0',
        'stp': '.1.3.6.1.2.1.17.2.7.0',
    }
    """
     específico de  cada  fabricante. Tem algumas variações, cujo  índice 
     varia  para cada modelo, armazenada em _fab_var. É possível criar um
     mecanismo  para  descobrir esse  índice também. No  momento ele está 
     codificado em cada subclasse, que representa um modelo do switch.
    """
    _oids_fab = (
        '.1.3.6.1.2.1.47.1.1.1.1.7.',  # físico
        '.1.3.6.1.2.1.47.1.1.1.1.10.',  # versão software
        '.1.3.6.1.2.1.47.1.1.1.1.11.',  # serial
        '.1.3.6.1.2.1.47.1.1.1.1.12.',  # fabricante
        '.1.3.6.1.2.1.47.1.1.1.1.13.',  # modelo
    )
    _oids_vlans = {
        'vlans': '.1.3.6.1.4.1.43.45.1.2.23.1.2.1.1.1.1',
        'tagged': '.1.3.6.1.4.1.43.45.1.2.23.1.2.1.1.1.17',
        'untagged': '.1.3.6.1.4.1.43.45.1.2.23.1.2.1.1.1.18',
    }
    _oids_poe = {
        'poeadmin': '.1.3.6.1.2.1.105.1.1.1.',
        'poempower': '.1.3.6.1.4.1.43.45.1.10.2.14.1.1.3',
        'poesuffix': '1',
    }
    management_vlan = globals()['SWITCH_MANAGED_VLAN']
    _map_baseport_ifindex = {}

    @classmethod
    def is_compatible(cls, descr):
        return True

    def __init__(self, host, community='public', version=2):
        if not host:
            return

        # default for 3Com / HP (HPN)
        self._mask = _mask_bigendian
        self._fab_var = '2'
        self.comunidadew = 'private'
        self.ip = ''  # future: get it from interface vlan
        self.alias = ''  # todo: refactor this
        self.board = {}  # get_geral() fill this
        self.portas = {}
        self.vlans = []
        self.vtagged = {}
        self.vuntagged = {}
        self.__lldp = {}
        self.intvlan = {}
        self.macs = ()
        self.macs_filtered = ()
        self.ip_mac = {}
        self.lldp = {}
        self.uplink = ()

        if isinstance(host, str):
            self.host = host
            self.comunidade = community
            # print("switch: host: {}, comunidade: {}".format(host, community))
            self.sessao = SNMP(host, community, version)
            self.sessao.start()

        # this index is per switch model, so a class attribute should be fine.
        if not self._map_baseport_ifindex:
            self.map_baseport()
        logging.debug(('-- _map_baseport_ifindex: ', self._map_baseport_ifindex))

    # Necessário criar uma segunda sessão se a comunidade privada for diferente da pública
    # Pode ser que chamemos essa função diversas vezes, de vários lugares diferentes.
    # Então vamos evitar recriar a sessão toda vez. 'force' força recriar.
    def set_start(self, comunidadew='private', version=2, force=False):
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
            #
        :return: nothing. Sets the object variable _map_baseport_ifindex
        """
        oid_portifindex = '.1.3.6.1.2.1.17.1.4.1.2'
        self._map_baseport_ifindex = {}
        for (_poid, _type, _ifindex) in self.sessao.walk(oid_portifindex):
            bidx = _poid.split('.')[-1]
            self._map_baseport_ifindex[int(_ifindex)] = int(bidx)

    def get_geral(self):
        """ Get basic info of this snmp equipment. Includes Descr.0. """
        oids = self._oids_geral.values()
        valores = snmp_values(self.sessao.get(oids))

        for x, y in list(zip(self._oids_geral.keys(), valores)):
            self.board[x] = y

        self.board['mac'] = format_mac(self.board['mac'])
        tmp = self.board['nome'].upper().split('-')
        self.alias = tmp[0] + '-' + tmp[-1]
        self.board['stp'] = int(self.board['stp'])
        # print("-- Switch: {}, {}".format(self.board['mac'], self.board['nome']))

    def load(self):
        """
        Load every interesting characteristics, usually separated into several different methods,
         except the mac-ip list.
        """
        self.get_geral()

        self.get_fab()
        logging.debug(self.board)

        self.get_vlans()
        logging.debug('-- self.vtagged: ' + str(self.vtagged))
        logging.debug('-- self.vuntagged: ' + str(self.vuntagged))

        self.get_portas()
        logging.debug('-- portas: ' + str(self.portas))

        self.lldp = {}
        self.get_lldp_neighbor()
        logging.debug(('-- após vizinhos: ', self.lldp))
        logging.debug(('   +---> uplinks: ', self.uplink))

        self.get_mac_list()
        logging.debug(('-- mac list: ', *self.macs))

    # _fab_var será definido pelas subclasses
    def get_fab(self):
        oids = tuple(v + self._fab_var for v in self._oids_fab)
        valores = self.sessao.get(oids)
        sys_fisico, sys_versoft, sys_serial, sys_fab, sys_modelo = snmp_values(valores)
        self.board['fisico'] = sys_fisico
        self.board['versoft'] = sys_versoft
        self.board['serial'] = sys_serial
        self.board['fab'] = sys_fab.split(' ')[0]
        self.board['modelo'] = sys_modelo

    # mapa de vlans tagged (egress) e untagged. O mapa usa basePort como referência
    def get_vlans(self):
        """
        Get Tagged and Untagged vlans from switch as dictionaries.
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

    # dot1dStpPortEnable (1,2 = ena, disable), dot1dStpPortState,
    #               stp_admin                       stp_state                   stp_pvid
    _oids_stp = ('.1.3.6.1.2.1.17.2.15.1.4.', '.1.3.6.1.2.1.17.2.15.1.3.', '.1.3.6.1.2.1.17.7.1.4.5.1.1.')

    def _oid_stp(self, porta):
        return [v + porta for v in self._oids_stp]

    # poe_admin poe_status poe_class   poe_mpower
    def _oid_poe(self, porta):
        return [self._oids_poe['poeadmin'] + v + '.' + self._oids_poe['poesuffix'] + '.' + porta for v in
                ('3', '6', '10')] \
               + [self._oids_poe['poempower'] + '.' + self._oids_poe['poesuffix'] + '.' + porta]

    # padrão para 3Com e HP. Nem todos switches suportam a árvore dot1qVlanStaticUntaggedPorts.
    # INTEGER {vLANTrunk(1), access(2), hybrid(3), fabric(4)}
    _ifVLANType = '.1.3.6.1.4.1.43.45.1.2.23.1.1.1.1.5'

    def _oid_vtype(self, porta):
        return ['.'.join([self._ifVLANType, porta])]

    # devolve as vlans tagged e untagged para aquela port
    # precisa que seja carregada as vlans existentes nesse switch antes
    def _vlans_ports(self, port):  # , pvid):
        """
        Get VLANS associate to a port. Need to call get_vlans() before this one.
        There are list of vlans with ports, this way the port will be searched to discover the vlans
        :param port: the switch port
        :return: tuple with tagged and untagged vlans as string each
        """
        vtag = []
        vuntag = []
        # vamos descobrir quais vlans uma port possui, tanto tagged qto untagged.
        for j in self.vlans:
            # qdo há algum bug ao tentar pegar as vlans tagged e untagged...
            if j not in self.vtagged or j not in self.vuntagged:
                continue
            # ignora alguns erros temporários do tipo deletar vlan e o SNMP não atualizar em todas as tabelas.
            try:
                T = self.portlist(self.vtagged[j], port)
                U = self.portlist(self.vuntagged[j], port)
                # se a port está marcada como egress e untagged, zera a egress
                x = T if T > 0 and U == 0 else 0
                # port do pvid aparece como untagged...
                y = U if U > 0 else 0

                if x > 0: vtag += [j]
                if y > 0: vuntag += [j]
            except:
                print('-- ## switch::_vlans_ports: erro port {}'.format(port))
        return (vtag, vuntag)

    # NULL values ruins all values of a oid list, even those valid
    # so we have to individually get result by result
    def _snmp_ports_stp(self, porta):
        oidlist = self._oid_stp(porta)
        ret = []
        for i in oidlist:
            ret += self.sessao.get(i)
        return ret

    def _snmp_ports_poe(self, porta):
        # poe_admin poe_status poe_class  poe_mpower
        oidlist = self._oid_poe(porta)
        return self.sessao.get(oidlist)

    def _snmp_ports_vtype(self, porta):
        oidlist = self._oid_vtype(porta)
        ret = []
        for i in oidlist:
            ret += self.sessao.get(i)
        return ret

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
    def get_portas(self):
        """
        Get the switches ports, filtering to get only ether type - sometimes interface vlan appear here, it depends
        on the switch.
        :return: set a dictionary indexed by port number
        """
        # fazer diferente do shell script: pegar os índices das portas e verificar se é ethernet
        # para então pegar todas as outras variáveis. É mais robusto assim, especialmente se quisermos
        # estender o uso para o 7900 ou outros switches.
        # navegando pelo iftype para obter o tipo e a port ao mesmo tempo. Com ela poderemos separar
        # Ethernet de Interface Vlan.
        oid_iftype = '.1.3.6.1.2.1.2.2.1.3'
        for (_oid, _type, _value) in self.sessao.walk(oid_iftype):
            porta = int(_oid[(len(oid_iftype) + 1):])
            iftype = int(_value)

            if self._is_port_ether(iftype):  # and port in self._map_baseport_ifindex:
                self.portas[porta] = self.get_porta_ether(porta)

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

    # PARAM: espera-se que port seja do tipo 'int'
    def get_porta_ether(self, porta):
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

        valores = snmp_values(result, filter=True)
        ifdesc, ifmtu, ifspeed, ifphys, ifadmin, ifoper, iflast, ifindis, \
        ifoutdis, ifduplex, ifalias, ifhcinoct, ifhcoutoct, ifinoct, ifoutoct = valores
        ifinoct = ifhcinoct if ifinoct < ifhcinoct else ifinoct
        ifoutoct = ifhcoutoct if ifoutoct < ifhcoutoct else ifoutoct
        # Specific things for each vendor / model.
        # Uses separeted methods for easier overload.
        oidlist = self._snmp_ports_stp(i)
        oidlist += self._snmp_ports_poe(i)
        oidlist += self._snmp_ports_vtype(i)
        valores = snmp_values(oidlist, filter=True)
        stp_admin, stp_state, stp_pvid, poe_admin, poe_status, poe_class, poe_mpower, vtype = valores
        del result, oidlist, valores

        ifspeed = int(ifspeed)
        ifspeedn = int(ifspeed / 1000000) if ifspeed > 0 else ifspeed
        # \-- iflast, when the interface last changed, format TimeTicks =  0:00:00.00
        iflast = sum([part * base for part, base in zip((3600, 60, 1), map(float, iflast.split(':')))]) * 100
        # Some switches are too much verbose on interface description. Altough the max length check should be done by
        # other class, it won't know how handle the information contained here except trunking the string to a certain
        # length.
        # So, specially for D-LINKs, any subclass should rewrite this description to best fit its purpose of describing
        # the port.
        ifdesc = self._format_ifdesc(ifdesc)

        vtag = ''
        vuntag = ''
        # 2 = port access, vtag and vuntag are not applicable.
        if vtype != '2':
            vtag, vuntag = self._vlans_ports(porta)
            if len(vtag) > 4090:  # probably trunking port with 'permit vlan all' and all vlans created.
                vtag = [4095, ]

        logging.debug('-- port {} ({}), vtag = "{}", vuntag = "{}"'.format(str(porta), str(ifdesc), (vtag), (vuntag)))
        return {
            'speed': ifspeedn
            , 'duplex': int(ifduplex)
            , 'admin': int(ifadmin)
            , 'oper': int(ifoper)
            , 'lastchange': iflast
            , 'discards_in': int(ifindis)
            , 'discards_out': int(ifoutdis)
            , 'oct_in': int(ifinoct)
            , 'oct_out': int(ifoutoct)
            , 'stp_admin': int(stp_admin)
            , 'stp_state': int(stp_state)
            , 'poe_admin': int(poe_admin)
            , 'poe_detection': self._conv_poe_status(poe_status)
            , 'poe_class': int(poe_class)
            , 'poe_mpower': int(poe_mpower)
            , 'mac_count': 0
            , 'pvid': stp_pvid
            , 'porta_tagged': vtag
            , 'porta_untagged': vuntag
            # data: fica por conta de outra classe gerar
            , 'nome': ifdesc
            , 'alias': ifalias
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
            # dentro do OID tem informação da VLAN e do MAC associado a uma port.
            vlan = int(oid[14])
            mac = '{:02x}:{:02x}:{:02x}:{:02x}:{:02x}:{:02x}'.format(*(int(v) for v in oid[15:]))
            # blacklist ou alguma configuração do tipo (static, interface vlan, etc)
            if port == 0:
                self.macs_filtered += ((port, mac, vlan),)
            else:
                self.macs += ((port, mac, vlan),)

    def _lldp_filter_is_uplink(self, lporta, arr):
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
        # se for "00" (em hex), é um voip. Ou algo sem qualquer capacidade de rotear
        # se Telefone... pula.
        # basicamente, 0 = other, 36 = bridge & telefone (Yealink), &4 = bridge
        logging.debug("[{} / {}] lldp_filter_is_uplink: port {} :: capenable = {:d}".
                      format(self.alias, self.host, lporta, arr['capenable']))
        if arr['capenable'] == 0 or arr['capenable'] == 36 or arr['capenable'] & 4 == 1:
            # print("-- [{} / {}] lldp_filter_is_uplink: port {} é voip ou s/ roteamento. capenable = {:d}".format(
            #    self.alias, self.host, lporta, arr['capenable']))
            logging.debug("--           +-----> capenable condition: returning FALSE")
            return False

        # alguns voips podem estar com alimentação via fonte.
        if arr['portsubtype'] == '3' and arr['chassissubtype'] == '5':
            logging.debug("--> [{} / {}] lldp_filter_is_uplink: poe port {} :: subtype/chassi = 3/5".
                          format(self.alias, self.host, lporta))
            return False

        # extra OIDs para analisar se o outro lado é switch ou não. Vê se PVID for 1 e POE desabilitado ou ao menos,
        # baixo consumo.
        # .1.0.8802.1.1.2.1.5.4623.1.2.2.1.6.lporta  -> power class. Talvez seja interessante isso. 1 = switch.
        # .1.0.8802.1.1.2.1.5.4623.1.2.2.1.3.lporta  -> (true/false 1/2) se POE está habilitado.
        # .1.0.8802.1.1.2.1.5.32962.1.2.1.1.1.lporta -> pvid da port.
        oids = ('.1.0.8802.1.1.2.1.5.4623.1.2.2.1.6.' + lporta,
                '.1.0.8802.1.1.2.1.5.4623.1.2.2.1.3.' + lporta,
                '.1.0.8802.1.1.2.1.5.32962.1.2.1.1.1.' + lporta,
                )
        res = snmp_values(self.sessao.get(oids))

        # em vez de verificar quem é switch, vamos verificar quem certamente não é: APs. Isso é bem específico para nossas redes
        # talvez seja bom deixar, no futuro, em algum arquivo de configuração
        if res[2] == '20' or res[2] == '55':
            return False

        # return True if (res[2] == '1' or int(res[2]) >= 100) and (res[1] == '2' or res[0] == '1') else False
        # modificando: se POE está desligado OU power class == 1, então não será VOIP nem AP
        if res[1] == 2 or res[0] == '1':
            return True
        logging.debug(('lldp_filter_is_uplink: poe: ', res[1]))
        # return True if res[1] != '1' else False
        # adicionar outros testes... o antigo está falho. Deixar como False até criar melhores condições
        return False

    # mudanças para detectar melhor o que há na outra ponta
    # lldpRemChassisId
    _oids_lldp_mac = '.1.0.8802.1.1.2.1.4.1.1.5'
    _oids_lldp = {
        'chassissubtype': '.1.0.8802.1.1.2.1.4.1.1.4',
        'portsubtype': '.1.0.8802.1.1.2.1.4.1.1.6',
        'rporta': '.1.0.8802.1.1.2.1.4.1.1.7',
        'remportdesc': '.1.0.8802.1.1.2.1.4.1.1.8',
        'remsysname': '.1.0.8802.1.1.2.1.4.1.1.9',
        'capsupported': '.1.0.8802.1.1.2.1.4.1.1.11',
        'capenable': '.1.0.8802.1.1.2.1.4.1.1.12',
    }
    _oids_lldp_local = {
        'locportdesc': '.1.0.8802.1.1.2.1.3.7.1.4',
    }

    def get_lldp_neighbor(self, is_uplink="_lldp_filter_is_uplink"):
        """
        Get neighbors through LLDP.
        :param is_uplink: optional function to filter LLDP neighbors
        :return: [{lporta: (rmac, rporta)},]
        """

        self.__lldp = {}
        self.lldp = {}
        if is_uplink is not None:
            is_uplink = getattr(self, is_uplink)

        logging.debug("--> : [{} / {}] LLDP: self.lldp {}.".format(self.alias, self.host, str(self.lldp)))
        vizinhos = self.sessao.walk(self._oids_lldp_mac)
        for (oid, tipo, _rmac) in vizinhos:
            oid = oid.replace(self._oids_lldp_mac, '').split('.')

            # alguns dispositivos registram mais de uma vez a mesma port na tabela
            # (o detalhe é a chave temporal que muda). Fazer um filtro para isso.
            lporta = int(oid[2])
            logging.debug("[{} / {}] LLDP: port {}.".format(self.alias, self.host, lporta))
            if lporta in self.lldp:
                logging.debug(
                    "--> NOTE: [{} / {}] LLDP: port {} já consta no dicionário.".format(self.alias, self.host, lporta))
                continue

            snmpId = oid[1]
            lidx = '.'.join(oid[2:4])
            ip = oid[-4:]

            # pega o restante dos dados necessários para identificar um switch na outra ponta.
            res = {}
            # dados da port local
            for k, oid in self._oids_lldp_local.items():
                logging.debug("{} = {}".format(k, self.sessao.get('.'.join((oid, str(lporta))))[0][2]))
                res[k] = snmp_values(self.sessao.get('.'.join((oid, str(lporta)))))[0]

            for k, oid in self._oids_lldp.items():
                # fazendo um ajuste para funcionar com D-LINK, devido a um erro deles no snmpget na árvore LLDP
                res[k] = snmp_values(self.sessao.getnext('.'.join((oid, snmpId, str(lporta)))))[0]

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
                # VOIPs Yealink deixam o campo obtido em _oids_lldp_mac vazio. 
                # Marcam como networkAddress em chassissubtype, mas não informam nada neste campo. 
                # Contudo: rporta e portsubtype contém os dados de MAC da port remota.
                if _rmac == '""':
                    logging.debug("--> NOTE: [{} / {}] LLDP: lporta {}: rmac é nulo.".
                                  format(self.alias, self.host, lporta))
                    continue
                rmac = '{:d}.{:d}.{:d}.{:d}'.format(*[int(v, 16) for v in _rmac.strip(' "').split(' ')[-4:]])

            elif res['chassissubtype'] == '7':
                # Ignoring local ports this time. We need to find a device for that.
                # usually local ports are not numeric and we'll storage only numbers for ports.
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
                tmp = res['rporta'].split('/')
                if tmp[0][-1] == '1':
                    rporta = tmp[2]
                else:
                    # switches com vários layers
                    rporta = ''.join((tmp[0][-1], tmp[2].zfill(2)))
            elif res['portsubtype'] == '3':  # DLINK / VOIPs
                rporta = str(int(res['rporta'].rstrip().split(' ')[-1], 16) + 1)
            else:
                rporta = res['rporta']

            self.lldp[lporta] = (rmac, rporta)
            res['rporta'] = rporta
            res['rmac'] = rmac
            self.__lldp[lporta] = res

            try:
                if is_uplink and is_uplink(str(lporta), res):
                    self.uplink += (lporta,)
            except Exception as e:
                logging.debug('-- #### Exceção Uplink #### ', e)
                self.uplink += (lporta,)

        return self.__lldp

    def portlist(self, valor, port):
        """
        função para interpretar valor em bits de PortList fornecida via SNMP
        por cada switch.
        Cada switch armazena, numa máscara de bits, quais portas estão on ou Off
        para determinados valores (poe, tag, untag, etc) para cada vlan

        rfc2674-qbridge.mib
        DESCRIPTION
            "Each octet within this value specifies a set of eight ports, with the first octet specifying ports 1
            through 8, the second octet specifying ports 9 through 16, etc.
            Within each octet, the most significant bit represents the lowest numbered port, and the least significant
            bit represents the highest numbered port.  Thus, each port of the bridge is represented by a single bit
            within the value of this object.  If that bit has a value of '1' then that port is included in the set of
            ports; the port is not included if its bit has a value of '0'."

        assert isinstance(valor, list) or isinstance(valor, tuple), "valor is not list/tuple"
        assert isinstance(port, int) and port > 0, "port must be int > 0"
        """
        nporta = port - 1
        try:
            idx = math.floor(nporta / 8)
        except:
            idx = 0
        mask = self._mask(nporta)  # defined in __init__

        # print('-- switch::portlist, port = {}, idx = {}, mascara = {}'.format(port,idx,mascara))
        # If you get problems here, recheck the OID. A wrong or bad one gives trouble.
        try:
            return valor[idx] & mask
        except:
            return 0

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
            # reagrupa os 4 últimos dígitos do OID, que são o IP. O 5º é a port, e não interessa agora
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

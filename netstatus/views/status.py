from django.shortcuts import render
from django.db.models import F, Subquery, OuterRef

from ..models import Switches, SwitchesNeighbors, SwitchesPorts, Mac
from ..models import Surveillance, Printer, Wifi, Voip

#   those classes are suited for expansion, or the list to be expanded.
#   each one represents a type of object or of something is connected to network we manage, though the switches, ports
# and macs.

# TODO: it should be in a configuration file.
__special_pvid = {20: 'pvid_20', 55: 'pvid_55'}


def __set_switches_view_data(maincss=None, maintitle=None, cssclass=None, title=None, content=None, inline=False):
    if maincss == maintitle == cssclass == title == content == None and inline == False:
        return None
    if maintitle and maintitle.strip() == '':
        maintitle = None
    _data = {'maincss': maincss,
             'maintitle': maintitle,
             'content': content,
             'class': cssclass,
             'title': title,
             'inline': inline
             }
    return _data


def _format_maccount(port):
    cssclass = content = ''
    # TODO: create dynamic checks for some specific configuration. These here ignore a VLAN for wifis, each already is
    #   informed in the wifi formatting function.
    if port.mac_count > 2 and port.pvid != 20 and port.port != port.switch.stp_root:
        cssclass = 'macs_alto'
        content = '{} macs'.format(port.mac_count)
    return __set_switches_view_data(cssclass=cssclass, content=content)


def _format_voip(port, voip):
    if not voip or port.poe_mpower <= 0:
        return __set_switches_view_data()
    cssclass = 'voip'
    title = "{}\n({})".format(voip['name'], voip['depto'])
    content = '{}'.format(voip['branch'])
    return __set_switches_view_data(cssclass=cssclass, title=title, content=content)


def _format_vlan(port):
    if not port:
        return __set_switches_view_data()
    maincss = cssclass = title = content = ''
    tag = untag = ''
    if len(port.port_tagged) > 0:
        tag = port.port_tagged.replace(',', ', ')
    # only shows relevant untagged vlans. Usually is only one equals to pvid.
    if port.port_untagged != str(port.pvid) and port.port_untagged != 0:
        untag = '{}'.format(port.port_untagged.replace(',', ', '))
    if port.pvid in __special_pvid:
        cssclass += " "+__special_pvid[port.pvid]
    if port.pvid == port.port_untagged and tag == '':
        content = '{}'.format(port.pvid)
        cssclass = ' tag_access'
        title = 'Access Port'
    # if length is too big, reduce it to a better fit in the screen
    if len(tag)+len(untag) < 10:
        if untag:
            content = "{} // {}<br>({})".format(port.pvid, tag, untag)
        else:
            content = "{} // {}".format(port.pvid, tag)
    else:
        content = "{} // <br><div class=tooltip>•••<span class=tooltiptext>Tagged: {}</span></div>".\
                    format(port.pvid, tag)
    cssclass = "tag " + cssclass
    return __set_switches_view_data(cssclass=cssclass, title=title, content=content, maincss=maincss)


def _format_poe(port):
    if not port:
        return __set_switches_view_data()
    cssclass = title = content = ''
    content = 'P'
    if port.poe_admin == 1:
        power = int(port.poe_mpower) / 1000
        if power > 0:
            title = 'ON'
            cssclass = 'poe_on'
            content = 'P{}W'.format(power)
        else:
            title = 'Off'
            cssclass = 'poe_off'
    elif port.poe_admin == 2:
        title = 'disabled'
        cssclass = 'desabilitado'
    elif port.poe_admin == -1:
        title = 'absent'
        cssclass = 'ausente'
    return __set_switches_view_data(cssclass=cssclass, title=title, content=content)


def _format_port(port, mac_ip):
    if not port:
        return __set_switches_view_data()
    cssclass = title = content = maintitle = ''
    content = '&nbsp;'
    if port.admin == 2:
        cssclass = 'problema'
        content = 'shut'
    else:
        if port.oper == 1:
            if port.duplex == 2:
                cssclass = 'halfduplex'
                title = 'half duplex'
            if port.speed == 1000:
                content = '1G'
                cssclass += ' speed1G'
            elif port.speed == 100:
                content = '100M'
                cssclass += ' speed100M'
            elif port.speed == 10:
                content = '10M'
                cssclass += ' speed10M'
            else:
                cssclass = ''
                title = ''
    # check MAC-IP
    if port in mac_ip:
        maintitle = "{}\n{}".format(mac_ip[port].ip, mac_ip[port].mac)
    maintitle = "{}\n{}".format(port.alias if port.alias else port.name, maintitle)
    return __set_switches_view_data(cssclass=cssclass, title=title, content=content, maintitle=maintitle)


def _format_lldp(port, lldp):
    # print("###>>> lldp type: {}".format(type(lldp)))
    if not lldp:
        return __set_switches_view_data()
    maincss = ''
    name = lldp['omac'] if lldp['oname'] is None else lldp['oname']
    cssclass = 'vizinho'
    title = name
    content = '<a href="#{}">&uArr;</a>'.format(name)
    if port.port != port.switch.stp_root:
        maincss = 'vizinho_td'
    return __set_switches_view_data(cssclass=cssclass, title=title, content=content, inline=True, maincss=maincss)


def _format_stp(port, switch):
    maintitle = maincss = ''
    if switch.stp_root == port.port:
        maincss = 'stp_root'
        maintitle = 'STP: root'
    elif port.stp_admin == 1:
        if port.oper == 1 and port.admin == 1 and port.stp_state == 2:
            maincss = 'stp_block'
            maintitle = 'STP: block'
    else:
        # A core switch that informs STP disabled when the port is offline... trying to bypass that.
        if not (port.stp_admin == 2 and port.stp_state == 1 and port.admin == 1 and port.oper == 2):
            maincss = 'stp_disable'
            maintitle = 'STP: disable'
    return __set_switches_view_data(maintitle=maintitle, maincss=maincss)


def _format_printer(port, printer):
    if not port or not printer:
        return __set_switches_view_data()
    maincss = cssclass = title = content = ''
    cssclass = 'printer'
    title = '{}\n{}\n{}'.format(printer['dns'], printer['hrdesc'], printer['ip'])
    content = "<a href='http://{}' target=_BLANK>PRT</a>".format(printer['ip'])
    return __set_switches_view_data(cssclass=cssclass, title=title, content=content, maincss=maincss)


def _format_wifi(port, wifi):
    # this is a specific thing that should put in another place
    if not port or not wifi or port.pvid != 20:
        return __set_switches_view_data()
    maincss = cssclass = title = content = ''
    if port.port_tagged != '77':
        cssclass = 'wfu_problema'

    title = '{}\n{}\n{}'.format(wifi['ip'], wifi['ip6'], wifi['mac'])
    # wifi.mac_count
    content = "<img width=16 src=/static/img/wfu.png /><small>{}</small>".format(port.mac_count)
    return __set_switches_view_data(cssclass=cssclass, title=title, content=content, maincss=maincss)


def _format_surveillance(port, surv):
    # this is a specific thing that should put in another place
    if not port or not surv:
        return __set_switches_view_data()
    maincss = cssclass = title = content = ''

    if port.pvid != 55:
        cssclass = 'wfu_problema'

    title = '{}\n{}\n{}\n{}'.format(surv['type'], surv['ip'], surv['mac'], surv['comments'])
    content = "<img height=16 src=/static/img/vigi.png /><small>{}</small>".format(surv['type'][:5])
    return __set_switches_view_data(cssclass=cssclass, title=title, content=content, maincss=maincss)


def _format_use(port):
    if not port:
        return __set_switches_view_data()
    maincss = maintitle = content = ''
    cssclass = 'port'
    if port.admin != 2 and port.oct_in == 0 and port.oct_out == 0:
        maintitle = 'No traffic seen until now'
        cssclass += ' notraffic'
    # we want to write the port name in the cell background. However, not all switches use same pattern for names.
    # We should consider styles like GigabitEthernet1/0/10, A11, B21, Ethernet1/0/24 and limit the final string to
    # 3 chars length.
    slash_index = port.name.rfind('/')
    if slash_index != -1:
        # Example: GigabitEthernet1/0/12; Ethernet1/0/15 -- 3Com, HP
        content = port.name[0] + port.name[(slash_index+1):][:3]
    elif len(port.name) > 3:
        # Example: Port 27 -- DLink; Ethernet interface (rolling my eyes) -> should move this to a per switch class
        # if the last two digit isn't a number, take the port number as a reference.
        try:
            # big port number (special ports)... truncate the name instead
            if port.port > 999:
                content = port.name[:3]
            else:
                content = '{}'.format(int(port.name[-2:]))
        except ValueError:
            content = '{}'.format(port.port)
    else:
        # some HPN multi slot switches: A3, B24
        content = port.name
    return __set_switches_view_data(cssclass=cssclass, content=content, maintitle=maintitle, maincss=maincss, inline=True)


# Our View starts here.
def switches_list(request):
    # Load several network related objects into dictionaries. Better than putting ResultSets inside a loop,
    # and these data won't change anyway.
    surveillances = Surveillance.objects.all()
    survs_mac = {x.mac: {'mac': x.mac, 'ip': x.ip, 'type': x.type, 'comments': x.comments} for x in surveillances}
    del surveillances
    printers = Printer.objects.all()
    printers_mac = {x.mac: {'dns': x.dns, 'ip': x.ip, 'hrdesc': x.hrdesc} for x in printers}
    del printers
    wifis = Wifi.objects.all()
    wifis_mac = {x.mac: {'ip6': x.ip6, 'ip': x.ip, 'mac': x.mac} for x in wifis}
    del wifis
    voips = Voip.objects.all()
    voips_mac = {x.mac: {'branch': x.branch, 'name': x.name, 'depto': x.depto} for x in voips}
    del voips

    # making the switch core (stp_root == 0) as the first to be shown. Should be nice to add a custom ordering as
    # each person configures and names switches differently.
    switches = Switches.objects.filter(status='active').extra(
        select={'s1': 'stp_root=0', 's2': 'substring(name from -3)', 's3': 'substring(name from 1 for 3)'},
        order_by=['-s1', 's2', 's3']
    )
    for switch in switches:
        # now these data are depends on each Switch.
        # a relation of port / mac is necessary to identify which resource is on which port of the switch.
        # At the same time, we'll need the ip / mac association for information on each port, so we'll create two
        # dictionaries from one loop.
        macs = switch.mac_switch.order_by('port')
        macs_hash = {}
        mac_ip = {}
        for m in macs:
            if m.port in macs_hash:
                macs_hash[m.port] += [m.mac]
            else:
                macs_hash[m.port] = [m.mac]
            if m.vlan == 1:
                mac_ip[m.port] = {'mac': m.mac, 'ip': m.ip}

        lldps = SwitchesNeighbors.objects.filter(mac1=switch.mac).annotate(
            oname=Subquery(Switches.objects.filter(status='active', mac=OuterRef('mac2')).values('name'))
        )
        lldps_mac = {x.port1: {'omac': x.mac2, 'oport': x.port2, 'oname': x.oname} for x in lldps}
        del lldps

        # Here where the config for each port will be generated.
        switch_ports = switch.ports.all().order_by('port')
        ports_rendered = []
        for switch_port in switch_ports:
            # TODO: think if there is a better approach to this.
            _stp = _format_stp(switch_port, switch)
            _lldp = _format_lldp(switch_port, lldps_mac[switch_port.port]) if switch_port.port in lldps_mac else None
            _port = _format_port(switch_port, mac_ip)
            _poe = _format_poe(switch_port)
            _vlan = _format_vlan(switch_port)
            _use = _format_use(switch_port)
            _count = _format_maccount(switch_port)

            # if there is something plugged in, let's check it out what it is.
            # Avoid analyzes with connections to another switch or network bridge, as it doesn't make much sense.
            _voip = _surv = _wifi = _printer = _printer = None
            if switch_port.port in macs_hash and not _lldp:
                voip = next((y for x, y in voips_mac.items() if x in macs_hash[switch_port.port]), None)
                wifi = next((y for x, y in wifis_mac.items() if x in macs_hash[switch_port.port]), None)
                printer = next((y for x, y in printers_mac.items() if x in macs_hash[switch_port.port]), None)
                surveillance = next((y for x, y in survs_mac.items() if x in macs_hash[switch_port.port]), None)
                _voip = _format_voip(switch_port, voip)
                _wifi = _format_wifi(switch_port, wifi)
                _printer = _format_printer(switch_port, printer)
                _surv = _format_surveillance(switch_port, surveillance)

            ports_rendered += [(_use, _lldp, _stp, _port, _poe, _vlan, _voip, _printer, _wifi, _surv, _count),]
        switch.ports_rendered = ports_rendered

    return render(request, 'switches_list.html', {'switches': switches,})

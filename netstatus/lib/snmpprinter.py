import re
import socket
import netsnmp

from netstatus.models import Printer
from .snmp import SNMP


def _format_snmp(result):
    return (v[netsnmp.VALUE].replace('"', '')
              if v[netsnmp.TYPE] not in ('NOSUCHINSTANCE', 'NOSUCHOBJECT', 'NULL') else -1
              for v in result)


def probe_snmp_printer(host, community='public'):
    """
    Gather some info from network printers through SNMP and save into database.
    """
    if host == '':
        return ''
    try:
        sess_snmp = SNMP(host, community)
        if sess_snmp:
            sess_snmp.start()
    except:
        return 'Err opening snmp session'

    oids = ['.1.3.6.1.2.1.1.5.0',           # name
            '.1.3.6.1.2.1.1.1.0',           # description
            '.1.3.6.1.2.1.25.3.2.1.3.1',    # hardware description
            '.1.3.6.1.2.1.43.5.1.1.16.1',   # printer name
            '.1.3.6.1.2.1.43.5.1.1.17.1',   # serial
            '.1.3.6.1.2.1.25.3.2.1.3.1',    # brand
            '.1.3.6.1.2.1.2.2.1.6.1',       # mac1 - first possible place for the printer mac
            '.1.3.6.1.2.1.2.2.1.6.2',       # mac2
            ]
    result = sess_snmp.get(oids)
    # cleaning the data from SNMP
    values = _format_snmp(result)
    name, descr, hrdesc, pname, serial, brand, mac2, mac3 = values
    dns = socket.gethostbyaddr(host)[0].split('.', 1)[0]

    mac = ''
    if mac2:
        mac = mac2
    else:
        mac = mac3
    mac = mac.strip().replace(' ', ':')
    if len(mac) != 17:
        # some switches omits the left digit if zero
        mac = re.sub(r'^(.):', r'0\1', mac).lower().strip()
        mac = re.sub(r':(.):', r':0\1:', mac)
    if not pname or pname == -1:
        result = sess_snmp.get(['.1.3.6.1.4.1.11.2.3.9.4.2.1.1.3.3.0', '.1.3.6.1.4.1.11.2.3.9.4.2.1.1.3.2.0'])
        values = _format_snmp(result)
        serial, pname = values
        # these data are hex-coded strings.
        serial = bytearray.fromhex(serial).decode()
        pname = bytearray.fromhex(pname).decode()

    ip = host
    if not ip[0].isdigit():
        # TODO implement dns resolving for printer names
        pass

    printer = Printer()
    printer.mac = mac
    printer.ip = ip
    printer.hrdesc = hrdesc
    printer.dns = dns
    printer.name = pname
    printer.serial = serial
    printer.brand = descr
    try:
        printer.save()
        yield "Printer inserted. Values: <br>" \
              "dns: '{}', <br>ip: '{}', <br>mac: '{}', <br>hrdesc: '{}', <br>pname: '{}', <br>serial: '{}', "\
              "<br>descr: '{}'".\
            format(dns, ip, mac, hrdesc, pname, serial, descr)
    except:
        yield "Failed to insert printer: <br>"\
                "dns: '{}', <br>ip: '{}', <br>mac: '{}', <br>hrdesc: '{}', <br>pname: '{}', <br>serial: '{}', "\
              "<br>descr: '{}'".\
                format(dns, ip, mac, hrdesc, pname, serial, descr)
    return


"""
    Static functions for Switch classes
"""
import netsnmp


def format_mac(value):
    return value.replace('"', '').strip().replace(' ', ':').lower()


def snmp_values(values, filter_=False):
    """ Clean the OID data from SNMP library """
    if filter_:
        return (v[netsnmp.VALUE].replace('"', '')
                if v[netsnmp.TYPE] not in ('NOSUCHINSTANCE', 'NOSUCHOBJECT', 'NULL') else -1
                for v in values
                )
    return [v[netsnmp.VALUE].replace('"', '') for v in values]


def snmp_values_dict(values):
    return {v[netsnmp.OID].split('.')[-1]: v[netsnmp.VALUE].replace('"', '') for v in values}


# def mask_bigendian(nport):
def mask_littleendian(nport):
    """ get port from portlist (qbridge) through big endian mask. 3Com / HP use this.
    Set self.mask to call this.
    QBridge - Portlist. The RFC 2674 says the most significant bit, but don't force the bit order.
    """
    return 1 << (nport % 8)


# def mask_littleendian(nport):
def mask_bigendian(nport):
    """ get port from portlist (qbridge) through little endian mask. 
    D-Link / new HP / Extreme XOS use this.
    "the least significant bit represents the highest numbered port"
    Set self.mask to call this.
    """
    return 128 >> (nport % 8)


def lldp_is_uplink_extra(switch, lport, lldp_port):
    """
    Specifics checks. You may want to change this.
    """
    # More OIDs to guess if neighbor is switch or not. Check PVID == 1 and disabled POE at least.
    # .1.0.8802.1.1.2.1.5.4623.1.2.2.1.6.lport  -> power class.  1 = switch (maybe).
    # .1.0.8802.1.1.2.1.5.4623.1.2.2.1.3.lport  -> (true/false 1/2) if POE is enabled.
    # .1.0.8802.1.1.2.1.5.32962.1.2.1.1.1.lport -> pvid
    oids = ('.1.0.8802.1.1.2.1.5.4623.1.2.2.1.6.' + lport,
            '.1.0.8802.1.1.2.1.5.4623.1.2.2.1.3.' + lport,
            '.1.0.8802.1.1.2.1.5.32962.1.2.1.1.1.' + lport,
            )
    res = snmp_values(switch.sessao.get(oids))
    # checking specific variables for other type of devices.
    if res[2] == '20' or res[2] == '55':
        return False
    # return True if (res[2] == '1' or int(res[2]) >= 100) and (res[1] == '2' or res[0] == '1') else False
    # modificando: se POE está desligado OU power class == 1, então não será VOIP nem AP
    if res[1] == 2 or res[0] == '1':
        return True
    return False


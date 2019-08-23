"""
    Static functions for Switch classes
"""
import netsnmp


def format_mac(value):
    return value.replace('"', '').strip().replace(' ', ':').lower()


def snmp_values(values, filter=False):
    """ Clean the OID data from SNMP library """
    if filter:
        return (v[netsnmp.VALUE].replace('"', '')
                if v[netsnmp.TYPE] not in ('NOSUCHINSTANCE', 'NOSUCHOBJECT', 'NULL') else -1
                for v in values
                )
    return [v[netsnmp.VALUE].replace('"', '') for v in values]


def snmp_values_dict(values):
    return {v[netsnmp.OID].split('.')[-1]: v[netsnmp.VALUE].replace('"', '') for v in values}


def _mask_bigendian(nport):
    """ get port from portlist (qbridge) through big endian mask. 3Com / HP use this.
    Set self.mask to call this.
    QBridge - Portlist. The RFC 2674 says the most significant bit, but don't force the bit order.
    """
    return 1 << (nport % 8)


def _mask_littleendian(nport):
    """ get port from portlist (qbridge) through little endian mask. D-Link / new HP use this.
    Set self.mask to call this.
    D-LINK, e newer HP switches. Each subclass must set self._mask to this in the __init__
    """
    return 128 >> (nport % 8)
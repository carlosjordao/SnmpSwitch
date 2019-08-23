from netstatus.lib.snmp import SNMP


def probe_snmp_host(host, community, oper, oid, values=[]):
    if oper != 'get' and oper != 'set' and oper != 'walk':
        yield "Invalid Operation (%s). Must be get, walk or set\n" % oper
        return

    if oper == 'set':  # and not values:
        yield 'Not fully implemented yet. Sorry.'
        return

    if community is None or community == '':
        community = 'public'

    snmp = SNMP(host, community)
    if oper == 'get':
        yield snmp.get(oid)
    elif oper == 'walk':
        yield '\n'.join([i for i in snmp.walk(oid)])
    else:
        value = values[0]
        try:
            value_type = values[1]
        except:
            value_type = None
        yield snmp.set(oid, value, value_type)
    return

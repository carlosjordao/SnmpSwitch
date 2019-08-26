from netstatus.lib.switchfactory import SwitchFactory


def probe_switch_neighbors(host, community='public'):
    """
    Tool to list neighbors of a switch. May help visualize connections between pairs.
    :param host: switch ip or dns name
    :param community: if not using default configuration
    :return: empty. Yield will hold our response to StreamingHttpResponse on View
    """
    try:
        switch = SwitchFactory().factory(host, community)
        neighbors = switch.get_lldp_neighbor(None)
    except Exception as e:
        yield "error connecting to the switch"
        print(repr(e))
        return

    yield '# LOCAL: port number + port description  >>  REMOTE: switch name + port + port description'
    for k, v in neighbors.items():
        yield "{:>4}, {:>3}, {:>30}, {:>25}, {}".format(k, v['locportdesc'], v['remsysname'], v['rport'], v['remportdesc'])

    return


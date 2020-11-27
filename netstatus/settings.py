import os


class Settings:
    # Will be used to get the Switch interface Vlan and its IP.
    MANAGEMENT_VLAN = 20 \
        if 'MANAGEMENT_VLAN' not in os.environ else int(os.environ['MANAGEMENT_VLAN'])
    # function name used by Switch.get_lldp_neighbor to guess if port is an uplink or not.
    LLDP_IS_UPLINK_EXTRA = 'lldp_is_uplink_extra' \
        if 'LLDP_IS_UPLINK_EXTRA' not in os.environ else os.environ['LLDP_IS_UPLINK_EXTRA']
    # switch.alias is a small field which can be used to fast memorizing and fast searching among several switches.
    # It is mainly used by humans, so the format should appropriate to each case. Default to first 3 chars plus last
    # two chars from name.
    SWITCH_ALIAS = lambda name: name[:3] + '-' + name[-2:] \
        if 'SWITCH_ALIAS' not in os.environ else eval(os.environ['SWITCH_ALIAS'])
    DEBUG = False
    #DEBUG = True

class Settings:
    # Will be used to get the Switch interface Vlan and its IP.
    MANAGEMENT_VLAN = 20
    # function name used by Switch.get_lldp_neighbor to guess if port is an uplink or not.
    LLDP_IS_UPLINK_EXTRA = 'lldp_is_uplink_extra'

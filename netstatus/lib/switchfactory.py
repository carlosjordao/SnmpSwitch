from .snmp import SnmpFactory
from .switch.Switch import *
from netsnmp._api import SNMPError


class SwitchFactory:
    """
    Factory resolver for Switch class, finding out which subclass is more suitable to represent each switch.
    Each subclass must implement sou_compatível(ifDescr) method.
    """
    @classmethod
    def _type(cls, descr, classe):
        """ Resolve the fittest subclass for this SNMP Switch through deep first. """
        for switchClass in classe.__subclasses__():
            logging.debug('    \\--> class: {}'.format(switchClass.__name__))
            if switchClass.is_compatible(descr):
                ret = SwitchFactory._type(descr, switchClass)
                if ret is not None:
                    return ret
                return switchClass
        return classe

    @classmethod
    def factory(cls, host, community='public', version=2):
        """
        Get new instance of Switch class or subclass based on the switch SNMP description field.
        :param host: IP of a switch
        :param community: snmp community
        :param version: 2. Only change this if you switch only supports SNMP version 1
        :return: new instance of Switch class/subclass
        """
        try:
            # if host is str:
            if isinstance(host, str):
                #snmp_con = SNMP(host, community)
                snmp_con = SnmpFactory.factory(host, community)
                snmp_con.start()
            else:
                snmp_con = host
            descr = Switch.online_description(snmp_con)
        except SNMPError as e:
            raise
        except Exception as e:
            raise Exception("FACTORY: Error with description: {}".format(e))
        class_found = SwitchFactory._type(descr, Switch)
        return class_found(host, community, version)


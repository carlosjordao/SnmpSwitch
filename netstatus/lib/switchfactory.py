from .switch.Switch import *


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
        logging.debug("FACTORY: host: {}, comunidade: {}".format(host, community))
        try:
            # if host is str:
            if isinstance(host, str):
                snmp_con = SNMP(host, community)
                snmp_con.start()
            else:
                snmp_con = host
            descr = snmp_con.get('.1.3.6.1.2.1.1.1.0')[0][2].replace('"', '')
        except Exception as e:
            logging.debug("FACTORY: Error with description: {}".format(e))
            return None
        class_found = SwitchFactory._type(descr, Switch)
        logging.debug('FACTORY: found class: {}'.format(class_found.__name__))
        return class_found(host, community, version)


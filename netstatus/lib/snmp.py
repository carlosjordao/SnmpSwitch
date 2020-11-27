from datetime import timedelta
import os

import netsnmp


class SnmpFactory:
    """
        Factory class for SNMP. It aims to be easier to change to other methods 
    like PseudoSNMP or using Mock
    """
    @classmethod
    def factory(cls, host='', community='public', version=2):
        return SNMP(host, community, version)


class SNMP:
    """
        Wrap class for snmp library.
        netsnmp official library has an odd syntax for me and there is another library available in pip3 with a better
        one. But in case we may need to change this to another one, this class should minimize the amount of rework.
    """
    host = ''
    version = 2
    community = 'public'
    session = None
    _map = {1: '1', 2: '2c', 3: '3'}

    def __init__(self, host, community='public', version=2):
        self.community = community
        self.version = self._map[version]
        # IPv6 needs to be explicit, it won't guess based on IP
        self.host = 'udp6:[{}]'.format(host) if ':' in host else host

    def start(self):
        try:
            self.session = netsnmp.SNMPSession(self.host, self.community)
        except:
            print("Session err for {}".format(self.host))
            raise

    def get(self, oids_var):
        return self.session.get(oids_var)

    def getnext(self, oids_var):
        return self.session.getnext(oids_var)

    def walk(self, oids_var):
        return self.session.walk(oids_var)

    # type_var must be one of several letters provided by snmpset -h
    def set(self, oids_var, value, type_var):
        return self.session.set(oids_var, value, type_var)

    def __del__(self):
        self.session.close()


class PseudoSnmp(SNMP):
    """
    This class is used to provide offline data from switches as if it were online.
    This class aims to 'simulate' a switch through reading files from:
         snmpwalk -One -v2c 
    command and providing an answer as if it is online. This way, there won't 
    need to test it with live switches at the beginning of the development or 
    after any changes.

    As the objective is just provide some kind of interface to test the whole system, the number of features will
    be limited. The only bugs to be fixed is any that prevents the test occurrence or that gives a unexpected answer
    some point through get(), getnext() and walk() methods.

    Expected file format:
    .1.3.6.1.2.1.197.1.4.2.0 = ""
    .1.3.6.1.2.1.207.1.2.1.0 = Counter64: 0
    Output:
    [('.1.3.6.1.2.1.207.1.2.1.0', 'Counter64', '0'), ...]
    """
    # where we store the files from snmpwalk -On
    path = '/opt/switches'
    _oid_ip = '.1.3.6.1.2.1.4.20.1.1'

    # you should change this

    def __init__(self, host, community='public', version=2):
        super().__init__(host, community, version)
        self.host = host
        self.mib = {}  # the place the mib is stored after reading the snmpwalk file
        self.response = []  # one call at time, so one response.
        self._oid_ip_ext = '192.168'  # the switch IP starts with this. A hack to test integration with Models
        self.community = 'public'  # it doesn't matter

    @staticmethod
    def NOOBJECT(oids_var):
        return [(oids_var, 'NOSUCHOBJECT', '-1')]

    def _traverse(self, oid):
        """
            Go search through the mib stored as a chained list, as in C
            Returns the pointer to the entry, or an empty dict as null pointer
        if not found
            Used for retrieving data (get / walk)
        """
        if oid[0] == '.':
            oid = oid[1:]
        pointer = self.mib
        for i in oid.split('.'):
            if i not in pointer:
                return {}
            pointer = pointer[i]
        return pointer

    @staticmethod
    def _format_content(pointer):
        content = pointer['content'].strip()
        _type = pointer['type']
        if _type == 'STRING' or _type == 'Hex-STRING':
            pointer['content'] = '"{}"'.format(content)
        elif _type == 'Timeticks':
            # netsnmp-py: ('.1.3.6.1.2.1.2.2.1.9.20', 'Timeticks', '48:12:16:25.82')
            # get the raw value (snmpwalk without -One)
            if content.find('(') != -1:
                ticks = float(content[content.find('(') + 1:content.find(')')])
            else:
                # snmpwalk with -Oe has only raw values
                ticks = float(content)
            c = timedelta(seconds=(ticks/100))
            pointer['content'] = "%s:%.2d:%.2d:%.2d.%.2d" % \
                                 (c.days, c.seconds // 3600, (c.seconds // 60) % 60, c.seconds % 60, ticks % 100)
        else:
            # .1.3.6.1.2.1.2.2.1.3.1 = INTEGER: ethernetCsmacd(6)
            if content and not content[0].isdigit():
                content = content[content.rfind('(') + 1:-1]
            pointer['content'] = content

    def start(self):
        """
        Load the snmpwalk file
        """
        filename = '{}/{}'.format(self.path, self.host)
        if not os.path.isfile(filename):
            raise ValueError("Cannot locate the test file for snmp: " + filename)
        pointer = {}
        with open(filename) as f:
            content = ''
            for line in f:
                # starts with OID
                if line[0] == '.' and line[1].isdigit():
                    # netstatus-py lib brings all STRING with double quotes.
                    if pointer:
                        self._format_content(pointer)
                    tmp = line.split(' ') # splits 4 parts: oid, =, type, value  
                    try:
                        # first value is OID
                        _idx = tmp[0][1:]    # remove the first dot
                        # lines without type are empty strings
                        if tmp[2] == '""':
                            _type = 'STRING'
                            _content = '""'
                        else:
                            _type = tmp[2][:-1]             # remove the :
                            _content = ' '.join(tmp[3:])    # content == value

                        # now create the dictonary from the OID we got.
                        pointer = self.mib
                        for i in _idx.split('.'):
                            if i not in pointer:
                                pointer[i] = {}
                            pointer = pointer[i]
                        pointer['type']    = _type
                        pointer['content'] = _content
                        pointer['oid']     = '.' + _idx
                    except IndexError as e:
                        print(line, e)
                # multi line data
                else:
                    pointer['content'] += line
            if pointer:
                self._format_content(pointer)
        v = self.getnext('{}.{}'.format(self._oid_ip, self._oid_ip_ext))[0]
        if v[netsnmp.VALUE] != '-1':
            self.host = v[netsnmp.VALUE]

    def _get_value(self, oids_var, p):
        if 'type' not in p:
            return self.NOOBJECT(oids_var)
        return [(oids_var, p['type'], p['content'])]

    def get(self, oids_var):
        if type(oids_var) is str:
            oids_var = [oids_var]
        ret = []
        for i in oids_var:
            p = self._traverse(i)
            ret += self._get_value(i, p)
        return ret

    def _getnext_str(self, oids_var):
        p = self._traverse(oids_var)
        if 'type' in p:
            return [(p['oid'], p['type'], p['content'])]
        while p and 'type' not in p:
            i = next(iter(p.keys()))
            p = p[i]
        if p and 'type' in p:
            return [(oids_var, p['type'], p['content'])]
        return self.NOOBJECT(oids_var)

    def getnext(self, oids_var):
        """
            Get the next valid entry and value from some OID 
            We don't need to traverse like walk, so the recursive function 
        is different
        """
        if type(oids_var) is str:
            oids_var = [oids_var]
        ret = []
        for i in oids_var:
            ret += self._getnext_str(i)
        return ret

    def _walk_p(self, p, response):
        if 'type' in p: # it means we found an entry, let's save it
            response += [(p['oid'], p['type'], p['content'])]
        else:
            # not a leaf, so get the entries to the next level
            # (deepest first)
            for i in p.keys():
                self._walk_p(p[i], response)
        return

    def walk(self, oids_var):
        response = []
        if type(oids_var) is str:
            oids_var = [oids_var]
        for l in oids_var:
            # finding the root pointer to the walk
            p = self._traverse(l)
            self._walk_p(p, response)
        return response

    def __del__(self):
        pass


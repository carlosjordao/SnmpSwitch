import sys
import time
import logging
from threading import Thread, Lock

from django.db import IntegrityError, DataError, connection, connections
from django.utils import timezone

from netstatus.lib.switchfactory import SwitchFactory
from netstatus.models import Switches, SwitchesNeighbors, Mac, SwitchesPorts
from netstatus.settings import Settings
from netstatus.lib.switch import switchlib


IP_CORE = ''
switches_list = {}
lock = Lock()


def now():
    return timezone.now().isoformat()


def redirect_stderr(f):
    """
    Wraps a python function that prints to the console, and returns those results as a yield response.
    This is used mainly for redirect legacy classes and common info printed to console to StreamingHttpResponse instead.
    """
    class WritableObject:
        def __init__(self):
            self.content = []

        def write(self, string):
            self.content.append(string)

    def new_f(*args, **kwargs):
        printed = WritableObject()
        sys.stderr = printed
        if Settings.DEBUG:
            logging.basicConfig(level=logging.DEBUG)
        logging.StreamHandler(printed)
        f(*args, **kwargs)
        sys.stderr = sys.__stdout__
        return printed.content

    return new_f


@redirect_stderr
def probe_update_host(host='', community='public', dryrun=False):
    # one host to be probed and inserted into database
    rows = [[host, 0, community, -1]]
    _switch_status(rows, dryrun)
    return


@redirect_stderr
def probe_update_db(dryrun=False):
    """
    Fetches all switches from database. This data is sento to _switch_status() to do the job.
    :param dryrun: if True, won't activate the save() after checking the switch.
    :return:
    """
    try:
        from django.db import connection
        cursor = connection.cursor()
        cursor.execute("SELECT ip, stp_root, community_ro, id "
                       "FROM switches WHERE status = 'active'")
        rows = cursor.fetchall()
    except Exception as e:
        print(e, file=sys.stderr)
        return
    if len(rows) == 0:
        print("Probe_update: Error: no switch to connect to from database", file=sys.stderr)
        return
    _switch_status(rows, dryrun)
    return


def _switch_status(rows, dryrun):
    """
    Get and save the data from one or more switches through SNMP into database. Makes conversion from SNMP classes
    to the database model.
    Receives one or more switches in a tuple with other options. These will be probed in parallel to optimize time and
    all the data will be placed into Models and save.
    :param rows: [[ip, stp_root, community, id],...]
    :param dryrun: for testing. Avoid saving into database after every step.
    :return: empty string. The main information is yielded for the StreamHttpResponse()
    """
    logging.debug('##>>> switch_status: rows={}, dryrun={}'.format(rows, dryrun))
    global IP_CORE
    global switches_list
    switches_list = {}
    results = {}
    start = time.perf_counter()
    # load all host in parallel
    othreads = []
    try:
        for row in rows:
            results[row[0]] = -1
            t = Thread(target=_load_host, args=(row[0], row[2], row[3]))
            othreads += [t]
            t.start()
            time.sleep(0.10)
        for t in othreads:
            t.join()
    except Exception as e:
        print('%% Error After threads: {}'.format(e), file=sys.stderr, end='')

    s_core = switches_list[IP_CORE] if IP_CORE and IP_CORE in switches_list else None
    diff = (len(rows) - len(switches_list))
    res = 'ok' if diff == 0 else 'problems'
    host_problems = [i[0] for i in rows if i[0] not in switches_list] if diff != 0 else []
    print("-- ### Total (switches, switch_list, diff) = ({}, {}, {}) => {}, core={}\nproblems = {}".
          format(len(rows), len(switches_list), diff, res, s_core, host_problems), file=sys.stderr, end='')

    # todo: remove it in future versions after test.
    for o in switches_list.values():
        if o is None:
            print('-- switch is none. skipping...', file=sys.stderr, end='')
            continue
        try:
            switch = Switches.objects.get(mac=o.mac)
        except Switches.DoesNotExist as e:
            print("###### error: switch was not found in database. mac={}".format(o.mac), file=sys.stderr, end='')
            switch = Switches()

        print('##>>> Switch ID={}, serial_number={}, name={}, alias={}, mac={}, ip="{}", totaltime={}; vendor={},\n'
              '\t\tclass={}, len(ports)={}'.format(
              switch.id, switch.serial_number, switch.name, switch.alias, switch.mac, o.host, o.totaltime, o.vendor,
              o.__class__.__name__, len(o.portas)), 
              file=sys.stderr, end='')

        print('##\t\t oid_poe_admin = {}'.format(o._oid_poe('1')[0]), file=sys.stderr, end='')

        # the switch should be unique in the database, based on mac / serial_number.
        # But it may be relocated and have name and IP changed. So, apply those changes to the database.
        switch.name          = o.name
        switch.mac           = o.mac
        switch.ip            = o.host
        switch.model         = o.model
        switch.serial_number = o.serial
        switch.status        = 'active'
        switch.vendor        = o.vendor
        switch.soft_version  = o.soft_version
        switch.stp_root      = o.stp
        switch.community_ro  = o.comunidade
        # logging.debug('##>>> switchs: ({}, {}, {}, model={}, serial={}, vendor={}, ver={}, stp={})'.format(o.name, o.mac, o.host, o.model, o.serial, o.vendor, o.soft_version, o.stp))
        try:
            switch.alias = Settings.SWITCH_ALIAS(o.name) if Settings.SWITCH_ALIAS else o.name[:6]
        except TypeError:
            switch.alias = o.name[:6]

        if not dryrun:
            try:
                switch.save()
                cursor = connection.cursor()
                cursor.execute("UPDATE switches SET status='inactive_script' "
                               "WHERE status='active' AND ip='{0}' and serial_number <> '{1}'".\
                               format(switch.ip, switch.serial_number))
            except DataError as e:
                print("##>>> Error saving switch {} ({}): {}".format(switch.id, switch.name, e))
                print(connection.queries[-1])
                continue
            except IntegrityError as e:
                import pprint
                print("##>>> Switch already is present in db but not found when you looked for it.\n"
                      "{}\n id={}, mac={}, mac2={}".
                      format(e,  switch.id, switch.mac, o.mac))
                pp = pprint.PrettyPrinter(indent=4)
                pp.pprint(connection.queries[-3:])
                continue

        sp = o.portas[1]
        print('##\t\t{}, {}, {}, admin={}, oper={}, stp_admin={}, poe_admin={}; poe_mpower={}, pvid={}, '
              'vtagged={}, vuntagged={}'.format(
              1, sp['nome'][:30], sp['speed'], sp['admin'], sp['oper'], sp['stp_admin'], sp['poe_admin'], 
              sp['poe_mpower'], sp['pvid'], ', '.join(sp['tagged']), ', '.join(sp['untagged'])), 
              file=sys.stderr, end='')

        # this check is just to avoid deleting ports associate to this switch. Not a big deal, though, but
        # our database should store significant changes onto switches_ports and feed the *_log tables with previous
        # data. Avoiding deleting avoids excessive insert into other table, not for sake of performance, but to maintain
        # these log tables useful to check changes in the network.
        for port, pdata in o.portas.items():
            try:
                sp = SwitchesPorts.objects.get(switch=switch, port=port)
            except SwitchesPorts.DoesNotExist as e:
                sp = SwitchesPorts()
            sp.switch = switch
            sp.port = port
            sp.speed = pdata['speed']
            sp.duplex = pdata['duplex']
            sp.admin = pdata['admin']
            sp.oper = pdata['oper']
            sp.lastchange = pdata['lastchange']
            sp.discards_in = pdata['discards_in']
            sp.discards_out = pdata['discards_out']
            sp.oct_in = pdata['oct_in']
            sp.oct_out = pdata['oct_out']
            sp.stp_admin = pdata['stp_admin']
            sp.stp_state = pdata['stp_state']
            sp.poe_admin = pdata['poe_admin']
            sp.poe_detection = pdata['poe_detection']
            sp.poe_class = pdata['poe_class']
            sp.poe_mpower = pdata['poe_mpower']
            sp.mac_count = 0
            sp.pvid = pdata['pvid']
            sp.port_tagged = ', '.join(pdata['tagged'])
            sp.port_untagged = ', '.join(pdata['untagged'])
            sp.data = now()
            sp.name = pdata['nome'][0:30]
            sp.alias = pdata['alias'][0:80]
            #print('##>>> ... ... {}, {}, {}, admin={}, oper={}, stp_admin={}, poe_admin={}; poe_mpower={}, pvid={}'.format(
            #      port, sp.name, sp.speed, sp.admin, sp.oper, sp.stp_admin, sp.poe_admin, sp.poe_mpower, sp.pvid), 
            #      file=sys.stderr, end='')
            if not dryrun:
                try:
                    sp.save()
                except IntegrityError as e:
                    print("##>>>  Error saving port {}: {}".format(sp.port, e), file=sys.stderr, end='')

        SwitchesNeighbors.objects.filter(mac1=switch.mac).delete()
        for lport in o.uplink:
            # omac, oport = o.lldp[lport]
            omac = o.lldp[lport]['rmac']
            oport = o.lldp[lport]['rport']
            sn = SwitchesNeighbors(mac1=switch.mac, port1=lport, mac2=omac, port2=oport)
            if not dryrun:
                sn.save()

        # macs can appear duplicated due several reasons, like several wifi ports or trunking ports.
        # so, we will create a dict to clean, letting the last entry overwrite the last value.
        macs = {}
        for (port, mac, vlan) in o.macs:
            macs[(switch.id, mac, vlan)] = port
        Mac.objects.filter(switch=switch).delete()
        for (_, mac, vlan), port in macs.items():
            # m = Mac(switch=switch, mac=mac, vlan=vlan, port=port, data=datetime.now())
            m = Mac(switch=switch, mac=mac, vlan=vlan, port=port, data=now())
            if s_core:
                m.ip = s_core.ip_mac[mac] if mac in s_core.ip_mac else ''
            if not dryrun:
                try:
                    m.save()
                except Exception as e:
                    print("#>>> error saving mac: {}".format(e), file=sys.stderr, end='')

    # updating the mac_count field in SwitchesPorts is much easier through database.
    if not dryrun:
        with connection.cursor() as cursor:
            cursor.execute("UPDATE switches_ports SET mac_count=(select count(*) from mac where "
                           "mac.switch=switches_ports.switch and mac.port=switches_ports.port)")
    endtime = time.perf_counter() - start
    print("-- *** Execution total time: %5.01f s" % endtime, file=sys.stderr, end='')
    return


def _load_host(host, community, switchid):
    """
    Obtain all data from a switch through SNMP.
    Small piece of code used to parallelize switches probes called by Thread class
    :param host: hostname / IP (mainly last one) of the switch
    :param community: the community used by this host
    :param switchid: id from database. -1 if nonexistent
    :return: integer value with status. 3=ok, 2 and 1 are problems. Not really used.
    """
    global switches_list
    global IP_CORE
    global lock 
    obj = SwitchFactory().factory(host, community)
    if not obj:
        return 1
    obj.id = switchid
    start1 = time.perf_counter()
    try:
        obj.load()
    except Exception as e:
        import traceback
        logging.debug("-- %% _load_host(): host {} got exception in load(): {}\n----- Trace: {}".
                      format(host, e, traceback.print_exc()))
        return 2
    try:
        # if stp_root (main / sole switch), then try to get the IP-MAC relation
        if obj.stp == 0:
            obj.get_ip_mac()
            IP_CORE = host
            logging.debug('-- %% found core: {}'.format(host))
        obj.totaltime = "%3.01f s" % (time.perf_counter() - start1)
    except Exception as e:
        logging.debug("-- %% _load_host: host {} error getting assessing some data: {}".format(host, e))
        return 2

    if not lock.acquire(timeout=30):
        logging.debug("-- %% host {} was locked out and couldn't be inserted back into list. ".format(host))
        return 3
    switches_list[host] = obj
    lock.release()
    return 0


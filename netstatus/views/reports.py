from django.shortcuts import render
from django.db import connection

from ..models import ListMacHistory, Switches


def _format_list_rawquery(fields, table, order_by):
    """
    common query and tables used to check when some device last appeared in our net
    :param fields: specific fields used by table
    :param table: the database table used by this device to storage its configuration (mac is a must)
    :param order_by: field of 'table' to sort the query
    :return:
    """
    return '''
    SELECT 
        (select name from switches where id=z.switch) as last_sname, z.port as last_port, z.data as last_seen,
        (select name from switches where id=m.switch) as sname,
        r.mac as mac,
        r.ip as ip, 
        m.port as port, 
        m.data as data,
        {}
    FROM {} r LEFT JOIN mac m 
    ON r.mac=m.mac
    LEFT OUTER JOIN  mat_listMacHistory as z ON (r.mac=z.mac)
    ORDER BY r.{}, m.data DESC, last_seen DESC
    '''.format(fields, table, order_by)


def printers_list(request):
    object = ListMacHistory.objects.raw(_format_list_rawquery(
        'hrdesc, dns, name, serial, brand',
        'printer',
        'mac',
    ))
    return render(request, 'printer_list.html', {"device": object})


def voip_list(request):
    object = ListMacHistory.objects.raw(_format_list_rawquery(
        'branch, name, depto',
        'voip',
        'branch',
    ))
    return render(request, 'voip_list.html', {"device": object})


def wifi_list(request):
    object = ListMacHistory.objects.raw(_format_list_rawquery(
        'ip6, name',
        'wifi',
        'mac',
    ))
    return render(request, 'wifi_list.html', {"device": object})


def surv_list(request):
    object = ListMacHistory.objects.raw(_format_list_rawquery(
        'type, comments',
        'surveillance',
        'mac',
    ))
    return render(request, 'surv_list.html', {"device": object})


def report_view(request):
    switches = Switches.objects.all().order_by('vendor', 'soft_version', 'mac')
    switches_ports = {}
    with connection.cursor() as cursor:
        cursor.execute("SELECT count(*), (speed *(oper-2)*-1) as speed, (CASE (duplex-(oper*2)) WHEN 0 THEN 'half' "
                       "WHEN 1 THEN 'full' ELSE '0' END) as duplex, switches.name as name  FROM switches_ports inner "
                       "join switches on (switch=switches.id) WHERE status='active'  GROUP BY 4,2,3 ORDER BY 4,2,3")
        sum_ports = {
            '0_0': 0,
            '10_half': 0,
            '10_full': 0,
            '100_half': 0,
            '100_full': 0,
            '1000_full': 0,
        }
        total = 0
        # count, speed, duplex, name
        for i in cursor.fetchall():
            if i[3] not in switches_ports:
                switches_ports[i[3]] = {
                    '0_0': '-',
                    '10_half': '-',
                    '10_full': '-',
                    '100_half': '-',
                    '100_full': '-',
                    '1000_full': '-',
                }
            switches_ports[i[3]]['{}_{}'.format(i[1], i[2])] = i[0]
            total += i[0]
            sum_ports['{}_{}'.format(i[1], i[2])] += i[0]
        switches_ports['Total'] = sum_ports
    return render(request, 'report.html', {'switches': switches, 'switches_ports': switches_ports, 'total': total})


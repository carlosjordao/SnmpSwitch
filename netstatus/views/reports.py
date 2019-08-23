from django.shortcuts import render

from ..models import ListMacHistory


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

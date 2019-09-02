from django.http import StreamingHttpResponse, HttpResponse
from django.shortcuts import render

from netstatus.lib.snmpprinter import probe_snmp_printer
from netstatus.lib.updatestatus import probe_update_host, probe_update_db
from netstatus.lib.neighbors import probe_switch_neighbors


def probe_view(request):
    return render(request, 'probe.html')


def probe_service(request, service, target='', community='public'):
    if request.method == 'POST':
        return HttpResponse('invalid request.')

    if service == 'printer':
        response = probe_snmp_printer(target, community)

    elif service == 'switch':
        response = probe_update_host(target, community)

    elif service == 'neighbors':
        response = probe_switch_neighbors(target, community)

    elif service == 'updatedb':
        response = probe_update_db()

    else:
        return HttpResponse('invalid service: {}'.format(service))

    response = '\n'.join(['<pre>', *response, '</pre>'])
    return StreamingHttpResponse(response)

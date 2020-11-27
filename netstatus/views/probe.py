from django.http import StreamingHttpResponse, HttpResponse
from django.shortcuts import render
from netsnmp._api import SNMPError

from netstatus.lib.snmpprinter import probe_snmp_printer
from netstatus.lib.probe import probe_update_host, probe_update_db, inspect_host
from netstatus.lib.neighbors import probe_switch_neighbors

from netstatus.lib.snmp import PseudoSnmp

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
    return HttpResponse(response)


def inspect_service(request, target='', community='public'):
    if request.method == 'POST':
        return HttpResponse('invalid request.')
    if request.GET.get('mock', '') != '':
        target = PseudoSnmp(target)
        target.start()
    try:
        obj = inspect_host(target, community)
        if obj is None:
            return HttpResponse("");
    except SNMPError as e1:
        return HttpResponse("ERROR: Hostname probably invalid. " + str(e1));
    except Exception as e2:
        return HttpResponse("ERROR: " + str(e2));
    # TODO: add a failure template
    obj.mask__name = obj._mask.__name__
    obj.class__name = obj.__class__.__name__
    return render(request, 'inspect-host.html', {'switch': obj})

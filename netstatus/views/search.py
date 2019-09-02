from django.http import JsonResponse
from django.shortcuts import render
from rest_framework.decorators import api_view

from netstatus.models import ListMacHistory


@api_view(['GET', 'POST'])
def macip_api(request):
    """
    API endpoint that allows member to be viewed or edited made by function.
    """
    if request.method == 'GET':
        return render(request, 'search.html')

    # let's add a minimum length to search for, or the search will take too much
    if request.method == 'POST':
        if hasattr(request, 'data') and 'search[value]' in request.data:
            search = request.data['search[value]']
            if len(search) > 6:
                order = 'data DESC'
                if 'order[0][column]' in request.data:
                    order = '{} {}'.format(int(request.data['order[0][column]'])+1, request.data['order[0][dir]'][:4])
                filter_ip = ''
                if 'filter_ip' in request.data and request.data['filter_ip'] == 'true':
                    filter_ip = "ip <> '' AND "
                search = search + '%'
                queryset = ListMacHistory.objects.raw('''
                    SELECT mac, (select name from switches where id=switch) as sname, port, vlan, ip, data 
                    FROM mat_listmachistory m
                    WHERE (mac ilike %s or ip like %s) AND {0}
                        port not in (select stp_root from switches where switch=m.switch)
                    ORDER by {1}
                '''.format(filter_ip, order), (search, search))
                response = []
                for q in queryset:
                    data = {
                        'switch': q.sname,
                        'port': q.port,
                        'vlan': q.vlan,
                        'ip': q.ip,
                        'data': q.data,
                        'mac': q.mac,
                    }
                    response += [data]
                return JsonResponse({'draw': int(request.data['draw']),
                                     'recordsTotal': len(response),
                                     'recordsFiltered': len(response),
                                     'data': response,
                                     })
        return JsonResponse({'recordsTotal': 0, 'recordsFiltered': 0, 'data': {}})

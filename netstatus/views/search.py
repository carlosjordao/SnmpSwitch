from django.http import JsonResponse
from django.shortcuts import render
from requests import Response
from rest_framework import status
from rest_framework.decorators import api_view

from netstatus.models import ListMacHistory, Switches


# api_view
@api_view(['GET', 'POST'])
def macip_api(request):
    """
    API endpoint that allows member to be viewed or edited made by function.
    """
    if request.method == 'GET':
        return render(request, 'search.html')

    # let's add a minimum length to search for, or the search will take too much
    if request.method == 'POST':
        if request.data and 'search[value]' in request.data:
            search = request.data['search[value]']
            if len(search) > 6:
                order = 'data DESC'
                if 'order[0][column]' in request.data:
                    order = '{} {}'.format(int(request.data['order[0][column]'])+1, request.data['order[0][dir]'])
                filter_ip = ''
                if 'filter_ip' in request.data and request.data['filter_ip'] == 'true':
                    filter_ip = "ip <> '' AND "
                queryset = ListMacHistory.objects.raw('''
                    SELECT mac, (select name from switches where id=switch) as sname, port, vlan, ip, data 
                    FROM mat_listmachistory m
                    WHERE (mac ilike '{0}%%' or ip like '{1}%%') AND {3}
                        port not in (select stp_root from switches where switch=m.switch)
                    ORDER by {2}
                '''.format(search, search, order, filter_ip))
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
                return JsonResponse({'draw': request.data['draw'],
                                     'recordsTotal': len(response),
                                     'recordsFiltered': 0,
                                     'data': response,
                                     })

                # return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        return Response({}, status=status.HTTP_400_BAD_REQUEST)

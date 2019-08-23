"""SnmpSwitch URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/1.10/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  url(r'^$', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  url(r'^$', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.conf.urls import url, include
    2. Add a URL to urlpatterns:  url(r'^blog/', include('blog.urls'))
"""
from django.urls import path, include
from rest_framework.urlpatterns import format_suffix_patterns

from .views import switches_list, printers_list, voip_list, wifi_list, surv_list
from .views import macip_api, probe_view, probe_service, report_view

urlpatterns = [
    path('', switches_list),
    path('printers-list/', printers_list),
    path('voip-list/', voip_list),
    path('wifi-list/', wifi_list),
    path('surv-list/', surv_list),
    path('search/', macip_api),
    path('report/', report_view),
    path('probe/', probe_view),
    path('probe/<str:service>', probe_service),
    path('probe/<str:service>/<str:target>/<str:community>', probe_service),
    path('probe/<str:service>/<str:target>/<str:community>/', probe_service),
]

urlpatterns = format_suffix_patterns(urlpatterns)


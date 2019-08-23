ABOUT
-------
SnmpSwitch is a project aiming probing network devices, mainly switches but other types too, and gathering some data through SNMP connections.

Its objective is *not* do what other monitoring softwares do, like Zabbix and Nagios, which already do that very well. Instead, it's something about device configuration state that can obtained through SNMP.

For example, the main objective is collect data from switches in the network, store the port configuration about uplink, STP, POE, VLANs and things connected to that port, in such way that allows spot easily something misconfigured or finding where some device is connect to.

The hard part is all interesting data are in proprietary MIBs and need to be programmed individually, as not all switches has support for some data in SNMP (like interface vlan) or the data available is not enough for this software purpose.

The current version supports some switches, like 3Com 4500G, Huawei S5720, D-LING DGS3420, some HPs (A5200, A3600). Similar devices to this should work fine, as each switch model are close, but some other needs a little tweak sometimes to befully working.

Use this software at your own risk


INSTALL
----------
* Depends on: psycopg2, django, python 3, netsnmp-py
* netsnmp-py is installed through pip:
	* depends on (debian / ubuntu): libsnmp-dev, libzmq3-dev, libczmq-dev
	pip install netstnmp-py
* postgresql server

* This software uses PostgreSQL as there are functions and rules to spice some things.
* create a database and use the snmpswitch.sql to create tables and everything else.
* this github is the django project. If you already have a server with python and django, you may import the 'netstatus' app
* new switches are inserted through the web interface 'Probe the Net' > 'Probe one switch'
* new printers follows the same path.
* other data, like voip, cameras or wireless devices should be add through django admin, or directly to the database.


USE
-----
* after inserting all switches you want, you should see them on 'Network Status' link
* you may use crontab or any other type of job manager to call the URL /probe/updatedb, as this will read the database and update all switches stored in there. 
* you should protect the above link, or even the entire application, with a firewall or django auth (the last is not included).


Evolution
-----------
* include more vendors / models
* expand to more functionalities
* recognize more network devices.

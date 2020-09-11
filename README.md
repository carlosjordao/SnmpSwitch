# ABOUT
SnmpSwitch is a project aiming probing network devices, mainly switches but not exclusively, and gathering some data through SNMP connections with Python 3 and Django.

Its objective is *not* do what other monitoring softwares do, like Zabbix and Nagios, which already do that very well. Instead, it's something about device configuration state management that can obtained through SNMP.

For example, the main objective is to collect data from switches in the network, store configuration about uplink, STP, POE, VLANs, MAC and any interesting things connected to a switch port, in such way that allows anyone to spot easily something misconfigured or finding where some device is connect to.

The hard part of this project is intregrating several proprietary MIBs as many interesting things are only available in there and not in the IETF MIB tree, which means that needs to be programmed individually, as not all switches has support for some data in SNMP (like interface vlan) or the data available is not enough for this software purpose.

The current version supports some switches, like 3Com 4500G, Huawei S5720, D-LING DGS3420, some HPs (A5200, A3600). Similar devices to those should work fine, as they may share enough parts of the MIB tree, but some other needs a little tweak to befully operational.

Use this software at your own risk.

# Preview
![image1](https://i.imgur.com/keA4LvH.png)
![image2](https://i.imgur.com/AlOLTJM.png)

# INSTALL
  apt install python3 python3-psycopg2 pip libsnmp-dev libzmq3-dev libczmq-dev postgresql
  pip3 install netstnmp-py django djangorestframework

  * Depends on: psycopg2, django (and rest_framework module), python 3, netsnmp-py
  * netsnmp-py is installed through pip:
    * install depends on some packages (debian / ubuntu): libsnmp-dev, libzmq3-dev, libczmq-dev
        * they should be installed manually before attempting to install netsnmp-py
  * postgresql server (remember to configure pg_hba.conf)

  * look after SnmpSwitch/settings.py for database and other configurations (put your server name/IP on ALLOW_HOSTS)

  * This software uses PostgreSQL as there are functions, procedures and rules to spice some things.
  * create a database called "snmpswitch" and use the snmpswitch.sql to create tables and other structures.
  * You should create the database first, through snmpswitch.sql, as it has several rules and functions to improve some background actions (on delete, on insert, etc), allowing the app to be simpler.
  * this github stores a django project. If you already have a server with python and django, you may import only the 'netstatus' app.
  * new switches are inserted through the web interface 'Probe the Net' > 'Probe one switch'
  * new printers follows the same path.
  * other data, like voip, cameras or wireless devices should be add through django admin interface, or directly to the database.


# USE
  1. use: python3 manage.py migrate
	* this will connect and create the database tables for you. You only need to create beforehand the database.
  2. after that, add some extra tables, functions and rules to postgres. For now, they will add some kind of log upon some alterations. Add all necessary parameters to this command:
    psql -d snmpswitch < SnmpSwitch/snmpswitch-functions.sql

  3. Go to "Probe" section and try probing each switch you need. After inserting all switches you want, you should see them on 'Network Status' link
	* altough there isn't a interface to bulk insert, you can use scripts with the URL http://<site>/probe/switch/<ip>/<community>

  * There is an admin interface (provided with django admin) to insert into the database VOIP and other things. You should create a superuser to log on. The URL is http://<site>/admin
  * you may use crontab or any other type of job manager to call the URL /probe/updatedb, as this will read the database and update all switches stored in there. 
  * you should protect the above link, or even the entire application, with a firewall or django auth (the last is not included).
  * Use crontab to run this SQL commands for database maintenance (1x per week):
	 select * from mac_history(); delete from mac_log; REFRESH MATERIALIZED VIEW mat_listmachistory 


# Evolution
  * include more vendors / models
  * expand to more functionalities
  * recognize more network devices.

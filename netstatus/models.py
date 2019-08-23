# This is an auto-generated Django model module.
# You'll have to do the following manually to clean this up:
#   * Rearrange models' order
#   * Make sure each model has one field with primary_key=True
#   * Make sure each ForeignKey has `on_delete` set to the desired behavior.
#   * Remove `managed = True` lines if you wish to allow Django to create, modify, and delete the table
# Feel free to rename the models, but don't rename db_table values or field names.
from __future__ import unicode_literals

from django.db import models
from django.db.models import DEFERRED
from django.db.models.functions import datetime


class Ipv6(models.Model):
    ip6 = models.CharField(max_length=50)
    mac = models.CharField(max_length=17)

    class Meta:
        managed = True
        db_table = 'ipv6'
        unique_together = (('ip6', 'mac'),)


class Mac(models.Model):
    id = models.IntegerField(primary_key=True)
    switch = models.ForeignKey('Switches', models.DO_NOTHING, db_column='switch', blank=False, null=False, default=0,
                               related_name='mac_switch')
    mac = models.CharField(max_length=17, default='', blank=False, null=False)
    port = models.SmallIntegerField()
    vlan = models.SmallIntegerField()
    ip = models.CharField(max_length=15, blank=True, null=True)
    data = models.DateTimeField(auto_now_add=True, blank=False)

    class Meta:
        managed = True
        db_table = 'mac'
        unique_together = (('switch', 'mac', 'vlan'),)


class Printer(models.Model):
    dns = models.CharField(max_length=30)
    ip = models.CharField(max_length=15)
    mac = models.CharField(unique=True, max_length=17, primary_key=True)
    hrdesc = models.CharField(max_length=180)
    name = models.CharField(max_length=80)
    serial = models.CharField(max_length=30)
    brand = models.CharField(max_length=180)

    class Meta:
        managed = True
        db_table = 'printer'


class Switches(models.Model):
    id = models.AutoField(primary_key=True)
    STATUS = (('active', 'active'), ('stored', 'stored '), ('discarded', 'discarded'), ('repair', 'repair'),
              ('inactive_script', 'inactive_script'))
    name = models.CharField(max_length=40)
    alias = models.CharField(max_length=7)
    mac = models.CharField(unique=True, max_length=17)
    ip = models.CharField(max_length=39)
    model = models.CharField(max_length=60, blank=True, null=True)
    serial_number = models.CharField(unique=True, max_length=40)
    status = models.TextField(choices=STATUS)  # This field type is a guess.
    vendor = models.CharField(max_length=30, blank=True, null=True)
    soft_version = models.CharField(max_length=80, blank=True, null=True)
    stp_root = models.SmallIntegerField(blank=True, null=True)
    community_ro = models.CharField(max_length=20)
    community_rw = models.CharField(max_length=20)

    class Meta:
        managed = True
        db_table = 'switches'


class SwitchesPorts(models.Model):
    id = models.AutoField(primary_key=True)
    switch = models.ForeignKey(Switches, models.DO_NOTHING, db_column='switch', blank=False, null=False, default=0, related_name='ports')
    port = models.SmallIntegerField(blank=False)
    speed = models.IntegerField()
    duplex = models.SmallIntegerField()
    admin = models.SmallIntegerField()
    oper = models.SmallIntegerField()
    lastchange = models.BigIntegerField()
    discards_in = models.BigIntegerField()
    discards_out = models.BigIntegerField()
    stp_admin = models.SmallIntegerField()
    stp_state = models.SmallIntegerField()
    poe_admin = models.SmallIntegerField()
    poe_detection = models.SmallIntegerField()
    poe_class = models.SmallIntegerField()
    poe_mpower = models.SmallIntegerField()
    mac_count = models.SmallIntegerField()
    pvid = models.SmallIntegerField()
    port_tagged = models.CharField(max_length=2000)
    port_untagged = models.CharField(max_length=80)
    data = models.DateTimeField()
    name = models.CharField(max_length=30)
    alias = models.CharField(max_length=80)
    oct_in = models.BigIntegerField()
    oct_out = models.BigIntegerField()

    class Meta:
        managed = True
        db_table = 'switches_ports'
        unique_together = (('switch', 'port'),)


class SwitchesNeighbors(models.Model):
    id = models.IntegerField(primary_key=True)
    mac1 = models.CharField(max_length=17)
    port1 = models.SmallIntegerField()
    mac2 = models.CharField(max_length=17)
    port2 = models.SmallIntegerField()

    class Meta:
        managed = True
        db_table = 'switches_neighbors'
        unique_together = (('mac1', 'port1', 'mac2'),)


class Surveillance(models.Model):
    mac = models.CharField(unique=True, max_length=17, primary_key=True)
    type = models.TextField(db_column='type')  # This field type is a guess.
    ip = models.CharField(max_length=15)
    comments = models.TextField()
    name = models.CharField(max_length=80)

    class Meta:
        managed = True
        db_table = 'surveillance'


class Voip(models.Model):
    branch = models.SmallIntegerField(primary_key=True)
    name = models.CharField(max_length=60)
    display = models.CharField(max_length=40)
    depto = models.CharField(max_length=80)
    ip = models.CharField(max_length=15)
    mac = models.CharField(max_length=17, unique=True)

    class Meta:
        managed = True
        db_table = 'voip'


class Wifi(models.Model):
    mac = models.CharField(primary_key=True, max_length=17)
    ip = models.CharField(max_length=15)
    ip6 = models.CharField(max_length=50)
    name = models.CharField(max_length=20)
    optionv4 = models.TextField()
    optionv6 = models.TextField()
    comments = models.TextField()

    class Meta:
        managed = True
        db_table = 'wifi'


class ListMacHistory(models.Model):
    """
    Read-only class. The mat_listMacHistory is a materialized view to speed up searches upon mac history
    """
    switch = models.ForeignKey('Switches', models.DO_NOTHING, db_column='switch', blank=False, null=False, default=0, related_name='hist_switch')
    mac = models.CharField(max_length=17, default='', blank=False, null=False)
    port = models.SmallIntegerField()
    vlan = models.SmallIntegerField()
    ip = models.CharField(max_length=15, blank=True, null=True)
    data = models.DateTimeField(primary_key=True)

    def save(self, *args, **kwargs):
        return

    def delete(self, *args, **kwargs):
        return

    class Meta:
        managed = False
        db_table = 'mat_listmachistory'

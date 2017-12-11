#!/usr/bin/env python3

import humanfriendly
import json
import logging
import os
from random import randint
import threading
import time
import click
from container_service_extension.cluster import load_from_metadata
from container_service_extension.cluster import TYPE_MASTER
from container_service_extension.cluster import TYPE_NODE
from container_service_extension.config import get_config
import logging
import pkg_resources
from pyvcloud.vcd.client import _WellKnownEndpoint
from pyvcloud.vcd.client import BasicLoginCredentials
from pyvcloud.vcd.client import Client
from pyvcloud.vcd.client import EntityType
from pyvcloud.vcd.client import QueryResultFormat
from pyvcloud.vcd.client import RelationType
from pyvcloud.vcd.client import TaskStatus
from pyvcloud.vcd.org import Org
from pyvcloud.vcd.task import Task
from pyvcloud.vcd.vapp import VApp
from pyvcloud.vcd.vdc import VDC
from vsphere_guest_run.vsphere import VSphere
import re
import requests
import threading
import time
import traceback
import uuid
import yaml
from vcd_cli.utils import stdout
import random
import sys

def get_unit_number(vm_resource, disk_resource):
    for d in vm_resource.VmSpecSection.DiskSection.DiskSettings:
        if hasattr(d, 'Disk') and d.Disk.get('href') == disk_resource.get('href'):
            return d.UnitNumber.text
    return None

def mount_disk(config, org_name, vdc_name, vapp_name, vm_name, disk_name):
    print('host:')
    print(config['vcd']['host'])
    client_sysadmin = Client(
        uri=config['vcd']['host'],
        api_version=config['vcd']['api_version'],
        verify_ssl_certs=config['vcd']['verify'],
        log_file='sysadmin.log',
        log_headers=True,
        log_bodies=True)
    client_sysadmin.set_credentials(
        BasicLoginCredentials(config['vcd']['username'], 'System', config['vcd']['password']))
    org_resource = client_sysadmin.get_org_by_name(org_name)
    print('org:', org_name)
    org = Org(client_sysadmin, href=org_resource.get('href'))
    print(org_resource.get('href'))
    print('vdc:', vdc_name)
    vdc_resource = org.get_vdc(vdc_name)
    print(vdc_resource.get('href'))
    vdc = VDC(client_sysadmin, resource=vdc_resource)
    print('vapp:', vapp_name)
    vapp_resource = vdc.get_vapp(vapp_name)
    vapp = VApp(client_sysadmin, resource=vapp_resource)
    print(vapp_resource.get('href'))
    print('vm:', vm_name)
    vm_resource = vapp.get_vm(vm_name)
    print(vm_resource.get('href'))
    print('disk:', disk_name)
    disk_resource = vdc.get_disk(disk_name)
    print(disk_resource.get('href'))
    unit_number = get_unit_number(vm_resource, disk_resource)
    print('Unit:', unit_number)

    moid = vapp.get_vm_moid(vm_name)

    vs = VSphere(config['vcs']['host'], config['vcs']['username'],
                 config['vcs']['password'], port=int(config['vcs']['port']))
    vs.connect()
    vm = vs.get_vm_by_moid(moid)

    script = 'for i in $(ls /sys/class/scsi_host/); do echo 0 0 0 > /sys/class/scsi_host/$i/scan; done;'
    result = vs.execute_script_in_guest(vm, 'root',
                                        config['broker']['password'],
                                        script, wait_for_completion=True,
                                        wait_time=1, get_output=True)
    print(result[0])
    print(result[1].content.decode())
    print(result[2].content.decode())

    command = '/bin/ls /sys/bus/scsi/devices/2:0:{unit}:0/block'.format(unit=unit_number)
    result = vs.execute_program_in_guest(vm, 'root',
                                         config['broker']['password'],
                                         command, wait_for_completion=True,
                                         wait_time=1, get_output=True)

    device_name = result[1].content.decode().rstrip()
    print('device_name:', device_name)
    device = '/dev/' + device_name
    print('device:', device)

    # command = '/sbin/fdisk -l /dev/{device_name}'.format(device_name=device_name)
    # result = vs.execute_program_in_guest(vm,
    #                             'root',
    #                             config['broker']['password'],
    #                             command,
    #                             wait_for_completion=True,
    #                             wait_time=1,
    #                             get_output=True)
    # disk_info = result[1].content.decode()

    script = """
if [ -b {device} ]
then
    echo -e 'n\n\n\n\n\nw' | fdisk {device}
    partprobe {device}
    mkfs -t ext4 {device}1
    mkdir /mnt/{disk_name}
    cat <<EOF >> /etc/fstab
{device}1\t/mnt/{disk_name}\text4\tdefaults\t0\t0
EOF
    mount {device}1
fi
""".format(device=device, disk_name=disk_name)
    print(script)
    result = vs.execute_script_in_guest(vm, 'root',
                                        config['broker']['password'],
                                        script, wait_for_completion=True,
                                        wait_time=1, get_output=True,
                                        target_file='/root/floppylion.sh',
                                        delete_script=True)
    print(result[0])
    print(result[1].content.decode())
    print(result[2].content.decode())


if __name__ == '__main__':
    config = get_config(sys.argv[1])
    mount_disk(config, sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5], sys.argv[6])

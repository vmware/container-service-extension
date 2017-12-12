# container-service-extension
# Copyright (c) 2017 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

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
from pyvcloud.vcd.utils import stdout_xml
import os
import glob
import copy


LOGGER = logging.getLogger(__name__)

SLEEP_TIME = 2

def get_unit_number(vm_resource, disk_resource):
    for d in vm_resource.VmSpecSection.DiskSection.DiskSettings:
        if hasattr(d, 'Disk') and d.Disk.get('href') == disk_resource.get('href'):
            return d.UnitNumber.text
    return None

class PVProvisioner(threading.Thread):
    def __init__(self, config):
        threading.Thread.__init__(self)
        self.config = config
        self.host = config['vcd']['host']
        self.username = config['vcd']['username']
        self.password = config['vcd']['password']
        self.version = config['vcd']['api_version']
        self.verify = config['vcd']['verify']
        self.log = config['vcd']['log']
        LOGGER.setLevel(logging.DEBUG)
        handler = logging.FileHandler('pv.log')
        formatter = logging.Formatter(
            '%(asctime)s | '
            '%(levelname)s | '
            '%(module)s-'
            '%(funcName)s-'
            '%(lineno)s | '
            '%(message)s')
        handler.setFormatter(formatter)
        LOGGER.addHandler(handler)

    def _connect_sysadmin(self):
        self.client_sysadmin = Client(
            uri=self.host,
            api_version=self.version,
            verify_ssl_certs=self.verify,
            log_file='sysadmin.log',
            log_headers=True,
            log_bodies=True)
        self.client_sysadmin.set_credentials(
            BasicLoginCredentials(self.username, 'System', self.password))

    def run(self):
        LOGGER.debug('PV provisioner thread started')
        if 'CSE_LOCAL' in os.environ:
            LOGGER.debug('local mode: %s' % os.environ['CSE_LOCAL'])
        while True:
            vs = VSphere(
                self.config['vcs']['host'],
                self.config['vcs']['username'],
                self.config['vcs']['password'],
                port=int(self.config['vcs']['port']))
            vs.connect()
            self._connect_sysadmin()
            q = self.client_sysadmin.get_typed_query(
                    'adminVApp',
                    query_result_format=QueryResultFormat.RECORDS,
                    qfilter='metadata:cse.cluster.status==STRING:ready;metadata:cse.node.type==STRING:' + TYPE_MASTER,
                    fields='metadata:cse.cluster.name' +
                           ',metadata:cse.cluster.id')
            records = list(q.execute())
            for record in records:
                cluster_name = ''
                cluster_id = ''
                if hasattr(record, 'Metadata'):
                    for me in record.Metadata.MetadataEntry:
                        if me.Key == 'cse.cluster.name':
                            cluster_name = me.TypedValue.Value
                        elif me.Key == 'cse.cluster.id':
                            cluster_id = me.TypedValue.Value

                vapp = VApp(self.client_sysadmin, href=record.get('href'))
                vapp_name = record.get('name')
                moid = vapp.get_vm_moid(vapp_name)
                LOGGER.debug('%s, %s, %s' % (cluster_name, vapp_name, moid))
                vm = vs.get_vm_by_moid(moid)
                try:
                    files = []
                    if 'CSE_LOCAL' in os.environ:
                        files = glob.glob(os.environ['CSE_LOCAL']+'/req/*.json')
                    else:
                        list_files = vs.list_files_in_guest(vm, 'root', self.config['broker']['password'], '/root/cse/req', pattern='.*.json')
                        for f in list_files.files:
                            files.append('/root/cse/req/'+f.path)
                    for f in files:
                        LOGGER.debug('PV request: %s' % f)
                        if 'CSE_LOCAL' in os.environ:
                            with open(f) as json_data:
                                json_request = json.load(json_data)
                        else:
                            response = vs.download_file_from_guest(vm, 'root', self.config['broker']['password'], f)
                            json_request = json.loads(response.content.decode('utf-8'))
                        json_response = None
                        try:
                            if 'spec' in json_request:
                                if 'claimRef' in json_request['spec']:
                                    if 'kind' in json_request['spec']['claimRef']:
                                        if json_request['spec']['claimRef']['kind'] == 'PersistentVolumeClaim':
                                            if json_request['status']['phase'] == 'Released':
                                                json_response = {'status':{'phase':''}}
                                                self.process_request_delete_pv(cluster_name, cluster_id, vapp, moid, json_request)
                            elif 'PVC' in json_request:
                                json_response = copy.deepcopy(json_request)
                                self.process_request_provision_pv(cluster_name, cluster_id, vapp, moid, json_request)
                            else:
                                pass
                        except Exception as e:
                            LOGGER.error(e, exc_info=True)
                            if 'PVC' in json_request:
                                json_response['PVC']['status']['phase'] = 'failed'
                                json_response['PVC']['status']['reason'] = str(e)
                                json_response['PVC']['status']['message'] = str(e)
                            else:
                                json_response['status']['phase'] = 'failed'
                                json_response['status']['reason'] = str(e)
                                json_response['status']['message'] = str(e)
                        if 'CSE_LOCAL' in os.environ:
                            os.remove(f)
                        else:
                            vs.delete_file_in_guest(vm, 'root', self.config['broker']['password'], f)
                        if json_response is not None:
                            f = f.replace('/req/', '/res/')
                            if 'CSE_LOCAL' in os.environ:
                                with open(f, 'w') as outfile:
                                    json.dump(json_response, outfile)
                            else:
                                vs.upload_file_to_guest(vm, 'root', self.config['broker']['password'], json.dumps(json_response), f)
                except Exception as e:
                    LOGGER.error(e, exc_info=True)

            time.sleep(SLEEP_TIME)

    def process_request_provision_pv(self, cluster_name, cluster_id, vapp, moid, json_request):
        vdc_resource = self.client_sysadmin.get_linked_resource(vapp.resource, RelationType.UP, EntityType.VDC.value)
        vdc = VDC(self.client_sysadmin, resource=vdc_resource)
        disk_name_orig = json_request['PVC']['metadata']['name']
        disk_name = '%s-%s' % (cluster_name, disk_name_orig)
        disk_size = json_request['PVC']['spec']['resources']['requests']['storage']

        d = None
        try:
            d = vdc.get_disk(disk_name)
        except Exception as e:
            if str(e).startswith('Found multiple'):
                raise Exception('disk already exists')
        if d is not None:
            raise Exception('disk already exists')

        # if disk doesn't exist:
        #     create it
        # if disk is already attached:
        #     raise Exception
        # attach disk to a vm
        # use disk id to create directory

        LOGGER.info('PV %s, creating new ind. disk, size: %s' % (disk_name, disk_size))
        disk_resource = vdc.add_disk(name=disk_name,
                                     size=humanfriendly.parse_size(disk_size),
                                     bus_type='6',
                                     bus_sub_type='VirtualSCSI')
        task_resource = self.client_sysadmin.get_task_monitor().wait_for_status(
            task=disk_resource.Tasks.Task[0],
            timeout=60,
            poll_frequency=2,
            fail_on_status=None,
            expected_target_statuses=[
                TaskStatus.SUCCESS,
                TaskStatus.ABORTED,
                TaskStatus.ERROR,
                TaskStatus.CANCELED])
        task_status = task_resource.get('status').lower()
        disk_id = disk_resource.get('id')
        disk_href = disk_resource.get('href')
        vapp_owner = vapp.resource.Owner.User.get('name')
        LOGGER.info('PV %s(%s), create status: %s' % (disk_name, disk_id, task_status))
        assert task_status == TaskStatus.SUCCESS.value
        vdc.reload()
        while True:
            d = self.client_sysadmin.get_resource(disk_href)
            if d.get('status') == '1':
                break
            else:
                LOGGER.info('PV %s(%s), disk status: %s' % (disk_name, disk_id, d.get('status')))
                time.sleep(2)
        LOGGER.info('PV %s(%s), changing owner to: %s' % (disk_name, disk_id, vapp_owner))
        change_disk_owner_result = vdc.change_disk_owner(disk_name,
                                     vapp.resource.Owner.User.get('href'),
                                     disk_id=disk_id)
        cluster = load_from_metadata(self.client_sysadmin,
                                     name=cluster_name,
                                     cluster_id=cluster_id)[0]
        LOGGER.info('PV %s(%s), load cluster: %s@%s' % (disk_name, disk_id, cluster['name'], cluster['vdc_name']))
        nodes = cluster['nodes']
        if len(nodes) == 0:
            nodes = cluster['master_nodes']
        for n in range(random.randrange(25)):
            target_node = random.choice(nodes)
        target_vapp = VApp(self.client_sysadmin, href=target_node['href'])
        target_moid = target_vapp.get_vm_moid(target_node['name'])
        LOGGER.info('PV %s(%s), attaching to: %s, moid: %s' % (disk_name, disk_id, target_node['name'], target_moid))
        task = target_vapp.attach_disk_to_vm(
            disk_href=disk_href,
            vm_name=target_node['name'])
        task_resource = self.client_sysadmin.get_task_monitor().wait_for_status(
            task=task,
            timeout=60,
            poll_frequency=2,
            fail_on_status=None,
            expected_target_statuses=[
                TaskStatus.SUCCESS,
                TaskStatus.ABORTED,
                TaskStatus.ERROR,
                TaskStatus.CANCELED])
        task_status = task_resource.get('status').lower()
        LOGGER.info('PV %s(%s), attach disk status: %s' % (disk_name, disk_id, task_status))
        assert task_status == TaskStatus.SUCCESS.value
        target_vapp.reload()
        vm_name = target_node['name']
        vm_resource = target_vapp.get_vm(vm_name)
        unit_number = get_unit_number(vm_resource, disk_resource)

        vs = VSphere(
            self.config['vcs']['host'],
            self.config['vcs']['username'],
            self.config['vcs']['password'],
            port=int(self.config['vcs']['port']))
        vs.connect()
        vm = vs.get_vm_by_moid(target_moid)
        max_retries = 25
        retry = 0
        device_name = None
        device = None
        path = None
        while retry < max_retries:
            script = 'for i in $(ls /sys/class/scsi_host/); do echo 0 0 0 > /sys/class/scsi_host/$i/scan; done;'
            result = vs.execute_script_in_guest(vm, 'root',
                                                self.config['broker']['password'],
                                                script, wait_for_completion=True,
                                                wait_time=1, get_output=True)
            LOGGER.info('PV %s(%s), scan scsi status: %s' % (disk_name, disk_id, result[0]))
            assert result[0] == 0
            command = '/bin/ls /sys/bus/scsi/devices/2:0:{unit}:0/block'.format(unit=unit_number)
            result = vs.execute_program_in_guest(vm, 'root',
                                                 self.config['broker']['password'],
                                                 command, wait_for_completion=True,
                                                 wait_time=1, get_output=True)
            LOGGER.info('PV %s(%s), get device status: %s' % (disk_name, disk_id, result[0]))
            if result[0] == 0:
                device_name = result[1].content.decode().rstrip()
                device = '/dev/' + device_name
                path = '/mnt/' + disk_name_orig
                break
            else:
                retry += 1
                LOGGER.error('PV %s(%s), retry: %s' % (disk_name, disk_id, retry))
                LOGGER.error('PV %s(%s), get device stdout: %s' % (disk_name, disk_id, result[1].content.decode()))
                LOGGER.error('PV %s(%s), get device stderr: %s' % (disk_name, disk_id, result[2].content.decode()))
                time.sleep(1)
        assert device is not None and path is not None
        script = """
if [ -b {device} ]
then
    echo -e 'n\n\n\n\n\nw' | fdisk {device}
    partprobe {device}
    echo 1 > /sys/block/{device_name}/device/rescan
    sync
    sync
    mkfs -t ext4 {device}1
    mkdir -p {path}
    cat <<EOF >> /etc/fstab
{device}1\t{path}\text4\tdefaults\t0\t0
EOF
    mount {device}1
fi
""".format(device=device, device_name=device_name, path=path)
        result = vs.execute_script_in_guest(vm, 'root',
                                            self.config['broker']['password'],
                                            script, wait_for_completion=True,
                                            wait_time=1, get_output=True)
        LOGGER.info('PV %s(%s), mount script status: %s, device: %s, path: %s' % (disk_name, disk_id, result[0], device, path))
        if result[0] != 0:
            LOGGER.error('PV %s(%s), mount script stdout: %s' % (disk_name, disk_id, result[1].content.decode()))
            LOGGER.error('PV %s(%s), mount script stderr: %s' % (disk_name, disk_id, result[2].content.decode()))
        else:
            LOGGER.info('PV %s(%s), bound, VM: %s, moid: %s, device: %s, path: %s' % (disk_name, disk_id, target_node['name'], target_moid, device, path))
        assert result[0] == 0


    def process_request_delete_pv(self, cluster_name, cluster_id, vapp, moid, json_request):
        vdc_resource = self.client_sysadmin.get_linked_resource(vapp.resource, RelationType.UP, EntityType.VDC.value)
        vdc = VDC(self.client_sysadmin, resource=vdc_resource)
        disk_name_orig = json_request['spec']['claimRef']['name']
        disk_uid = json_request['spec']['claimRef']['uid']
        disk_name = '%s-%s' % (cluster_name, disk_name_orig)

        disk_resource = vdc.get_disk(disk_name)

        vm_name = disk_resource.attached_vms.VmReference.get('name')
        vm_href = disk_resource.attached_vms.VmReference.get('href')
        vm_resource = self.client_sysadmin.get_resource(vm_href)
        vapp_resource = self.client_sysadmin.get_linked_resource(vm_resource, RelationType.UP, EntityType.VAPP.value)
        vapp_name = vapp_resource.get('name')

        LOGGER.info('PV %s, deleting ind. disk: %s, vapp: %s, vm: %s, pvc-uid: %s' % (disk_name_orig, disk_name, vapp_name, vm_name, disk_uid))

        disk_id = disk_resource.get('id')
        disk_href = disk_resource.get('href')

        target_vapp = VApp(self.client_sysadmin, resource=vapp_resource)
        target_moid = target_vapp.get_vm_moid(vm_name)
        LOGGER.debug('%s, %s, %s' % (cluster_name, vapp_name, target_moid))

        vs = VSphere(
            self.config['vcs']['host'],
            self.config['vcs']['username'],
            self.config['vcs']['password'],
            port=int(self.config['vcs']['port']))
        vs.connect()
        vm = vs.get_vm_by_moid(target_moid)
        script = """
umount -f /mnt/{dir}
sed -i '/\/mnt\/{dir}/d' /etc/fstab
""".format(dir=disk_name_orig)
        result = vs.execute_script_in_guest(vm, 'root',
                                            self.config['broker']['password'],
                                            script, wait_for_completion=True,
                                            wait_time=1, get_output=True)
        LOGGER.info('PV %s(%s), umount script status: %s, vm: %s' % (disk_name, disk_id, result[0], vm_name))
        if result[0] != 0:
            LOGGER.error('PV %s(%s), umount script stdout: %s' % (disk_name, disk_id, result[1].content.decode()))
            LOGGER.error('PV %s(%s), umount script stderr: %s' % (disk_name, disk_id, result[2].content.decode()))
        else:
            LOGGER.info('PV %s(%s), umount, VM: %s, moid: %s' % (disk_name, disk_id, vm_name, target_moid))
        assert result[0] == 0

        LOGGER.info('PV %s(%s), detaching from: %s, moid: %s' % (disk_name, disk_id, vm_name, target_moid))
        task = target_vapp.detach_disk_from_vm(
            disk_href=disk_resource.get('href'),
            disk_type=disk_resource.get('type'),
            disk_name=disk_resource.get('name'),
            vm_name=vm_name)
        task_resource = self.client_sysadmin.get_task_monitor().wait_for_status(
            task=task,
            timeout=60,
            poll_frequency=2,
            fail_on_status=None,
            expected_target_statuses=[
                TaskStatus.SUCCESS,
                TaskStatus.ABORTED,
                TaskStatus.ERROR,
                TaskStatus.CANCELED])
        task_status = task_resource.get('status').lower()
        LOGGER.info('PV %s(%s), detach disk status: %s' % (disk_name, disk_id, task_status))
        assert task_status == TaskStatus.SUCCESS.value

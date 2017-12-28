# container-service-extension
# Copyright (c) 2017 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

import logging

from pyvcloud.vcd.client import QueryResultFormat
from pyvcloud.vcd.client import TaskStatus
from pyvcloud.vcd.vapp import VApp
from pyvcloud.vcd.vm import VM

import random
import string
import time
from vsphere_guest_run.vsphere import VSphere

TYPE_MASTER = 'mstr'
TYPE_NODE = 'node'
LOGGER = logging.getLogger(__name__)
logging.basicConfig(filename='cse.log')


def wait_until_tools_ready(vm):
    while True:
        try:
            status = vm.guest.toolsRunningStatus
            if 'guestToolsRunning' == status:
                LOGGER.debug('vm tools %s are ready' % vm)
                return
            LOGGER.debug('waiting for vm tools %s to be ready (%s)' % (vm,
                                                                       status))
            time.sleep(1)
        except Exception:
            LOGGER.debug('waiting for vm tools %s to be ready (%s)* ' %
                         (vm, status))
            time.sleep(1)


def load_from_metadata(client, name=None, cluster_id=None,
                       get_leader_ip=False):
    clusters_dict = {}
    if cluster_id is None:
        query_filter = 'metadata:cse.cluster.id==STRING:*'
    else:
        query_filter = 'metadata:cse.cluster.id==STRING:%s' % cluster_id
    if name is not None:
        query_filter += ';name==%s' % name
    resource_type = 'vApp'
    if client.is_sysadmin():
        resource_type = 'adminVApp'
    q = client.get_typed_query(
        resource_type,
        query_result_format=QueryResultFormat.ID_RECORDS,
        qfilter=query_filter,
        fields='metadata:cse.cluster.id,metadata:cse.master.ip,'
        'metadata:cse.version,metadata:cse.template')
    records = list(q.execute())
    nodes = []
    for record in records:
        vapp_id = record.get('id').split(':')[-1]
        vdc_id = record.get('vdc').split(':')[-1]
        node = {
            'vapp_name': record.get('name'),
            'vdc_name': record.get('vdcName'),
            'vapp_id': vapp_id,
            'vapp_href': '%s/vApp/vapp-%s' % (client._uri, vapp_id),
            'vdc_href': '%s/vdc/%s' % (client._uri, vdc_id),
            'record': record,
            'master_ip': ''
        }
        if hasattr(record, 'Metadata'):
            for me in record.Metadata.MetadataEntry:
                if me.Key == 'cse.cluster.id':
                    node['cluster_id'] = str(me.TypedValue.Value)
                elif me.Key == 'cse.version':
                    node['cse_version'] = str(me.TypedValue.Value)
                elif me.Key == 'cse.master.ip':
                    node['master_ip'] = str(me.TypedValue.Value)
                elif me.Key == 'cse.template':
                    node['template'] = str(me.TypedValue.Value)
        nodes.append(node)
    for node in nodes:
        cluster = {}
        cluster['name'] = node['vapp_name']
        cluster['cluster_id'] = node['cluster_id']
        cluster['status'] = ''
        cluster['leader_endpoint'] = node['master_ip']
        cluster['vapp_id'] = node['vapp_id']
        cluster['vapp_href'] = node['vapp_href']
        cluster['vdc_name'] = node['vdc_name']
        cluster['vdc_href'] = node['vdc_href']
        cluster['master_nodes'] = []
        cluster['nodes'] = []
        cluster['number_of_vms'] = node['record'].get('numberOfVMs')
        cluster['template'] = node['template']
        clusters_dict[cluster['name']] = cluster
    return list(clusters_dict.values())


def add_nodes(qty,
              template,
              node_type,
              config,
              client,
              org,
              vdc,
              vapp,
              body,
              wait=True):
    if qty < 1:
        return None
    specs = []
    catalog_item = org.get_catalog_item(config['broker']['catalog'],
                                        template['catalog_item'])
    source_vapp = VApp(client, href=catalog_item.Entity.get('href'))
    source_vm = source_vapp.get_all_vms()[0].get('name')
    storage_profile = None
    if 'storage_profile' in body and body['storage_profile'] is not None:
        storage_profile = vdc.get_storage_profile(body['storage_profile'])
    cust_script_init = \
"""#!/usr/bin/env bash
if [ x$1=x"postcustomization" ];
then
""" # NOQA
    cust_script_common = \
"""
echo "root:{password}" | chpasswd
""".format(password=template['admin_password']) # NOQA
    if 'ssh_key' in body:
        cust_script_common += \
"""
mkdir -p /root/.ssh
echo '{ssh_key}' >> /root/.ssh/authorized_keys
chmod -R go-rwx /root/.ssh
""".format(ssh_key=body['ssh_key'])  # NOQA
    cust_script_end = \
"""
fi
"""  # NOQA
    cust_script = cust_script_init
    cust_script += cust_script_common
    cust_script += cust_script_end
    for n in range(qty):
        name = None
        while True:
            name = '%s-%s' % (node_type, ''.join(
                random.choices(string.ascii_lowercase + string.digits, k=4)))
            try:
                vapp.get_vm(name)
            except Exception:
                break
        spec = {
            'source_vm_name': source_vm,
            'vapp': source_vapp.resource,
            'target_vm_name': name,
            'hostname': name,
            'network': body['network'],
            'ip_allocation_mode': 'pool',
            'cust_script': cust_script
        }
        if storage_profile is not None:
            spec['storage_profile'] = storage_profile
        specs.append(spec)
    if ('cpu_count' in body and body['cpu_count'] is not None) or (
            'memory' in body and body['memory'] is not None):
        reconfigure_hw = True
    else:
        reconfigure_hw = False

    task = vapp.add_vms(specs, power_on=not reconfigure_hw)
    if wait:
        task = client.get_task_monitor().wait_for_status(
            task=task,
            timeout=600,
            poll_frequency=5,
            fail_on_status=None,
            expected_target_statuses=[
                TaskStatus.SUCCESS, TaskStatus.ABORTED, TaskStatus.ERROR,
                TaskStatus.CANCELED
            ],
            callback=None)
        if task.get('status').lower() != TaskStatus.SUCCESS.value:
            task_resource = client.get_resource(task.get('href'))
            if hasattr(task_resource, 'taskDetails'):
                raise Exception(task_resource.get('taskDetails'))
            elif hasattr(task_resource, 'Details'):
                raise Exception(task_resource.Details.text)
            else:
                raise Exception('Couldn\'t add node(s).')
    if wait and reconfigure_hw:
        vapp.reload()
        for spec in specs:
            vm_resource = vapp.get_vm(spec['target_vm_name'])
            if 'cpu_count' in body and body['cpu_count'] is not None:
                vm = VM(client, resource=vm_resource)
                task = vm.modify_cpu(body['cpu_count'])
                task = client.get_task_monitor().wait_for_status(
                    task=task,
                    timeout=600,
                    poll_frequency=5,
                    fail_on_status=None,
                    expected_target_statuses=[
                        TaskStatus.SUCCESS, TaskStatus.ABORTED,
                        TaskStatus.ERROR, TaskStatus.CANCELED
                    ],
                    callback=None)
            if 'memory' in body and body['memory'] is not None:
                vm = VM(client, resource=vm_resource)
                task = vm.modify_memory(body['memory'])
                task = client.get_task_monitor().wait_for_status(
                    task=task,
                    timeout=600,
                    poll_frequency=5,
                    fail_on_status=None,
                    expected_target_statuses=[
                        TaskStatus.SUCCESS, TaskStatus.ABORTED,
                        TaskStatus.ERROR, TaskStatus.CANCELED
                    ],
                    callback=None)
            vm = VM(client, resource=vm_resource)
            task = vm.power_on()
            if wait:
                task = client.get_task_monitor().wait_for_status(
                    task=task,
                    timeout=600,
                    poll_frequency=5,
                    fail_on_status=None,
                    expected_target_statuses=[
                        TaskStatus.SUCCESS, TaskStatus.ABORTED,
                        TaskStatus.ERROR, TaskStatus.CANCELED
                    ],
                    callback=None)
                if task.get('status').lower() != TaskStatus.SUCCESS.value:
                    task_resource = client.get_resource(task.get('href'))
                    if hasattr(task_resource, 'taskDetails'):
                        raise Exception(task_resource.get('taskDetails'))
                    elif hasattr(task_resource, 'Details'):
                        raise Exception(task_resource.Details.text)
                    else:
                        raise Exception('Couldn\'t add node(s).')
    return {'task': task, 'specs': specs}


def get_nodes(vapp, node_type):
    nodes = []
    for node in vapp.get_all_vms():
        if node.get('name').startswith(node_type):
            nodes.append(node)
    return nodes


def delete_nodes(node_names, client, vapp):
    pass


def wait_for_tools_ready_callback(message, exception=None):
    print('waiting for guest tools, status: %s' % message)
    LOGGER.debug('waiting for guest tools, status: %s' % message)
    if exception is not None:
        LOGGER.error('exception: %s' % str(exception))


def wait_for_guest_execution_callback(message, exception=None):
    LOGGER.debug(message)
    print(message)
    if exception is not None:
        LOGGER.error('exception: %s' % str(exception))


def get_init_info(config, vapp, password):
    script = \
"""#!/usr/bin/env bash
kubeadm token create
ip route get 1 | awk '{print $NF;exit}'
""" # NOQA
    nodes = get_nodes(vapp, TYPE_MASTER)
    result = execute_script_in_nodes(
        config, vapp, password, script, nodes, check_tools=False)
    return result[0][1].content.decode().split()


def get_master_ip(config, vapp, template):
    script = \
"""#!/usr/bin/env bash
ip route get 1 | awk '{print $NF;exit}'
""" # NOQA
    nodes = get_nodes(vapp, TYPE_MASTER)
    result = execute_script_in_nodes(
        config,
        vapp,
        template['admin_password'],
        script,
        nodes,
        check_tools=False)
    return result[0][1].content.decode().split()[0]


def get_cluster_config(config, vapp, password):
    file_name = '/root/.kube/config'
    nodes = get_nodes(vapp, TYPE_MASTER)
    result = get_file_from_nodes(
        config, vapp, password, file_name, nodes, check_tools=False)
    if len(result) == 0 or result[0].status_code != 200:
        raise Exception('Couldn\'t get cluster configuration')
    return result[0].content.decode()


def init_cluster(config, vapp, template):
    from container_service_extension.config import get_data_file
    script = get_data_file('mstr-%s.sh' % template['name'])
    nodes = get_nodes(vapp, TYPE_MASTER)
    result = execute_script_in_nodes(config, vapp, template['admin_password'],
                                     script, nodes)
    if result[0][0] != 0:
        raise Exception('Couldn\'t initialize cluster:\n%s' %
                        result[0][2].content.decode())


def join_cluster(config, vapp, template):
    from container_service_extension.config import get_data_file
    init_info = get_init_info(config, vapp, template['admin_password'])
    tmp_script = get_data_file('node-%s.sh' % template['name'])
    script = tmp_script.format(token=init_info[0], ip=init_info[1])
    nodes = get_nodes(vapp, TYPE_NODE)
    results = execute_script_in_nodes(config, vapp, template['admin_password'],
                                      script, nodes)
    for result in results:
        if result[0] != 0:
            raise Exception(
                'Couldn\'t join cluster:\n%s' % result[2].content.decode())


def wait_until_ready_to_exec(vs, vm, password, tries=30):
    ready = False
    script = \
"""#!/usr/bin/env bash
uname -a
""" # NOQA
    for n in range(tries):
        try:
            result = vs.execute_script_in_guest(
                vm,
                'root',
                password,
                script,
                target_file=None,
                wait_for_completion=True,
                wait_time=5,
                get_output=True,
                delete_script=True,
                callback=wait_for_guest_execution_callback)
            if result[0] == 0:
                ready = True
                break
            raise Exception('script returned %s' % result[0])
        except Exception:
            print('VM is not ready to execute scripts, yet')
            time.sleep(2)
    if not ready:
        raise Exception('VM is not ready to execute scripts')


def execute_script_in_nodes(config,
                            vapp,
                            password,
                            script,
                            nodes,
                            check_tools=True):
    vs = VSphere(
        config['vcs']['host'],
        config['vcs']['username'],
        config['vcs']['password'],
        port=int(config['vcs']['port']))
    vs.connect()
    all_results = []
    for node in nodes:
        LOGGER.debug('running script on %s' % node.get('name'))
        print('running script on %s' % node.get('name'))
        moid = vapp.get_vm_moid(node.get('name'))
        vm = vs.get_vm_by_moid(moid)
        if check_tools:
            vs.wait_until_tools_ready(
                vm, sleep=5, callback=wait_for_tools_ready_callback)
            wait_until_ready_to_exec(vs, vm, password)
        result = vs.execute_script_in_guest(
            vm,
            'root',
            password,
            script,
            target_file=None,
            wait_for_completion=True,
            wait_time=10,
            get_output=True,
            delete_script=True,
            callback=wait_for_guest_execution_callback)
        result_stdout = result[1].content.decode()
        result_stderr = result[2].content.decode()
        LOGGER.debug(result[0])
        LOGGER.debug(result_stderr)
        LOGGER.debug(result_stdout)
        print(result[0])
        print(result_stderr)
        print(result_stdout)
        all_results.append(result)
    return all_results


def get_file_from_nodes(config,
                        vapp,
                        password,
                        file_name,
                        nodes,
                        check_tools=True):
    vs = VSphere(
        config['vcs']['host'],
        config['vcs']['username'],
        config['vcs']['password'],
        port=int(config['vcs']['port']))
    vs.connect()
    all_results = []
    for node in nodes:
        LOGGER.debug('getting file from node %s' % node.get('name'))
        moid = vapp.get_vm_moid(node.get('name'))
        vm = vs.get_vm_by_moid(moid)
        if check_tools:
            vs.wait_until_tools_ready(
                vm, sleep=5, callback=wait_for_tools_ready_callback)
            wait_until_ready_to_exec(vs, vm, password)
        result = vs.download_file_from_guest(vm, 'root', password, file_name)
        all_results.append(result)
    return all_results

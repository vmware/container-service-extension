# container-service-extension
# Copyright (c) 2017 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

import logging
import random
import re
import string
import time

from pyvcloud.vcd.client import QueryResultFormat
from pyvcloud.vcd.vapp import VApp
from pyvcloud.vcd.vm import VM

from container_service_extension.utils import get_vsphere

TYPE_MASTER = 'mstr'
TYPE_NODE = 'node'
TYPE_NFS = 'nfsd'

LOGGER = logging.getLogger('cse.cluster')


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


def load_from_metadata(client, name=None, cluster_id=None):
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
        cluster['nfs_nodes'] = []
        cluster['number_of_vms'] = node['record'].get('numberOfVMs')
        if 'template' in node:
            cluster['template'] = node['template']
        else:
            cluster['template'] = ''
        clusters_dict[cluster['name']] = cluster
    return list(clusters_dict.values())


def add_nodes(qty, template, node_type, config, client, org, vdc, vapp, body):
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
    cust_script_common = ''
    cust_script_end = \
"""
fi
"""  # NOQA
    if 'ssh_key' in body and body['ssh_key'] is not None:
        cust_script_common += \
"""
mkdir -p /root/.ssh
echo '{ssh_key}' >> /root/.ssh/authorized_keys
chmod -R go-rwx /root/.ssh
""".format(ssh_key=body['ssh_key'])  # NOQA

    if cust_script_common is '':
        cust_script = None
    else:
        cust_script = cust_script_init + cust_script_common + cust_script_end
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
            'ip_allocation_mode': 'pool'
        }
        if cust_script is not None:
            spec['cust_script'] = cust_script
        if storage_profile is not None:
            spec['storage_profile'] = storage_profile
        specs.append(spec)
    if ('cpu' in body and body['cpu'] is not None) or \
       ('memory' in body and body['memory'] is not None):
        reconfigure_hw = True
    else:
        reconfigure_hw = False
    task = vapp.add_vms(specs, power_on=not reconfigure_hw)
    # TODO(get details of the exception like not enough resources avail)
    client.get_task_monitor().wait_for_status(task)
    if reconfigure_hw:
        vapp.reload()
        for spec in specs:
            vm_resource = vapp.get_vm(spec['target_vm_name'])
            if 'cpu' in body and body['cpu'] is not None:
                vm = VM(client, resource=vm_resource)
                task = vm.modify_cpu(body['cpu'])
                client.get_task_monitor().wait_for_status(task)
            if 'memory' in body and body['memory'] is not None:
                vm = VM(client, resource=vm_resource)
                task = vm.modify_memory(body['memory'])
                client.get_task_monitor().wait_for_status(task)
            vm = VM(client, resource=vm_resource)
            task = vm.power_on()
            client.get_task_monitor().wait_for_status(task)
    password = source_vapp.get_admin_password(source_vm)
    vapp.reload()
    for spec in specs:
        vm_resource = vapp.get_vm(spec['target_vm_name'])
        command = '/bin/echo "root:{password}" | chpasswd'.format(
            password=template['admin_password'])
        nodes = [vm_resource]
        execute_script_in_nodes(
            config,
            vapp,
            password,
            command,
            nodes,
            check_tools=True,
            wait=False)
        if node_type == TYPE_NFS:
            LOGGER.debug('Enabling NFS server on %s' %
                         spec['target_vm_name'])
            from container_service_extension.config import get_data_file
            script = get_data_file('nfsd-%s.sh' % template['name'])
            execute_script_in_nodes(config, vapp,
                                    template['admin_password'],
                                    script, nodes)
    return {'task': task, 'specs': specs}


def get_nodes(vapp, node_type):
    nodes = []
    for node in vapp.get_all_vms():
        if node.get('name').startswith(node_type):
            nodes.append(node)
    return nodes


def wait_for_tools_ready_callback(message, exception=None):
    LOGGER.debug('waiting for guest tools, status: %s' % message)
    if exception is not None:
        LOGGER.error('exception: %s' % str(exception))


def wait_for_guest_execution_callback(message, exception=None):
    LOGGER.debug(message)
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
    LOGGER.debug('getting master IP for vapp: %s' % vapp.resource.get('name'))
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
    master_ip = result[0][1].content.decode().split()[0]
    LOGGER.debug('getting master IP for vapp: %s, ip: %s' %
                 (vapp.resource.get('name'), master_ip))
    return master_ip


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


def join_cluster(config, vapp, template, target_nodes=None):
    from container_service_extension.config import get_data_file
    init_info = get_init_info(config, vapp, template['admin_password'])
    tmp_script = get_data_file('node-%s.sh' % template['name'])
    script = tmp_script.format(token=init_info[0], ip=init_info[1])
    if target_nodes is None:
        nodes = get_nodes(vapp, TYPE_NODE)
    else:
        nodes = []
        for node in vapp.get_all_vms():
            if node.get('name') in target_nodes:
                nodes.append(node)
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
            LOGGER.info('VM is not ready to execute scripts, yet')
            time.sleep(2)
    if not ready:
        raise Exception('VM is not ready to execute scripts')


def execute_script_in_nodes(config,
                            vapp,
                            password,
                            script,
                            nodes,
                            check_tools=True,
                            wait=True):
    all_results = []
    for node in nodes:
        if 'chpasswd' in script:
            p = re.compile(':.*\"')
            debug_script = p.sub(':***\"', script)
        else:
            debug_script = script
        LOGGER.debug('will try to execute script on %s:\n%s' %
                     (node.get('name'), debug_script))
        vs = get_vsphere(config, vapp, node.get('name'))
        vs.connect()
        moid = vapp.get_vm_moid(node.get('name'))
        vm = vs.get_vm_by_moid(moid)
        if check_tools:
            LOGGER.debug('waiting for tools on %s' % node.get('name'))
            vs.wait_until_tools_ready(
                vm, sleep=5, callback=wait_for_tools_ready_callback)
            wait_until_ready_to_exec(vs, vm, password)
        LOGGER.debug('about to execute script on %s (vm=%s), wait=%s' %
                     (node.get('name'), vm, wait))
        if wait:
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
        else:
            result = [
                vs.execute_program_in_guest(
                    vm,
                    'root',
                    password,
                    script,
                    wait_for_completion=False,
                    get_output=False)
            ]
            result_stdout = ''
            result_stderr = ''
        LOGGER.debug(result[0])
        LOGGER.debug(result_stderr)
        LOGGER.debug(result_stdout)
        all_results.append(result)
    return all_results


def get_file_from_nodes(config,
                        vapp,
                        password,
                        file_name,
                        nodes,
                        check_tools=True):
    all_results = []
    for node in nodes:
        LOGGER.debug('getting file from node %s' % node.get('name'))
        vs = get_vsphere(config, vapp, node.get('name'))
        vs.connect()
        moid = vapp.get_vm_moid(node.get('name'))
        vm = vs.get_vm_by_moid(moid)
        if check_tools:
            vs.wait_until_tools_ready(
                vm, sleep=5, callback=wait_for_tools_ready_callback)
            wait_until_ready_to_exec(vs, vm, password)
        result = vs.download_file_from_guest(vm, 'root', password, file_name)
        all_results.append(result)
    return all_results


def delete_nodes_from_cluster(config, vapp, template, nodes, force=False):
    script = '#!/usr/bin/env bash\nkubectl delete node '
    for node in nodes:
        script += ' %s' % node
    script += '\n'
    password = template['admin_password']
    master_nodes = get_nodes(vapp, TYPE_MASTER)
    result = execute_script_in_nodes(
        config, vapp, password, script, master_nodes, check_tools=False)
    if result[0][0] != 0:
        if not force:
            raise Exception('Couldn\'t delete node(s):\n%s' %
                            result[0][2].content.decode())

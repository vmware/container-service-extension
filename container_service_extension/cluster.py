# container-service-extension
# Copyright (c) 2017 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

import random
import re
import string
import time

from pyvcloud.vcd.client import QueryResultFormat
from pyvcloud.vcd.vapp import VApp
from pyvcloud.vcd.vm import VM

from container_service_extension.exceptions import ClusterInitializationError
from container_service_extension.exceptions import ClusterJoiningError
from container_service_extension.exceptions import CseServerError
from container_service_extension.exceptions import DeleteNodeError
from container_service_extension.exceptions import NodeCreationError
from container_service_extension.exceptions import ScriptExecutionError
from container_service_extension.logger import SERVER_LOGGER as LOGGER
from container_service_extension.utils import get_data_file
from container_service_extension.utils import get_vsphere

TYPE_MASTER = 'mstr'
TYPE_NODE = 'node'
TYPE_NFS = 'nfsd'


def wait_until_tools_ready(vm):
    while True:
        try:
            status = vm.guest.toolsRunningStatus
            if 'guestToolsRunning' == status:
                LOGGER.debug(f"vm tools {vm} are ready")
                return
            LOGGER.debug(f"waiting for vm tools {vm} to be ready ({status})")
            time.sleep(1)
        except Exception:
            LOGGER.debug(f"waiting for vm tools {vm} to be ready ({status})* ")
            time.sleep(1)


def load_from_metadata(client, name=None, cluster_id=None):
    if cluster_id is None:
        query_filter = 'metadata:cse.cluster.id==STRING:*'
    else:
        query_filter = f'metadata:cse.cluster.id==STRING:{cluster_id}'
    if name is not None:
        query_filter += f';name=={name}'
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

    clusters = []
    for record in records:
        vapp_id = record.get('id').split(':')[-1]
        vdc_id = record.get('vdc').split(':')[-1]

        cluster = {
            'name': record.get('name'),
            'vapp_id': vapp_id,
            'vapp_href': f'{client._uri}/vApp/vapp-{vapp_id}',
            'vdc_name': record.get('vdcName'),
            'vdc_href': f'{client._uri}/vdc/{vdc_id}',
            'vdc_id': vdc_id,
            'leader_endpoint': '',
            'master_nodes': [],
            'nodes': [],
            'nfs_nodes': [],
            'number_of_vms': record.get('numberOfVMs'),
            'template': '',
            'cse_version': '',
            'cluster_id': '',
            'status': record.get('status')
        }
        if hasattr(record, 'Metadata'):
            for entry in record.Metadata.MetadataEntry:
                if entry.Key == 'cse.cluster.id':
                    cluster['cluster_id'] = str(entry.TypedValue.Value)
                elif entry.Key == 'cse.version':
                    cluster['cse_version'] = str(entry.TypedValue.Value)
                elif entry.Key == 'cse.master.ip':
                    cluster['leader_endpoint'] = str(entry.TypedValue.Value)
                elif entry.Key == 'cse.template':
                    cluster['template'] = str(entry.TypedValue.Value)

        clusters.append(cluster)

    return clusters


def add_nodes(qty, template, node_type, config, client, org, vdc, vapp, body):
    try:
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

        if cust_script_common == '':
            cust_script = None
        else:
            cust_script = cust_script_init + cust_script_common + \
                cust_script_end
        for n in range(qty):
            name = None
            while True:
                name = '%s-%s' % (
                    node_type,
                    ''.join(random.choices(
                        string.ascii_lowercase + string.digits, k=4)))
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
                LOGGER.debug(
                    f"enabling NFS server on {spec['target_vm_name']}")
                script = get_data_file('nfsd-%s.sh' % template['name'])
                exec_results = execute_script_in_nodes(
                    config, vapp,
                    template['admin_password'],
                    script, nodes)
                errors = get_script_execution_errors(exec_results)
                if errors:
                    raise ScriptExecutionError(
                        f"Script execution failed on node "
                        f"{spec['target_vm_name']}:{errors}")
    except Exception as e:
        node_list = [entry.get('target_vm_name') for entry in specs]
        raise NodeCreationError(node_list, str(e))
    return {'task': task, 'specs': specs}


def get_nodes(vapp, node_type):
    nodes = []
    for node in vapp.get_all_vms():
        if node.get('name').startswith(node_type):
            nodes.append(node)
    return nodes


def wait_for_tools_ready_callback(message, exception=None):
    LOGGER.debug(f"waiting for guest tools, status: {message}")
    if exception is not None:
        LOGGER.error(f"exception: {str(exception)}")


def wait_for_guest_execution_callback(message, exception=None):
    LOGGER.debug(message)
    if exception is not None:
        LOGGER.error(f"exception: {str(exception)}")


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
    LOGGER.debug(f"getting master IP for vapp: {vapp.resource.get('name')}")
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
    LOGGER.debug(f"getting master IP for vapp: {vapp.resource.get('name')}, "
                 f"ip: {master_ip}")
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
    script = get_data_file('mstr-%s.sh' % template['name'])
    nodes = get_nodes(vapp, TYPE_MASTER)
    result = execute_script_in_nodes(config, vapp, template['admin_password'],
                                     script, nodes)
    if result[0][0] != 0:
        raise ClusterInitializationError(
            f"Couldn\'t initialize cluster:\n{result[0][2].content.decode()}")


def join_cluster(config, vapp, template, target_nodes=None):
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
            raise ClusterJoiningError(
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
            raise Exception(f"script returned {result[0]}")
        except Exception:
            LOGGER.info("VM is not ready to execute scripts, yet")
            time.sleep(2)
    if not ready:
        raise CseServerError('VM is not ready to execute scripts')


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
        LOGGER.debug(f"will try to execute script on {node.get('name')}:\n"
                     f"{debug_script}")
        vs = get_vsphere(config, vapp, node.get('name'))
        vs.connect()
        moid = vapp.get_vm_moid(node.get('name'))
        vm = vs.get_vm_by_moid(moid)
        if check_tools:
            LOGGER.debug(f"waiting for tools on {node.get('name')}")
            vs.wait_until_tools_ready(
                vm, sleep=5, callback=wait_for_tools_ready_callback)
            wait_until_ready_to_exec(vs, vm, password)
        LOGGER.debug(f"about to execute script on {node.get('name')} (vm={vm})"
                     f", wait={wait}")
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
        LOGGER.debug(f"getting file from node {node.get('name')}")
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
            raise DeleteNodeError(
                f"Couldn't delete node(s):\n"
                f"{result[0][2].content.decode()}")


def get_script_execution_errors(results):
    errors = []
    for result in results:
        if result[0] != 0:
            errors.append(result[2].content.decode())
    return errors

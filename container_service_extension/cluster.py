# container-service-extension
# Copyright (c) 2017 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

import random
import string
import time

from pyvcloud.vcd.client import QueryResultFormat
from pyvcloud.vcd.org import Org
from pyvcloud.vcd.vapp import VApp
from pyvcloud.vcd.vm import VM
import requests

from container_service_extension.exceptions import ClusterInitializationError
from container_service_extension.exceptions import ClusterJoiningError
from container_service_extension.exceptions import ClusterOperationError
from container_service_extension.exceptions import CseServerError
from container_service_extension.exceptions import DeleteNodeError
from container_service_extension.exceptions import NodeCreationError
from container_service_extension.exceptions import ScriptExecutionError
from container_service_extension.logger import SERVER_LOGGER as LOGGER
from container_service_extension.pyvcloud_utils import get_sys_admin_client
from container_service_extension.remote_template_manager import \
    get_local_script_filepath
from container_service_extension.server_constants import ClusterMetadataKey
from container_service_extension.server_constants import LocalTemplateKey
from container_service_extension.server_constants import NodeType
from container_service_extension.server_constants import ScriptFile
from container_service_extension.server_constants import SYSTEM_ORG_NAME
from container_service_extension.utils import read_data_file
from container_service_extension.vsphere_utils import get_vsphere


def load_from_metadata(client, name=None, cluster_id=None,
                       org_name=None, vdc_name=None):

    if cluster_id is None:
        query_filter = 'metadata:cse.cluster.id==STRING:*'
    else:
        query_filter = f'metadata:cse.cluster.id==STRING:{cluster_id}'
    if name is not None:
        query_filter += f';name=={name}'

    if vdc_name is not None:
        query_filter += f";vdcName=={vdc_name}"

    resource_type = 'vApp'
    if client.is_sysadmin():
        resource_type = 'adminVApp'
        if org_name is not None and \
                org_name.lower() != SYSTEM_ORG_NAME.lower():
            org_resource = \
                client.get_org_by_name(org_name)
            org = Org(client, resource=org_resource)
            query_filter += f";org=={org.resource.get('id')}"

    q = client.get_typed_query(
        resource_type,
        query_result_format=QueryResultFormat.ID_RECORDS,
        qfilter=query_filter,
        fields='metadata:' + ClusterMetadataKey.CLUSTER_ID + ',metadata:' + # noqa: W504,E501
               ClusterMetadataKey.MASTER_IP + ',metadata:' + # noqa: W504
               ClusterMetadataKey.CSE_VERSION + ',metadata:' + # noqa: W504
               ClusterMetadataKey.TEMPLATE_NAME + ',metadata:' + # noqa: W504
               ClusterMetadataKey.TEMPLATE_REVISION + ',metadata:' + # noqa: W504,E501
               ClusterMetadataKey.BACKWARD_COMPATIBILE_TEMPLATE_NAME)
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
            'template_name': '',
            'template_revision': '',
            'cse_version': '',
            'cluster_id': '',
            'status': record.get('status')
        }
        if hasattr(record, 'Metadata'):
            for entry in record.Metadata.MetadataEntry:
                if entry.Key == ClusterMetadataKey.CLUSTER_ID:
                    cluster['cluster_id'] = str(entry.TypedValue.Value)
                elif entry.Key == ClusterMetadataKey.CSE_VERSION:
                    cluster['cse_version'] = str(entry.TypedValue.Value)
                elif entry.Key == ClusterMetadataKey.MASTER_IP:
                    cluster['leader_endpoint'] = str(entry.TypedValue.Value)
                elif entry.Key == ClusterMetadataKey.BACKWARD_COMPATIBILE_TEMPLATE_NAME: # noqa: E501
                    # Don't overwrite the value if already populated from the
                    # value corresponding to ClusterMetadataKey.TEMPLATE_NAME
                    if not cluster['template_name']:
                        cluster['template_name'] = str(entry.TypedValue.Value)
                elif entry.Key == ClusterMetadataKey.TEMPLATE_NAME:
                    cluster['template_name'] = str(entry.TypedValue.Value)
                elif entry.Key == ClusterMetadataKey.TEMPLATE_REVISION:
                    cluster['template_revision'] = str(entry.TypedValue.Value)

        clusters.append(cluster)

    return clusters


def add_nodes(client,
              num_nodes,
              node_type,
              org,
              vdc,
              vapp,
              catalog_name,
              template,
              network_name,
              num_cpu=None,
              memory_in_mb=None,
              storage_profile=None,
              ssh_key_filepath=None):
    specs = []
    try:
        if num_nodes < 1:
            return None
        catalog_item = org.get_catalog_item(
            catalog_name, template[LocalTemplateKey.CATALOG_ITEM_NAME])
        source_vapp = VApp(client, href=catalog_item.Entity.get('href'))
        source_vm = source_vapp.get_all_vms()[0].get('name')
        if storage_profile is not None:
            storage_profile = vdc.get_storage_profile(storage_profile)

        cust_script = None
        if ssh_key_filepath is not None:
            cust_script = \
                "#!/usr/bin/env bash\n" \
                "if [ x$1=x\"postcustomization\" ];\n" \
                "then\n" \
                "mkdir -p /root/.ssh\n" \
                f"echo '{ssh_key_filepath}' >> /root/.ssh/authorized_keys\n" \
                "chmod -R go-rwx /root/.ssh\n" \
                "fi"

        for n in range(num_nodes):
            name = None
            while True:
                name = f"{node_type}-{''.join(random.choices(string.ascii_lowercase + string.digits, k=4))}" # noqa: E501
                try:
                    vapp.get_vm(name)
                except Exception:
                    break
            spec = {
                'source_vm_name': source_vm,
                'vapp': source_vapp.resource,
                'target_vm_name': name,
                'hostname': name,
                'password': template[LocalTemplateKey.ADMIN_PASSWORD],
                'network': network_name,
                'ip_allocation_mode': 'pool'
            }
            if cust_script is not None:
                spec['cust_script'] = cust_script
            if storage_profile is not None:
                spec['storage_profile'] = storage_profile
            specs.append(spec)

        task = vapp.add_vms(specs, power_on=False)
        client.get_task_monitor().wait_for_status(task)
        vapp.reload()

        if not num_cpu:
            num_cpu = template[LocalTemplateKey.CPU]
        if not memory_in_mb:
            memory_in_mb = template[LocalTemplateKey.MEMORY]
        for spec in specs:
            vm_name = spec['target_vm_name']
            vm_resource = vapp.get_vm(vm_name)
            vm = VM(client, resource=vm_resource)

            task = vm.modify_cpu(num_cpu)
            client.get_task_monitor().wait_for_status(task)

            task = vm.modify_memory(memory_in_mb)
            client.get_task_monitor().wait_for_status(task)

            task = vm.power_on()
            client.get_task_monitor().wait_for_status(task)
            vapp.reload()

            if node_type == NodeType.NFS:
                LOGGER.debug(f"Enabling NFS server on {vm_name}")
                script_filepath = get_local_script_filepath(
                    template[LocalTemplateKey.NAME],
                    template[LocalTemplateKey.REVISION],
                    ScriptFile.NFSD)
                script = read_data_file(script_filepath, logger=LOGGER)
                exec_results = execute_script_in_nodes(
                    vapp=vapp, node_names=[vm_name], script=script)
                errors = _get_script_execution_errors(exec_results)
                if errors:
                    raise ScriptExecutionError(
                        f"Script execution failed on node {vm_name}:{errors}")
    except Exception as e:
        # TODO: get details of the exception to determine cause of failure,
        # e.g. not enough resources available.
        node_list = [entry.get('target_vm_name') for entry in specs]
        raise NodeCreationError(node_list, str(e))
    return {'task': task, 'specs': specs}


def _get_node_names(vapp, node_type):
    node_names = []
    for vm in vapp.get_all_vms():
        vm_name = vm.get('name')
        if vm_name.startswith(node_type):
            node_names.append(vm_name)
    return node_names


def _wait_for_tools_ready_callback(message, exception=None):
    LOGGER.debug(f"waiting for guest tools, status: {message}")
    if exception is not None:
        LOGGER.error(f"exception: {str(exception)}")


def _wait_for_guest_execution_callback(message, exception=None):
    LOGGER.debug(message)
    if exception is not None:
        LOGGER.error(f"exception: {str(exception)}")


def _get_init_info(vapp):
    script = \
        "#!/usr/bin/env bash\n" \
        "kubeadm token create\n" \
        "ip route get 1 | awk '{print $NF;exit}'\n"

    node_names = _get_node_names(vapp, NodeType.MASTER)
    result = execute_script_in_nodes(
        vapp=vapp, node_names=node_names, script=script)
    return result[0][1].content.decode().split()


def get_master_ip(vapp):
    LOGGER.debug(f"Getting master IP for vapp: "
                 f"{vapp.get_resource().get('name')}")
    script = \
        "#!/usr/bin/env bash\n" \
        "ip route get 1 | awk '{print $NF;exit}'\n" \

    node_names = _get_node_names(vapp, NodeType.MASTER)
    result = execute_script_in_nodes(
        vapp=vapp,
        node_names=node_names,
        script=script,
        check_tools=False)
    master_ip = result[0][1].content.decode().split()[0]
    LOGGER.debug(f"Retrieved master IP for vapp: "
                 f"{vapp.get_resource().get('name')}, ip: {master_ip}")
    return master_ip


def fetch_cluster_config(vapp):
    file_name = "/root/.kube/config"
    node_names = _get_node_names(vapp, NodeType.MASTER)
    result = _get_file_from_nodes(
        vapp, node_names, file_name, check_tools=False)
    if len(result) == 0 or result[0].status_code != requests.codes.ok:
        raise ClusterOperationError('Couldn\'t get cluster configuration')
    return result[0].content.decode()


def init_cluster(vapp, template):
    script_filepath = get_local_script_filepath(
        template[LocalTemplateKey.NAME], template[LocalTemplateKey.REVISION],
        ScriptFile.MASTER)
    script = read_data_file(script_filepath, logger=LOGGER)
    node_names = _get_node_names(vapp, NodeType.MASTER)
    result = execute_script_in_nodes(
        vapp=vapp,
        node_names=node_names,
        script=script)
    if result[0][0] != 0:
        raise ClusterInitializationError(
            f"Couldn\'t initialize cluster:\n{result[0][2].content.decode()}")


def join_cluster(vapp, template, target_nodes=None):
    init_info = _get_init_info(vapp)
    tmp_script_filepath = get_local_script_filepath(
        template[LocalTemplateKey.NAME], template[LocalTemplateKey.REVISION],
        ScriptFile.NODE)
    tmp_script = read_data_file(tmp_script_filepath, logger=LOGGER)
    script = tmp_script.format(token=init_info[0], ip=init_info[1])
    if target_nodes is None:
        node_names = _get_node_names(vapp, NodeType.WORKER)
    else:
        node_names = []
        for node in vapp.get_all_vms():
            vm_name = node.get('name')
            if vm_name in target_nodes:
                node_names.append(vm_name)
    results = execute_script_in_nodes(
        vapp=vapp, node_names=node_names, script=script)
    for result in results:
        if result[0] != 0:
            raise ClusterJoiningError(
                'Couldn\'t join cluster:\n%s' % result[2].content.decode())


def _wait_until_ready_to_exec(vs, vm, password, tries=30):
    ready = False
    script = \
        "#!/usr/bin/env bash\n" \
        "uname -a\n"

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
                callback=_wait_for_guest_execution_callback)
            if result[0] == 0:
                ready = True
                break
            raise Exception(f"script returned {result[0]}")
        except Exception:
            LOGGER.info("VM is not ready to execute scripts, yet")
            time.sleep(2)
    if not ready:
        raise CseServerError('VM is not ready to execute scripts')


def execute_script_in_nodes(vapp,
                            node_names,
                            script,
                            check_tools=True,
                            wait=True):
    all_results = []
    sys_admin_client = None
    try:
        sys_admin_client = get_sys_admin_client()
        for node_name in node_names:
            LOGGER.debug(f"will try to execute script on {node_name}:\n"
                         f"{script}")

            vs = get_vsphere(sys_admin_client, vapp, vm_name=node_name,
                             logger=LOGGER)
            vs.connect()
            moid = vapp.get_vm_moid(node_name)
            vm = vs.get_vm_by_moid(moid)
            password = vapp.get_admin_password(node_name)
            if check_tools:
                LOGGER.debug(f"waiting for tools on {node_name}")
                vs.wait_until_tools_ready(
                    vm, sleep=5, callback=_wait_for_tools_ready_callback)
                _wait_until_ready_to_exec(vs, vm, password)
            LOGGER.debug(f"about to execute script on {node_name} "
                         f"(vm={vm}), wait={wait}")
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
                    callback=_wait_for_guest_execution_callback)
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
    finally:
        if sys_admin_client:
            sys_admin_client.logout()

    return all_results


def _get_file_from_nodes(vapp, node_names, file_name, check_tools=True):
    all_results = []
    sys_admin_client = None
    try:
        sys_admin_client = get_sys_admin_client()
        for node_name in node_names:
            LOGGER.debug(f"getting file from node {node_name}")
            vs = get_vsphere(sys_admin_client, vapp, vm_name=node_name,
                             logger=LOGGER)
            vs.connect()
            moid = vapp.get_vm_moid(node_name)
            vm = vs.get_vm_by_moid(moid)
            password = vapp.get_admin_password(node_name)
            if check_tools:
                vs.wait_until_tools_ready(
                    vm, sleep=5, callback=_wait_for_tools_ready_callback)
                _wait_until_ready_to_exec(vs, vm, password)
            result = vs.download_file_from_guest(vm, 'root', password,
                                                 file_name)
            all_results.append(result)
    finally:
        if sys_admin_client:
            sys_admin_client.logout()
    return all_results


def delete_nodes_from_cluster(vapp, node_names, force=False):
    script = "#!/usr/bin/env bash\nkubectl delete node "
    for node_name in node_names:
        script += ' %s' % node_name
    script += '\n'
    master_node_names = _get_node_names(vapp, NodeType.MASTER)
    result = execute_script_in_nodes(
        vapp=vapp, node_names=master_node_names, script=script,
        check_tools=False)
    if result[0][0] != 0:
        if not force:
            raise DeleteNodeError(
                f"Couldn't delete node(s):\n"
                f"{result[0][2].content.decode()}")


def _get_script_execution_errors(results):
    errors = []
    for result in results:
        if result[0] != 0:
            errors.append(result[2].content.decode())
    return errors

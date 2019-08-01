# container-service-extension
# Copyright (c) 2017 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

import functools
import re
import threading
import traceback
import uuid

import pkg_resources
from pyvcloud.vcd.client import TaskStatus
from pyvcloud.vcd.client import VCLOUD_STATUS_MAP
from pyvcloud.vcd.org import Org
from pyvcloud.vcd.task import Task
from pyvcloud.vcd.vapp import VApp
from pyvcloud.vcd.vdc import VDC
from pyvcloud.vcd.vm import VM

from container_service_extension.abstract_broker import AbstractBroker
from container_service_extension.authorization import secure
from container_service_extension.cluster import add_nodes
from container_service_extension.cluster import delete_nodes_from_cluster
from container_service_extension.cluster import execute_script_in_nodes
from container_service_extension.cluster import fetch_cluster_config
from container_service_extension.cluster import get_master_ip
from container_service_extension.cluster import init_cluster
from container_service_extension.cluster import join_cluster
from container_service_extension.cluster import load_from_metadata
from container_service_extension.exception_handler import error_to_json
from container_service_extension.exceptions import ClusterAlreadyExistsError
from container_service_extension.exceptions import ClusterInitializationError
from container_service_extension.exceptions import ClusterJoiningError
from container_service_extension.exceptions import ClusterNotFoundError
from container_service_extension.exceptions import ClusterOperationError
from container_service_extension.exceptions import CseDuplicateClusterError
from container_service_extension.exceptions import CseServerError
from container_service_extension.exceptions import MasterNodeCreationError
from container_service_extension.exceptions import NFSNodeCreationError
from container_service_extension.exceptions import NodeCreationError
from container_service_extension.exceptions import NodeNotFoundError
from container_service_extension.exceptions import WorkerNodeCreationError
from container_service_extension.logger import SERVER_LOGGER as LOGGER
import container_service_extension.pyvcloud_utils as vcd_utils
from container_service_extension.server_constants import ClusterMetadataKey
from container_service_extension.server_constants import \
    CSE_NATIVE_DEPLOY_RIGHT_NAME
from container_service_extension.server_constants import K8S_PROVIDER_KEY
from container_service_extension.server_constants import K8sProvider
from container_service_extension.server_constants import NodeType
from container_service_extension.shared_constants import ERROR_DESCRIPTION_KEY
from container_service_extension.shared_constants import ERROR_MESSAGE_KEY
from container_service_extension.shared_constants import ERROR_STACKTRACE_KEY
from container_service_extension.shared_constants import RequestKey
import container_service_extension.utils as utils


OP_CREATE_CLUSTER = 'create_cluster'
OP_DELETE_CLUSTER = 'delete_cluster'
OP_CREATE_NODES = 'create_nodes'
OP_DELETE_NODES = 'delete_nodes'

OP_MESSAGE = {
    OP_CREATE_CLUSTER: 'create cluster',
    OP_DELETE_CLUSTER: 'delete cluster',
    OP_CREATE_NODES: 'create nodes in cluster',
    OP_DELETE_NODES: 'delete nodes from cluster',
}

MAX_HOST_NAME_LENGTH = 25


def rollback_on_failure(func):
    """Decorate to rollback on cluster and node creation failures.

    :param func: reference to the original function that is decorated

    :return: reference to the decorator wrapper
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except (MasterNodeCreationError, WorkerNodeCreationError,
                NFSNodeCreationError, ClusterJoiningError,
                ClusterInitializationError):
            try:
                # arg[0] refers to the current instance of the broker thread
                broker_instance = args[0]  # param self
                if broker_instance.req_spec.get(RequestKey.ROLLBACK):
                    broker_instance.cluster_rollback()
            except Exception as err:
                LOGGER.error(f"Failed to rollback cluster creation:{str(err)}")
        except NodeCreationError as e:
            try:
                broker_instance = args[0]
                node_list = e.node_names
                if broker_instance.req_spec.get(RequestKey.ROLLBACK):
                    broker_instance.node_rollback(node_list)
            except Exception as err:
                LOGGER.error(f"Failed to rollback node creation:{str(err)}")
    return wrapper


class VcdBroker(AbstractBroker, threading.Thread):
    def __init__(self, tenant_auth_token, request_spec):
        super().__init__(tenant_auth_token, request_spec)
        threading.Thread.__init__(self)
        self.req_spec = request_spec

        self.tenant_client = None
        self.client_session = None
        self.tenant_info = None

        self.sys_admin_client = None

        self.task = None
        self.task_resource = None
        self.op = None
        self.cluster_name = None
        self.cluster_id = None
        self.daemon = False

    def _connect_sys_admin(self):
        self.sys_admin_client = vcd_utils.get_sys_admin_client()

    def _disconnect_sys_admin(self):
        if self.sys_admin_client is not None:
            self.sys_admin_client.logout()
            self.sys_admin_client = None

    def _update_task(self,
                     status,
                     message=None,
                     error_message=None,
                     stack_trace=''):
        if not self.tenant_client.is_sysadmin():
            stack_trace = ''

        if self.task is None:
            self.task = Task(self.sys_admin_client)

        if message is None:
            message = OP_MESSAGE[self.op]

        if self.task_resource is not None:
            task_href = self.task_resource.get('href')
        else:
            task_href = None

        org_resource = self.tenant_client.get_org_by_name(
            self.req_spec.get(RequestKey.ORG_NAME))
        org = Org(self.tenant_client, resource=org_resource)
        user_href = org.get_user(self.client_session.get('user')).get('href')

        self.task_resource = self.task.update(
            status=status.value,
            namespace='vcloud.cse',
            operation=message,
            operation_name=self.op,
            details='',
            progress=None,
            owner_href=self.tenant_info['org_href'],
            owner_name=self.tenant_info['org_name'],
            owner_type='application/vnd.vmware.vcloud.org+xml',
            user_href=user_href,
            user_name=self.tenant_info['user_name'],
            org_href=self.tenant_info['org_href'],
            task_href=task_href,
            error_message=error_message,
            stack_trace=stack_trace
        )

    def _is_valid_name(self, name):
        """Validate that the cluster name against the pattern."""
        if len(name) > MAX_HOST_NAME_LENGTH:
            return False
        if name[-1] == '.':
            name = name[:-1]
        allowed = re.compile(r"(?!-)[A-Z\d-]{1,63}(?<!-)$", re.IGNORECASE)
        return all(allowed.match(x) for x in name.split("."))

    def _get_template(self, name=None, revision=None):
        server_config = utils.get_server_runtime_config()
        name = name or \
            self.req_spec.get(RequestKey.TEMPLATE_NAME) or \
            server_config['broker']['default_template_name']
        revision = revision or \
            self.req_spec.get(RequestKey.TEMPLATE_REVISION) or \
            server_config['broker']['default_template_revision']
        for template in server_config['broker']['templates']:
            if (template['name'] == name) and \
                    (str(template['revision']) == str(revision)):
                return template
        raise Exception(f"Template '{name}' at revision {revision} not found.")

    def _get_nfs_exports(self, ip, vapp, node):
        """Get the exports from remote NFS server (helper method).

        :param ip: (str): IP address of the NFS server
        :param vapp: (pyvcloud.vcd.vapp.VApp): The vApp or cluster
         to which node belongs
        :param node: (str): IP address of the NFS server
        :param node: (`lxml.objectify.StringElement`) object
        representing the vm resource.

        :return: (List): List of exports
        """
        # TODO: Find the right way to retrieve the template from which nfs node
        # was created.
        server_config = utils.get_server_runtime_config()
        template = server_config['broker']['templates'][0]
        script = f"#!/usr/bin/env bash\nshowmount -e {ip}"
        result = execute_script_in_nodes(vapp,
                                         template['admin_password'],
                                         script,
                                         nodes=[node],
                                         check_tools=False)
        lines = result[0][1].content.decode().split('\n')
        exports = []
        for index in range(1, len(lines) - 1):
            export = lines[index].strip().split()[0]
            exports.append(export)
        return exports

    def node_rollback(self, node_list):
        """Rollback for node creation failure.

        :param list node_list: faulty nodes to be deleted
        """
        LOGGER.info(f"About to rollback nodes from cluster with name: "
                    "{self.cluster_name}")
        LOGGER.info(f"Node list to be deleted:{node_list}")
        vapp = VApp(self.tenant_client, href=self.cluster['vapp_href'])
        template = self._get_template()
        try:
            delete_nodes_from_cluster(vapp, template, node_list, force=True)
        except Exception:
            LOGGER.warning("Couldn't delete node {node_list} from cluster:"
                           "{self.cluster_name}")
        for vm_name in node_list:
            vm = VM(self.tenant_client, resource=vapp.get_vm(vm_name))
            try:
                vm.undeploy()
            except Exception:
                LOGGER.warning(f"Couldn't undeploy VM {vm_name}")
        vapp.delete_vms(node_list)
        LOGGER.info(f"Successfully deleted nodes: {node_list}")

    def cluster_rollback(self):
        """Rollback for cluster creation failure."""
        LOGGER.info(f"About to rollback cluster with name: "
                    "{self.cluster_name}")
        self._connect_tenant()
        clusters = load_from_metadata(
            self.tenant_client, name=self.cluster_name)
        if len(clusters) != 1:
            LOGGER.debug(f"Cluster {self.cluster_name} not found.")
            return
        self.cluster = clusters[0]
        vdc = VDC(self.tenant_client, href=self.cluster['vdc_href'])
        vdc.delete_vapp(self.cluster['name'], force=True)
        LOGGER.info(f"Successfully deleted cluster: {self.cluster_name}")

    def run(self):
        LOGGER.debug(f"Thread started for operation={self.op}")
        if self.op == OP_CREATE_CLUSTER:
            self.create_cluster_thread()
        elif self.op == OP_DELETE_CLUSTER:
            self.delete_cluster_thread()
        elif self.op == OP_CREATE_NODES:
            self.create_nodes_thread()
        elif self.op == OP_DELETE_NODES:
            self.delete_nodes_thread()

    def list_clusters(self):
        self._connect_tenant()
        clusters = []
        raw_clusters = load_from_metadata(
            self.tenant_client,
            org_name=self.req_spec.get(RequestKey.ORG_NAME),
            vdc_name=self.req_spec.get(RequestKey.OVDC_NAME))
        for c in raw_clusters:
            clusters.append({
                'name': c['name'],
                'IP master': c['leader_endpoint'],
                'template_name': c.get('template_name'),
                'template_revision': c.get('template_revision'),
                'VMs': c['number_of_vms'],
                'vdc': c['vdc_name'],
                'status': c['status'],
                'vdc_id': c['vdc_id'],
                'org_name': vcd_utils.get_org_name_from_ovdc_id(c['vdc_id']),
                K8S_PROVIDER_KEY: K8sProvider.NATIVE
            })
        return clusters

    def get_cluster_info(self, **kwargs):
        """Get the info of the cluster.

        :param cluster_name: (str): Name of the cluster

        :return: (dict): Info of the cluster.
        """
        cluster_name = self.req_spec[RequestKey.CLUSTER_NAME]

        self._connect_tenant()
        clusters = load_from_metadata(
            self.tenant_client,
            name=cluster_name,
            org_name=self.req_spec.get(RequestKey.ORG_NAME),
            vdc_name=self.req_spec.get(RequestKey.OVDC_NAME))
        if len(clusters) > 1:
            raise CseDuplicateClusterError(f"Multiple clusters of name"
                                           f" '{cluster_name}' detected.")
        if len(clusters) == 0:
            raise ClusterNotFoundError(f"Cluster '{cluster_name}' not found.")

        cluster = clusters[0]
        cluster[K8S_PROVIDER_KEY] = K8sProvider.NATIVE
        vapp = VApp(self.tenant_client, href=clusters[0]['vapp_href'])
        vms = vapp.get_all_vms()
        for vm in vms:
            node_info = {
                'name': vm.get('name'),
                'ipAddress': ''
            }
            try:
                node_info['ipAddress'] = vapp.get_primary_ip(vm.get('name'))
            except Exception:
                LOGGER.debug(f"Unable to get ip address of node "
                             f"{vm.get('name')}")
            if vm.get('name').startswith(NodeType.MASTER):
                cluster.get('master_nodes').append(node_info)
            elif vm.get('name').startswith(NodeType.WORKER):
                cluster.get('nodes').append(node_info)
            elif vm.get('name').startswith(NodeType.NFS):
                cluster.get('nfs_nodes').append(node_info)
        return cluster

    def get_node_info(self, cluster_name, node_name):
        """Get the info of a given node in the cluster.

        :param cluster_name: (str): Name of the cluster
        :param node_name: (str): Name of the node

        :return: (dict): Info of the node.
        """
        self._connect_tenant()
        clusters = load_from_metadata(
            self.tenant_client,
            name=cluster_name,
            org_name=self.req_spec.get(RequestKey.ORG_NAME),
            vdc_name=self.req_spec.get(RequestKey.OVDC_NAME))
        if len(clusters) > 1:
            raise CseDuplicateClusterError(f"Multiple clusters of name"
                                           f" '{cluster_name}' detected.")
        if len(clusters) == 0:
            raise ClusterNotFoundError(f"Cluster '{cluster_name}' not found.")

        vapp = VApp(self.tenant_client, href=clusters[0]['vapp_href'])
        vms = vapp.get_all_vms()
        node_info = None
        for vm in vms:
            if (node_name == vm.get('name')):
                node_info = {
                    'name': vm.get('name'),
                    'numberOfCpus': '',
                    'memoryMB': '',
                    'status': VCLOUD_STATUS_MAP.get(int(vm.get('status'))),
                    'ipAddress': ''
                }
                if hasattr(vm, 'VmSpecSection'):
                    node_info[
                        'numberOfCpus'] = vm.VmSpecSection.NumCpus.text
                    node_info[
                        'memoryMB'] = \
                        vm.VmSpecSection.MemoryResourceMb.Configured.text
                try:
                    node_info['ipAddress'] = vapp.get_primary_ip(
                        vm.get('name'))
                except Exception:
                    LOGGER.debug(f"Unable to get ip address of node "
                                 f"{vm.get('name')}")
                if vm.get('name').startswith(NodeType.MASTER):
                    node_info['node_type'] = 'master'
                elif vm.get('name').startswith(NodeType.WORKER):
                    node_info['node_type'] = 'worker'
                elif vm.get('name').startswith(NodeType.NFS):
                    node_info['node_type'] = 'nfs'
                    exports = self._get_nfs_exports(node_info['ipAddress'],
                                                    vapp,
                                                    vm)
                    node_info['exports'] = exports
        if node_info is None:
            raise NodeNotFoundError(f"Node '{node_name}' not found in "
                                    f"cluster '{cluster_name}'")
        return node_info

    def get_cluster_config(self):
        self._connect_tenant()
        cluster_name = self.req_spec[RequestKey.CLUSTER_NAME]

        clusters = load_from_metadata(
            self.tenant_client,
            name=cluster_name,
            org_name=self.req_spec.get(RequestKey.ORG_NAME),
            vdc_name=self.req_spec.get(RequestKey.OVDC_NAME))
        if len(clusters) > 1:
            raise CseDuplicateClusterError(f"Multiple clusters of name"
                                           f" '{cluster_name}' detected.")
        if len(clusters) == 0:
            raise ClusterNotFoundError(f"Cluster '{cluster_name}' not found.")

        vapp = VApp(self.tenant_client, href=clusters[0]['vapp_href'])
        template = self._get_template(
            name=clusters[0]['template_name'],
            revision=clusters[0]['template_revision'])
        return fetch_cluster_config(vapp, template['admin_password'])

    @secure(required_rights=[CSE_NATIVE_DEPLOY_RIGHT_NAME])
    def create_cluster(self):
        required = [
            RequestKey.NETWORK_NAME
        ]
        utils.ensure_keys_in_dict(required, self.req_spec, dict_name='request')

        # check that requested template is valid, else fall back to default
        # template.
        self._get_template(
            name=self.req_spec.get(RequestKey.TEMPLATE_NAME),
            revision=self.req_spec.get(RequestKey.TEMPLATE_REVISION))

        self.cluster_name = self.req_spec[RequestKey.CLUSTER_NAME]
        if not self._is_valid_name(self.cluster_name):
            raise CseServerError("Invalid cluster name "
                                 f"'{self.cluster_name}'")

        self._connect_tenant()
        clusters = load_from_metadata(self.tenant_client,
                                      name=self.cluster_name)
        if len(clusters) != 0:
            raise ClusterAlreadyExistsError(f"Cluster {self.cluster_name} "
                                            "already exists.")

        LOGGER.debug(f"About to create cluster {self.cluster_name} on "
                     f"{self.req_spec[RequestKey.OVDC_NAME]} with "
                     f"{self.req_spec[RequestKey.NUM_WORKERS]} worker nodes, "
                     f"storage profile="
                     f"{self.req_spec[RequestKey.STORAGE_PROFILE_NAME]}")

        self._connect_sys_admin()
        self.cluster_id = str(uuid.uuid4())
        self.op = OP_CREATE_CLUSTER
        self._update_task(
            TaskStatus.RUNNING,
            message=f"Creating cluster {self.cluster_name}({self.cluster_id})")
        self.daemon = True
        self.start()
        result = {}
        result['name'] = self.cluster_name
        result['cluster_id'] = self.cluster_id
        result['task_href'] = self.task_resource.get('href')
        return result

    @rollback_on_failure
    def create_cluster_thread(self):
        try:
            org_resource = self.tenant_client.get_org_by_name(
                self.req_spec.get(RequestKey.ORG_NAME))
            org = Org(self.tenant_client, resource=org_resource)
            vdc_resource = org.get_vdc(self.req_spec.get(RequestKey.OVDC_NAME))
            vdc = VDC(self.tenant_client, resource=vdc_resource)
            network_name = self.req_spec.get(RequestKey.NETWORK_NAME)
            self._update_task(
                TaskStatus.RUNNING,
                message=f"Creating cluster vApp {self.cluster_name}"
                        f"({self.cluster_id})")
            try:
                vapp_resource = vdc.create_vapp(
                    self.cluster_name,
                    description=f"cluster {self.cluster_name}",
                    network=network_name,
                    fence_mode='bridged')
            except Exception as e:
                raise ClusterOperationError(
                    "Error while creating vApp:", str(e))

            self.tenant_client.get_task_monitor().wait_for_status(
                vapp_resource.Tasks.Task[0])

            template = self._get_template()

            tags = {}
            tags[ClusterMetadataKey.CLUSTER_ID] = self.cluster_id
            tags[ClusterMetadataKey.CSE_VERSION] = pkg_resources.require(
                'container-service-extension')[0].version
            tags[ClusterMetadataKey.TEMPLATE_NAME] = template['name']
            tags[ClusterMetadataKey.TEMPLATE_REVISION] = template['revision']
            vapp = VApp(self.tenant_client, href=vapp_resource.get('href'))
            task = vapp.set_multiple_metadata(tags)
            self.tenant_client.get_task_monitor().wait_for_status(task)

            self._update_task(
                TaskStatus.RUNNING,
                message=f"Creating master node for {self.cluster_name}"
                        f"({self.cluster_id})")
            vapp.reload()

            server_config = utils.get_server_runtime_config()
            catalog_name = server_config['broker']['catalog']
            try:
                add_nodes(
                    client=self.tenant_client,
                    num_nodes=1,
                    node_type=NodeType.MASTER,
                    org=org,
                    vdc=vdc,
                    vapp=vapp,
                    catalog_name=catalog_name,
                    template=template,
                    network_name=self.req_spec.get(RequestKey.NETWORK_NAME),
                    num_cpu=self.req_spec.get(RequestKey.NUM_CPU),
                    memory_in_mb=self.req_spec.get(RequestKey.MB_MEMORY),
                    storage_profile=self.req_spec.get(RequestKey.STORAGE_PROFILE_NAME), # noqa: E501
                    ssh_key_filepath=self.req_spec.get(RequestKey.SSH_KEY_FILEPATH)) # noqa: E501
            except Exception as e:
                raise MasterNodeCreationError(
                    "Error while adding master node:", str(e))

            self._update_task(
                TaskStatus.RUNNING,
                message=f"Initializing cluster {self.cluster_name}"
                        f"({self.cluster_id})")
            vapp.reload()
            init_cluster(vapp, template)
            master_ip = get_master_ip(vapp, template)
            task = vapp.set_metadata('GENERAL', 'READWRITE', 'cse.master.ip',
                                     master_ip)
            self.tenant_client.get_task_monitor().wait_for_status(task)
            if self.req_spec.get(RequestKey.NUM_WORKERS) > 0:
                self._update_task(
                    TaskStatus.RUNNING,
                    message=f"Creating "
                            f"{self.req_spec.get(RequestKey.NUM_WORKERS)} "
                            f"node(s) for "
                            f"{self.cluster_name}({self.cluster_id})")
                try:
                    add_nodes(
                        client=self.tenant_client,
                        num_nodes=self.req_spec.get(RequestKey.NUM_WORKERS),
                        node_type=NodeType.WORKER,
                        org=org,
                        vdc=vdc,
                        vapp=vapp,
                        catalog_name=catalog_name,
                        template=template,
                        network_name=self.req_spec.get(RequestKey.NETWORK_NAME), # noqa: E501
                        num_cpu=self.req_spec.get(RequestKey.NUM_CPU),
                        memory_in_mb=self.req_spec.get(RequestKey.MB_MEMORY),
                        storage_profile=self.req_spec.get(RequestKey.STORAGE_PROFILE_NAME), # noqa: E501
                        ssh_key_filepath=self.req_spec.get(RequestKey.SSH_KEY_FILEPATH)) # noqa: E501
                except Exception as e:
                    raise WorkerNodeCreationError(
                        "Error while creating worker node:", str(e))

                self._update_task(
                    TaskStatus.RUNNING,
                    message=f"Adding "
                            f"{self.req_spec.get(RequestKey.NUM_WORKERS)} "
                            f"node(s) to "
                            f"{self.cluster_name}({self.cluster_id})")
                vapp.reload()
                join_cluster(vapp, template)
            if self.req_spec.get(RequestKey.ENABLE_NFS):
                self._update_task(
                    TaskStatus.RUNNING,
                    message=f"Creating NFS node for {self.cluster_name}"
                            f"({self.cluster_id})")
                try:
                    add_nodes(
                        client=self.tenant_client,
                        num_nodes=1,
                        node_type=NodeType.NFS,
                        org=org,
                        vdc=vdc,
                        vapp=vapp,
                        catalog_name=catalog_name,
                        template=template,
                        network_name=self.req_spec.get(RequestKey.NETWORK_NAME), # noqa: E501
                        num_cpu=self.req_spec.get(RequestKey.NUM_CPU),
                        memory_in_mb=self.req_spec.get(RequestKey.MB_MEMORY),
                        storage_profile=self.req_spec.get(RequestKey.STORAGE_PROFILE_NAME), # noqa: E501
                        ssh_key_filepath=self.req_spec.get(RequestKey.SSH_KEY_FILEPATH)) # noqa: E501
                except Exception as e:
                    raise NFSNodeCreationError(
                        "Error while creating NFS node:", str(e))

            self._update_task(
                TaskStatus.SUCCESS,
                message=f"Created cluster {self.cluster_name}"
                        f"({self.cluster_id})")
        except (MasterNodeCreationError, WorkerNodeCreationError,
                NFSNodeCreationError, ClusterJoiningError,
                ClusterInitializationError, ClusterOperationError) as e:
            LOGGER.error(traceback.format_exc())
            error_obj = error_to_json(e)
            stack_trace = \
                ''.join(error_obj[ERROR_MESSAGE_KEY][ERROR_STACKTRACE_KEY])
            self._update_task(
                TaskStatus.ERROR,
                error_message=error_obj[ERROR_MESSAGE_KEY]
                [ERROR_DESCRIPTION_KEY],
                stack_trace=stack_trace)
            raise e
        except Exception as e:
            LOGGER.error(traceback.format_exc())
            error_obj = error_to_json(e)
            stack_trace = \
                ''.join(error_obj[ERROR_MESSAGE_KEY][ERROR_STACKTRACE_KEY])
            self._update_task(
                TaskStatus.ERROR,
                error_message=error_obj[ERROR_MESSAGE_KEY][ERROR_DESCRIPTION_KEY], # noqa: E501
                stack_trace=stack_trace)
        finally:
            self._disconnect_sys_admin()

    @secure(required_rights=[CSE_NATIVE_DEPLOY_RIGHT_NAME])
    def delete_cluster(self):
        cluster_name = self.req_spec[RequestKey.CLUSTER_NAME]
        LOGGER.debug(f"About to delete cluster with name: {cluster_name}")

        self.cluster_name = cluster_name
        self._connect_tenant()
        self._connect_sys_admin()
        self.op = OP_DELETE_CLUSTER
        clusters = load_from_metadata(
            self.tenant_client, name=self.cluster_name,
            org_name=self.req_spec.get(RequestKey.ORG_NAME),
            vdc_name=self.req_spec.get(RequestKey.OVDC_NAME))
        if len(clusters) > 1:
            raise CseDuplicateClusterError(
                f"Multiple clusters of name '{self.cluster_name}' detected.")
        if len(clusters) != 1:
            raise ClusterNotFoundError(
                f"Cluster {self.cluster_name} not found.")
        self.cluster = clusters[0]
        self.cluster_id = self.cluster['cluster_id']
        self._update_task(
            TaskStatus.RUNNING,
            message=f"Deleting cluster {self.cluster_name}"
                    f"({self.cluster_id})")
        self.daemon = True
        self.start()
        result = {}
        result['cluster_name'] = self.cluster_name
        result['task_href'] = self.task_resource.get('href')
        return result

    def delete_cluster_thread(self):
        LOGGER.debug(f"About to delete cluster with name: {self.cluster_name}")
        try:
            vdc = VDC(self.tenant_client, href=self.cluster['vdc_href'])
            task = vdc.delete_vapp(self.cluster['name'], force=True)
            self.tenant_client.get_task_monitor().wait_for_status(task)
            self._update_task(
                TaskStatus.SUCCESS,
                message=f"Deleted cluster {self.cluster_name}"
                        f"({self.cluster_id})")
        except Exception as e:
            LOGGER.error(traceback.format_exc())
            self._update_task(TaskStatus.ERROR, error_message=str(e))
        finally:
            self._disconnect_sys_admin()

    @secure(required_rights=[CSE_NATIVE_DEPLOY_RIGHT_NAME])
    def create_nodes(self):
        self.cluster_name = self.req_spec.get(RequestKey.CLUSTER_NAME)
        LOGGER.debug(f"About to add "
                     f"{self.req_spec.get(RequestKey.NUM_WORKERS)} nodes to "
                     f"cluster {self.cluster_name} on VDC "
                     f"{self.req_spec.get(RequestKey.OVDC_NAME)}")
        if self.req_spec.get(RequestKey.NUM_WORKERS) < 1:
            raise CseServerError(f"Invalid node count: {self.req_spec.get(RequestKey.NUM_WORKERS)}.") # noqa: E501
        if self.req_spec.get(RequestKey.NETWORK_NAME) is None:
            raise CseServerError(f'Network name is missing from the request.')

        self._connect_tenant()
        self._connect_sys_admin()
        clusters = load_from_metadata(
            self.tenant_client, name=self.cluster_name,
            org_name=self.req_spec.get(RequestKey.ORG_NAME),
            vdc_name=self.req_spec.get(RequestKey.OVDC_NAME))

        if len(clusters) > 1:
            raise CseDuplicateClusterError(f"Multiple clusters of name "
                                           f"'{self.cluster_name}' detected.")
        if len(clusters) == 0:
            raise ClusterNotFoundError(
                f"Cluster '{self.cluster_name}' not found.")

        self.cluster = clusters[0]
        self.op = OP_CREATE_NODES
        self.cluster_id = self.cluster['cluster_id']
        self._update_task(
            TaskStatus.RUNNING,
            message=f"Adding {self.req_spec.get(RequestKey.NUM_WORKERS)} "
                    f"node(s) to cluster "
                    f"{self.cluster_name}({self.cluster_id})")
        self.daemon = True
        self.start()
        result = {}
        result['cluster_name'] = self.cluster_name
        result['task_href'] = self.task_resource.get('href')
        return result

    @rollback_on_failure
    def create_nodes_thread(self):
        LOGGER.debug(f"About to add nodes to cluster with name: "
                     f"{self.cluster_name}")
        try:
            org_resource = self.tenant_client.get_org()
            org = Org(self.tenant_client, resource=org_resource)
            vdc = VDC(self.tenant_client, href=self.cluster['vdc_href'])
            vapp = VApp(self.tenant_client, href=self.cluster['vapp_href'])
            template = self._get_template()
            self._update_task(
                TaskStatus.RUNNING,
                message=f"Creating {self.req_spec.get(RequestKey.NUM_WORKERS)}"
                        f" node(s) for {self.cluster_name}({self.cluster_id})")

            node_type = NodeType.WORKER
            if self.req_spec.get(RequestKey.ENABLE_NFS):
                node_type = NodeType.NFS

            server_config = utils.get_server_runtime_config()
            catalog_name = server_config['broker']['catalog']

            new_nodes = \
                add_nodes(
                    client=self.tenant_client,
                    num_nodes=self.req_spec.get(RequestKey.NUM_WORKERS),
                    node_type=node_type,
                    org=org,
                    vdc=vdc,
                    vapp=vapp,
                    catalog_name=catalog_name,
                    template=template,
                    network_name=self.req_spec.get(RequestKey.NETWORK_NAME),
                    num_cpu=self.req_spec.get(RequestKey.NUM_CPU),
                    memory_in_mb=self.req_spec.get(RequestKey.MB_MEMORY),
                    storage_profile=self.req_spec.get(RequestKey.STORAGE_PROFILE_NAME), # noqa: E501
                    ssh_key_filepath=self.req_spec.get(RequestKey.SSH_KEY_FILEPATH)) # noqa: E501

            if node_type == NodeType.NFS:
                self._update_task(
                    TaskStatus.SUCCESS,
                    message=f"Created "
                            f"{self.req_spec.get(RequestKey.NUM_WORKERS)} "
                            f"node(s) for "
                            f"{self.cluster_name}({self.cluster_id})")
            elif node_type == NodeType.WORKER:
                self._update_task(
                    TaskStatus.RUNNING,
                    message=f"Adding "
                            f"{self.req_spec.get(RequestKey.NUM_WORKERS)} "
                            f"node(s) to cluster "
                            f"{self.cluster_name}({self.cluster_id})")
                target_nodes = []
                for spec in new_nodes['specs']:
                    target_nodes.append(spec['target_vm_name'])
                vapp.reload()
                join_cluster(vapp, template, target_nodes)
                self._update_task(
                    TaskStatus.SUCCESS,
                    message=f"Added "
                            f"{self.req_spec.get(RequestKey.NUM_WORKERS)} "
                            f"node(s) to cluster "
                            f"{self.cluster_name}({self.cluster_id})")
        except NodeCreationError as e:
            error_obj = error_to_json(e)
            LOGGER.error(traceback.format_exc())
            stack_trace = \
                ''.join(error_obj[ERROR_MESSAGE_KEY][ERROR_STACKTRACE_KEY])
            self._update_task(
                TaskStatus.ERROR,
                error_message=error_obj[ERROR_MESSAGE_KEY][ERROR_DESCRIPTION_KEY], # noqa: E501
                stack_trace=stack_trace)
            raise
        except Exception as e:
            error_obj = error_to_json(e)
            LOGGER.error(traceback.format_exc())
            stack_trace = \
                ''.join(error_obj[ERROR_MESSAGE_KEY][ERROR_STACKTRACE_KEY])
            self._update_task(
                TaskStatus.ERROR,
                error_message=error_obj[ERROR_MESSAGE_KEY][ERROR_DESCRIPTION_KEY], # noqa: E501
                stack_trace=stack_trace)
        finally:
            self._disconnect_sys_admin()

    @secure(required_rights=[CSE_NATIVE_DEPLOY_RIGHT_NAME])
    def delete_nodes(self):
        result = {'body': {}}
        self.cluster_name = self.req_spec.get(RequestKey.CLUSTER_NAME)
        LOGGER.debug(f"About to delete nodes from cluster with name: "
                     f"{self.req_spec.get(RequestKey.CLUSTER_NAME)}")

        if len(self.req_spec.get(RequestKey.NODE_NAMES_LIST)) < 1:
            raise CseServerError(f"Invalid list of nodes: {self.req_spec.get(RequestKey.NODE_NAMES_LIST)}.") # noqa: E501
        for node in self.req_spec.get(RequestKey.NODE_NAMES_LIST):
            if node.startswith(NodeType.MASTER):
                raise CseServerError(f"Can't delete a master node: '{node}'.")
        self._connect_tenant()
        self._connect_sys_admin()
        clusters = load_from_metadata(
            self.tenant_client, name=self.cluster_name,
            org_name=self.req_spec.get(RequestKey.ORG_NAME),
            vdc_name=self.req_spec.get(RequestKey.OVDC_NAME))
        if len(clusters) <= 0:
            raise CseServerError(f"Cluster '{self.cluster_name}' not found.")

        if len(clusters) > 1:
            raise CseDuplicateClusterError(f"Multiple clusters of name "
                                           f"'{self.cluster_name}' detected.")
        self.cluster = clusters[0]
        self.op = OP_DELETE_NODES
        self.cluster_id = self.cluster['cluster_id']
        self._update_task(
            TaskStatus.RUNNING,
            message=f"Deleting "
                    f"{len(self.req_spec.get(RequestKey.NODE_NAMES_LIST))} "
                    f"node(s) from cluster "
                    f"{self.cluster_name}({self.cluster_id})")
        self.daemon = True
        self.start()
        result = {
            'cluster_name': self.cluster_name,
            'task_href': self.task_resource.get('href')
        }
        return result

    def delete_nodes_thread(self):
        LOGGER.debug(f"About to delete nodes from cluster with name: "
                     f"{self.cluster_name}")
        try:
            vapp = VApp(self.tenant_client, href=self.cluster['vapp_href'])
            template = self._get_template()
            self._update_task(
                TaskStatus.RUNNING,
                message=f"Deleting "
                        f"{len(self.req_spec.get(RequestKey.NODE_NAMES_LIST))}"
                        f" node(s) from "
                        f"{self.cluster_name}({self.cluster_id})")
            try:
                delete_nodes_from_cluster(
                    vapp,
                    template,
                    self.req_spec.get(RequestKey.NODE_NAMES_LIST),
                    self.req_spec.get(RequestKey.FORCE_DELETE))
            except Exception:
                LOGGER.error(f"Couldn't delete node "
                             f"{self.req_spec.get(RequestKey.NODE_NAMES_LIST)}"
                             f" from cluster:{self.cluster_name}")
            self._update_task(
                TaskStatus.RUNNING,
                message=f"Undeploying "
                        f"{len(self.req_spec.get(RequestKey.NODE_NAMES_LIST))}"
                        f" node(s) for {self.cluster_name}({self.cluster_id})")
            for vm_name in self.req_spec.get(RequestKey.NODE_NAMES_LIST):
                vm = VM(self.tenant_client, resource=vapp.get_vm(vm_name))
                try:
                    task = vm.undeploy()
                    self.tenant_client.get_task_monitor().wait_for_status(task)
                except Exception:
                    LOGGER.warning(f"Couldn't undeploy VM {vm_name}")
            self._update_task(
                TaskStatus.RUNNING,
                message=f"Deleting "
                        f"{len(self.req_spec.get(RequestKey.NODE_NAMES_LIST))}"
                        f" VM(s) for {self.cluster_name}({self.cluster_id})")
            task = vapp.delete_vms(self.req_spec.get(RequestKey.NODE_NAMES_LIST)) # noqa: E501
            self.tenant_client.get_task_monitor().wait_for_status(task)
            self._update_task(
                TaskStatus.SUCCESS,
                message=f"Deleted "
                        f"{len(self.req_spec.get(RequestKey.NODE_NAMES_LIST))}"
                        f" node(s) to cluster "
                        f"{self.cluster_name}({self.cluster_id})")
        except Exception as e:
            LOGGER.error(traceback.format_exc())
            error_obj = error_to_json(e)
            stack_trace = \
                ''.join(error_obj[ERROR_MESSAGE_KEY][ERROR_STACKTRACE_KEY])
            self._update_task(
                TaskStatus.ERROR,
                error_message=error_obj[ERROR_MESSAGE_KEY][ERROR_DESCRIPTION_KEY],  # noqa: E501
                stack_trace=stack_trace)
        finally:
            self._disconnect_sys_admin()

    @secure(required_rights=[CSE_NATIVE_DEPLOY_RIGHT_NAME])
    def resize_cluster(self, curr_cluster_info=None):
        """Resize the cluster of a given name to given number of worker nodes.

        :param str name: Name of the cluster
        :param int node_count: New size of the worker nodes
        (should be greater than the current number).
        :param dict curr_cluster_info: Current properties of the cluster

        :return response: response returned by create_nodes()
        :rtype: dict
        """
        cluster_name = self.req_spec[RequestKey.CLUSTER_NAME]
        num_workers = self.req_spec[RequestKey.NUM_WORKERS]

        if curr_cluster_info:
            curr_worker_count = len(curr_cluster_info['nodes'])
        else:
            cluster = self.get_cluster_info(cluster_name=cluster_name)
            curr_worker_count = len(cluster['nodes'])

        if curr_worker_count > num_workers:
            raise CseServerError(f"Automatic scale down is not supported for "
                                 f"vCD powered Kubernetes clusters. Use "
                                 f"'vcd cse delete node' command.")
        elif curr_worker_count == num_workers:
            raise CseServerError(f"Cluster - {cluster_name} is already at the "
                                 f"size of {curr_worker_count}.")

        self.req_spec[RequestKey.NUM_WORKERS] = num_workers - curr_worker_count
        response = self.create_nodes()
        return response

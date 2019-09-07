# container-service-extension
# Copyright (c) 2017 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

import functools
import threading
import uuid

import pkg_resources
from pyvcloud.vcd.client import TaskStatus
from pyvcloud.vcd.client import VCLOUD_STATUS_MAP
from pyvcloud.vcd.task import Task
from pyvcloud.vcd.vapp import VApp
from pyvcloud.vcd.vdc import VDC
from pyvcloud.vcd.vm import VM
import requests

from container_service_extension.abstract_broker import AbstractBroker
from container_service_extension.authorization import secure
from container_service_extension.cluster import add_nodes
from container_service_extension.cluster import delete_nodes_from_cluster
from container_service_extension.cluster import execute_script_in_nodes
from container_service_extension.cluster import get_all_clusters
from container_service_extension.cluster import get_cluster
from container_service_extension.cluster import get_master_ip
from container_service_extension.cluster import get_node_names
from container_service_extension.cluster import get_template
from container_service_extension.cluster import init_cluster
from container_service_extension.cluster import is_valid_cluster_name
from container_service_extension.cluster import join_cluster
from container_service_extension.exception_handler import error_to_json
from container_service_extension.exceptions import ClusterAlreadyExistsError
from container_service_extension.exceptions import ClusterInitializationError
from container_service_extension.exceptions import ClusterJoiningError
from container_service_extension.exceptions import ClusterNotFoundError
from container_service_extension.exceptions import ClusterOperationError
from container_service_extension.exceptions import CseServerError
from container_service_extension.exceptions import MasterNodeCreationError
from container_service_extension.exceptions import NFSNodeCreationError
from container_service_extension.exceptions import NodeCreationError
from container_service_extension.exceptions import NodeNotFoundError
from container_service_extension.exceptions import WorkerNodeCreationError
from container_service_extension.logger import SERVER_LOGGER as LOGGER
import container_service_extension.pyvcloud_utils as vcd_utils
from container_service_extension.server_constants import ClusterMetadataKey
from container_service_extension.server_constants import CSE_NATIVE_DEPLOY_RIGHT_NAME # noqa: E501
from container_service_extension.server_constants import K8S_PROVIDER_KEY
from container_service_extension.server_constants import K8sProvider
from container_service_extension.server_constants import LocalTemplateKey
from container_service_extension.server_constants import NodeType
from container_service_extension.shared_constants import ERROR_DESCRIPTION_KEY
from container_service_extension.shared_constants import ERROR_MESSAGE_KEY
from container_service_extension.shared_constants import ERROR_STACKTRACE_KEY
from container_service_extension.shared_constants import RequestKey
import container_service_extension.utils as utils
import container_service_extension.vsphere_utils as vs_utils


def run_async(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        t = threading.Thread(target=func, args=args, kwargs=kwargs,
                             daemon=True)
        t.start()
        return t

    return wrapper


class VcdBroker(AbstractBroker):
    """Handles cluster operations for 'native' k8s provider."""

    def __init__(self, tenant_auth_token):
        self.tenant_client = None
        self.client_session = None
        self.tenant_user_name = None
        self.tenant_user_id = None
        self.tenant_org_name = None
        self.tenant_org_href = None
        # populates above attributes
        super().__init__(tenant_auth_token)

        self._sys_admin_client = None # private: use sys_admin_client property
        self.task = None
        self.task_resource = None

    @property
    def sys_admin_client(self):
        if self._sys_admin_client is None:
            self._sys_admin_client = vcd_utils.get_sys_admin_client()
        return self._sys_admin_client

    def logout_sys_admin_client(self):
        if self._sys_admin_client is not None:
            self._sys_admin_client.logout()
        self._sys_admin_client = None

    def get_cluster_info(self, data):
        """Get cluster metadata as well as node data.

        Common broker function that validates data for the 'cluster info'
        operation and returns cluster/node metadata as dictionary.

        Required data: cluster_name
        Optional data and default values: org_name=None, ovdc_name=None
        """
        required = [
            RequestKey.CLUSTER_NAME
        ]
        utils.ensure_keys_in_dict(required, data, dict_name='data')
        defaults = {
            RequestKey.ORG_NAME: None,
            RequestKey.OVDC_NAME: None
        }
        validated_data = {**defaults, **data}
        cluster_name = validated_data[RequestKey.CLUSTER_NAME]
        cluster = get_cluster(self.tenant_client, cluster_name,
                              org_name=validated_data[RequestKey.ORG_NAME],
                              ovdc_name=validated_data[RequestKey.OVDC_NAME])

        cluster[K8S_PROVIDER_KEY] = K8sProvider.NATIVE
        vapp = VApp(self.tenant_client, href=cluster['vapp_href'])
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

    def list_clusters(self, data):
        """List all native clusters and their relevant metadata.

        Common broker function that validates data for the 'list clusters'
        operation and returns a list of cluster data.

        Optional data and default values: org_name=None, ovdc_name=None
        """
        defaults = {
            RequestKey.ORG_NAME: None,
            RequestKey.OVDC_NAME: None
        }
        validated_data = {**defaults, **data}

        raw_clusters = get_all_clusters(
            self.tenant_client,
            org_name=validated_data[RequestKey.ORG_NAME],
            ovdc_name=validated_data[RequestKey.OVDC_NAME])

        clusters = []
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

    def get_cluster_config(self, data):
        """Get the cluster's kube config contents.

        Common broker function that validates data for 'cluster config'
        operation and returns the cluster's kube config file contents
        as a string.

        Required data: cluster_name
        Optional data and default values: org_name=None, ovdc_name=None
        """
        required = [
            RequestKey.CLUSTER_NAME
        ]
        utils.ensure_keys_in_dict(required, data, dict_name='data')
        defaults = {
            RequestKey.ORG_NAME: None,
            RequestKey.OVDC_NAME: None
        }
        validated_data = {**defaults, **data}

        cluster_name = validated_data[RequestKey.CLUSTER_NAME]
        cluster = get_cluster(self.tenant_client, cluster_name,
                              org_name=validated_data[RequestKey.ORG_NAME],
                              ovdc_name=validated_data[RequestKey.OVDC_NAME])
        vapp = VApp(self.tenant_client, href=cluster['vapp_href'])
        node_names = get_node_names(vapp, NodeType.MASTER)

        all_results = []
        try:
            for node_name in node_names:
                LOGGER.debug(f"getting file from node {node_name}")
                password = vapp.get_admin_password(node_name)
                vs = vs_utils.get_vsphere(self.sys_admin_client, vapp,
                                          vm_name=node_name, logger=LOGGER)
                vs.connect()
                moid = vapp.get_vm_moid(node_name)
                vm = vs.get_vm_by_moid(moid)
                filename = '/root/.kube/config'
                result = vs.download_file_from_guest(vm, 'root',
                                                     password,
                                                     filename)
                all_results.append(result)
        finally:
            self.logout_sys_admin_client()

        if len(all_results) == 0 or all_results[0].status_code != requests.codes.ok: # noqa: E501
            raise ClusterOperationError("Couldn't get cluster configuration")
        return all_results[0].content.decode()

    @secure(required_rights=[CSE_NATIVE_DEPLOY_RIGHT_NAME])
    def create_cluster(self, data):
        """Start the cluster creation operation.

        Common broker function that validates data for the 'create cluster'
        operation and returns a dictionary with cluster detail and task
        information. Calls the asyncronous cluster create function that
        actually performs the work. The returned `result['task_href']` can
        be polled to get updates on task progress.

        Required data: cluster_name, org_name, ovdc_name, network_name
        Optional data and default values: num_nodes=2, num_cpu=None,
            mb_memory=None, storage_profile_name=None, ssh_key_filepath=None,
            template_name=default, template_revision=default, enable_nfs=False,
            rollback=True
        """
        required = [
            RequestKey.CLUSTER_NAME,
            RequestKey.ORG_NAME,
            RequestKey.OVDC_NAME,
            RequestKey.NETWORK_NAME
        ]
        utils.ensure_keys_in_dict(required, data, dict_name='data')
        cluster_name = data[RequestKey.CLUSTER_NAME]
        # check that cluster name is syntactically valid
        if not is_valid_cluster_name(cluster_name):
            raise CseServerError(f"Invalid cluster name '{cluster_name}'")
        # check that cluster name doesn't already exist
        try:
            get_cluster(self.tenant_client, cluster_name,
                        org_name=data[RequestKey.ORG_NAME],
                        ovdc_name=data[RequestKey.OVDC_NAME])
            raise ClusterAlreadyExistsError(f"Cluster {cluster_name} "
                                            f"already exists.")
        except ClusterNotFoundError:
            pass
        # check that requested/default template is valid
        template = get_template(
            name=data.get(RequestKey.TEMPLATE_NAME),
            revision=data.get(RequestKey.TEMPLATE_REVISION))
        defaults = {
            RequestKey.NUM_WORKERS: 2,
            RequestKey.NUM_CPU: None,
            RequestKey.MB_MEMORY: None,
            RequestKey.STORAGE_PROFILE_NAME: None,
            RequestKey.SSH_KEY_FILEPATH: None,
            RequestKey.TEMPLATE_NAME: template[LocalTemplateKey.NAME],
            RequestKey.TEMPLATE_REVISION: template[LocalTemplateKey.REVISION],
            RequestKey.ENABLE_NFS: False,
            RequestKey.ROLLBACK: True,
        }
        validated_data = {**defaults, **data}
        template_name = validated_data[RequestKey.TEMPLATE_NAME]
        template_revision = validated_data[RequestKey.TEMPLATE_REVISION]

        # check that requested number of worker nodes is at least more than 1
        num_workers = validated_data[RequestKey.NUM_WORKERS]
        if num_workers < 1:
            raise CseServerError(f"Worker node count must be > 0 "
                                 f"(received {num_workers}).")

        cluster_id = str(uuid.uuid4())
        # must _update_task or else self.task_resource is None
        # do not logout of sys admin, or else in pyvcloud's session.request()
        # call, session becomes None
        self._update_task(
            TaskStatus.RUNNING,
            message=f"Creating cluster vApp '{cluster_name}' ({cluster_id})"
                    f" from template '{template_name}' "
                    f"(revision {template_revision})")
        self._create_cluster_async(
            org_name=validated_data[RequestKey.ORG_NAME],
            ovdc_name=validated_data[RequestKey.OVDC_NAME],
            cluster_name=cluster_name,
            cluster_id=cluster_id,
            template_name=template_name,
            template_revision=template_revision,
            num_workers=validated_data[RequestKey.NUM_WORKERS],
            network_name=validated_data[RequestKey.NETWORK_NAME],
            num_cpu=validated_data[RequestKey.NUM_CPU],
            mb_memory=validated_data[RequestKey.MB_MEMORY],
            storage_profile_name=validated_data[RequestKey.STORAGE_PROFILE_NAME], # noqa: E501
            ssh_key_filepath=validated_data[RequestKey.SSH_KEY_FILEPATH],
            enable_nfs=validated_data[RequestKey.ENABLE_NFS],
            rollback=validated_data[RequestKey.ROLLBACK])

        return {
            'name': cluster_name,
            'cluster_id': cluster_id,
            'task_href': self.task_resource.get('href')
        }

    @secure(required_rights=[CSE_NATIVE_DEPLOY_RIGHT_NAME])
    def resize_cluster(self, data):
        """Start the resize cluster operation.

        Common broker function that validates data for the 'resize cluster'
        operation. Native clusters cannot be resized down. Creating nodes is an
        asynchronous task, so the returned `result['task_href']` can be polled
        to get updates on task progress.

        Required data: cluster_name, network, num_nodes
        Optional data and default values: org_name=None, ovdc_name=None,
            rollback=True, template_name=None, template_revision=None
        """
        # TODO default template for resizing should be master's template
        required = [
            RequestKey.CLUSTER_NAME,
            RequestKey.NUM_WORKERS,
            RequestKey.NETWORK_NAME
        ]
        utils.ensure_keys_in_dict(required, data, dict_name='data')
        defaults = {
            RequestKey.ORG_NAME: None,
            RequestKey.OVDC_NAME: None,
            RequestKey.ROLLBACK: True,
            RequestKey.TEMPLATE_NAME: None,
            RequestKey.TEMPLATE_REVISION: None
        }
        validated_data = {**defaults, **data}
        cluster_name = validated_data[RequestKey.CLUSTER_NAME]
        num_workers_wanted = validated_data[RequestKey.NUM_WORKERS]
        if num_workers_wanted < 1:
            raise CseServerError(f"Worker node count must be > 0 "
                                 f"(received {num_workers_wanted}).")

        # cluster_handler.py already makes a cluster info API call to vCD, but
        # that call does not return any node info, so this additional
        # cluster info call must be made
        cluster_info = self.get_cluster_info(validated_data)
        num_workers = len(cluster_info['nodes'])
        if num_workers > num_workers_wanted:
            raise CseServerError(f"Automatic scale down is not supported for "
                                 f"vCD powered Kubernetes clusters. Use "
                                 f"'vcd cse delete node' command.")
        elif num_workers == num_workers_wanted:
            raise CseServerError(f"Cluster '{cluster_name}' already has "
                                 f"{num_workers} worker nodes.")

        validated_data[RequestKey.NUM_WORKERS] = num_workers_wanted - num_workers # noqa: E501
        return self.create_nodes(validated_data)

    @secure(required_rights=[CSE_NATIVE_DEPLOY_RIGHT_NAME])
    def delete_cluster(self, data):
        """Start the delete cluster operation.

        Common broker function that validates data for 'delete cluster'
        operation. Deleting nodes is an asynchronous task, so the returned
        `result['task_href']` can be polled to get updates on task progress.

        Required data: cluster_name
        Optional data and default values: org_name=None, ovdc_name=None
        """
        required = [
            RequestKey.CLUSTER_NAME
        ]
        utils.ensure_keys_in_dict(required, data, dict_name='data')
        defaults = {
            RequestKey.ORG_NAME: None,
            RequestKey.OVDC_NAME: None
        }
        validated_data = {**defaults, **data}
        cluster_name = validated_data[RequestKey.CLUSTER_NAME]

        cluster = get_cluster(self.tenant_client, cluster_name,
                              org_name=validated_data[RequestKey.ORG_NAME],
                              ovdc_name=validated_data[RequestKey.OVDC_NAME])
        cluster_id = cluster['cluster_id']
        # must _update_task here or else self.task_resource is None
        # do not logout of sys admin, or else in pyvcloud's session.request()
        # call, session becomes None
        self._update_task(
            TaskStatus.RUNNING,
            message=f"Deleting cluster {cluster_name} ({cluster_id})")
        self._delete_cluster_async(cluster_name=cluster_name,
                                   cluster_vdc_href=cluster['vdc_href'])

        return {
            'cluster_name': cluster_name,
            'task_href': self.task_resource.get('href')
        }

    def get_node_info(self, data):
        """Get node metadata as dictionary.

        Required data: cluster_name, node_name
        Optional data and default values: org_name=None, ovdc_name=None
        """
        required = [
            RequestKey.CLUSTER_NAME,
            RequestKey.NODE_NAME
        ]
        utils.ensure_keys_in_dict(required, data, dict_name='data')
        defaults = {
            RequestKey.ORG_NAME: None,
            RequestKey.OVDC_NAME: None
        }
        validated_data = {**defaults, **data}
        cluster_name = validated_data[RequestKey.CLUSTER_NAME]
        node_name = validated_data[RequestKey.NODE_NAME]

        cluster = get_cluster(self.tenant_client, cluster_name,
                              org_name=validated_data[RequestKey.ORG_NAME],
                              ovdc_name=validated_data[RequestKey.OVDC_NAME])

        vapp = VApp(self.tenant_client, href=cluster['vapp_href'])
        vms = vapp.get_all_vms()
        node_info = None
        for vm in vms:
            vm_name = vm.get('name')
            if node_name != vm_name:
                continue

            node_info = {
                'name': vm_name,
                'numberOfCpus': '',
                'memoryMB': '',
                'status': VCLOUD_STATUS_MAP.get(int(vm.get('status'))),
                'ipAddress': ''
            }
            if hasattr(vm, 'VmSpecSection'):
                node_info['numberOfCpus'] = vm.VmSpecSection.NumCpus.text
                node_info['memoryMB'] = vm.VmSpecSection.MemoryResourceMb.Configured.text # noqa: E501
            try:
                node_info['ipAddress'] = vapp.get_primary_ip(vm_name)
            except Exception:
                LOGGER.debug(f"Unable to get ip address of node {vm_name}")
            if vm_name.startswith(NodeType.MASTER):
                node_info['node_type'] = 'master'
            elif vm_name.startswith(NodeType.WORKER):
                node_info['node_type'] = 'worker'
            elif vm_name.startswith(NodeType.NFS):
                node_info['node_type'] = 'nfs'
                node_info['exports'] = self._get_nfs_exports(node_info['ipAddress'], vapp, vm_name) # noqa: E501
        if node_info is None:
            raise NodeNotFoundError(f"Node '{node_name}' not found in "
                                    f"cluster '{cluster_name}'")
        return node_info

    @secure(required_rights=[CSE_NATIVE_DEPLOY_RIGHT_NAME])
    def create_nodes(self, data):
        """Start the create nodes operation.

        Validates data for 'node create' operation. Creating nodes is an
        asynchronous task, so the returned `result['task_href']` can be polled
        to get updates on task progress.

        Required data: cluster_name, network_name
        Optional data and default values: num_nodes=2, num_cpu=None,
            mb_memory=None, storage_profile_name=None, ssh_key_filepath=None,
            template_name=default, template_revision=default, enable_nfs=False,
            rollback=True
        """
        required = [
            RequestKey.CLUSTER_NAME,
            RequestKey.NETWORK_NAME
        ]
        utils.ensure_keys_in_dict(required, data, dict_name='data')
        cluster_name = data[RequestKey.CLUSTER_NAME]
        # check that requested/default template is valid
        template = get_template(
            name=data.get(RequestKey.TEMPLATE_NAME),
            revision=data.get(RequestKey.TEMPLATE_REVISION))
        defaults = {
            RequestKey.ORG_NAME: None,
            RequestKey.OVDC_NAME: None,
            RequestKey.NUM_WORKERS: 1,
            RequestKey.NUM_CPU: None,
            RequestKey.MB_MEMORY: None,
            RequestKey.STORAGE_PROFILE_NAME: None,
            RequestKey.SSH_KEY_FILEPATH: None,
            RequestKey.TEMPLATE_NAME: template[LocalTemplateKey.NAME],
            RequestKey.TEMPLATE_REVISION: template[LocalTemplateKey.REVISION],
            RequestKey.ENABLE_NFS: False,
            RequestKey.ROLLBACK: True,
        }
        validated_data = {**defaults, **data}

        # TODO HACK default dictionary combining needs to be fixed
        validated_data[RequestKey.TEMPLATE_NAME] = validated_data[RequestKey.TEMPLATE_NAME] or template[LocalTemplateKey.NAME] # noqa: E501
        validated_data[RequestKey.TEMPLATE_REVISION] = validated_data[RequestKey.TEMPLATE_REVISION] or template[LocalTemplateKey.REVISION] # noqa: E501

        template_name = validated_data[RequestKey.TEMPLATE_NAME]
        template_revision = validated_data[RequestKey.TEMPLATE_REVISION]

        num_workers = validated_data[RequestKey.NUM_WORKERS]
        if num_workers < 1:
            raise CseServerError(f"Worker node count must be > 0 "
                                 f"(received {num_workers}).")

        cluster = get_cluster(self.tenant_client, cluster_name,
                              org_name=validated_data[RequestKey.ORG_NAME],
                              ovdc_name=validated_data[RequestKey.OVDC_NAME])
        cluster_id = cluster['cluster_id']
        # must _update_task here or else self.task_resource is None
        # do not logout of sys admin, or else in pyvcloud's session.request()
        # call, session becomes None
        self._update_task(
            TaskStatus.RUNNING,
            message=f"Creating {num_workers} node(s) from template "
                    f"'{template_name}' (revision {template_revision}) and "
                    f"adding to {cluster_name} ({cluster_id})")
        self._create_nodes_async(
            cluster_name=cluster_name,
            cluster_vdc_href=cluster['vdc_href'],
            cluster_vapp_href=cluster['vapp_href'],
            cluster_id=cluster_id,
            template_name=template_name,
            template_revision=template_revision,
            num_workers=validated_data[RequestKey.NUM_WORKERS],
            network_name=validated_data[RequestKey.NETWORK_NAME],
            num_cpu=validated_data[RequestKey.NUM_CPU],
            mb_memory=validated_data[RequestKey.MB_MEMORY],
            storage_profile_name=validated_data[RequestKey.STORAGE_PROFILE_NAME], # noqa: E501
            ssh_key_filepath=validated_data[RequestKey.SSH_KEY_FILEPATH],
            enable_nfs=validated_data[RequestKey.ENABLE_NFS],
            rollback=validated_data[RequestKey.ROLLBACK])

        return {
            'cluster_name': cluster_name,
            'task_href': self.task_resource.get('href')
        }

    @secure(required_rights=[CSE_NATIVE_DEPLOY_RIGHT_NAME])
    def delete_nodes(self, data):
        """Start the delete nodes operation.

        Validates data for the 'delete nodes' operation. Deleting nodes is an
        asynchronous task, so the returned `result['task_href']` can be polled
        to get updates on task progress.

        Required data: cluster_name, node_names_list
        Optional data and default values: org_name=None, ovdc_name=None
        """
        required = [
            RequestKey.CLUSTER_NAME,
            RequestKey.NODE_NAMES_LIST
        ]
        utils.ensure_keys_in_dict(required, data, dict_name='data')
        defaults = {
            RequestKey.ORG_NAME: None,
            RequestKey.OVDC_NAME: None
        }
        validated_data = {**defaults, **data}
        cluster_name = validated_data[RequestKey.CLUSTER_NAME]
        node_names_list = validated_data[RequestKey.NODE_NAMES_LIST]
        # check that there are nodes to delete
        if len(node_names_list) == 0:
            LOGGER.debug("No nodes specified to delete")
            return {'body': {}}
        # check that master node is not in specified nodes
        for node in node_names_list:
            if node.startswith(NodeType.MASTER):
                raise CseServerError(f"Can't delete a master node: '{node}'.")

        cluster = get_cluster(self.tenant_client, cluster_name,
                              org_name=validated_data[RequestKey.ORG_NAME],
                              ovdc_name=validated_data[RequestKey.OVDC_NAME])
        cluster_id = cluster['cluster_id']
        # must _update_task here or else self.task_resource is None
        # do not logout of sys admin, or else in pyvcloud's session.request()
        # call, session becomes None
        self._update_task(
            TaskStatus.RUNNING,
            message=f"Deleting {len(node_names_list)} node(s)"
                    f" from cluster {cluster_name}({cluster_id})")
        self._delete_nodes_async(
            cluster_name=cluster_name,
            cluster_vapp_href=cluster['vapp_href'],
            node_names_list=validated_data[RequestKey.NODE_NAMES_LIST])

        return {
            'cluster_name': cluster_name,
            'task_href': self.task_resource.get('href')
        }

    # all parameters following '*args' are required and keyword-only
    @run_async
    def _create_cluster_async(self, *args,
                              org_name, ovdc_name, cluster_name, cluster_id,
                              template_name, template_revision, num_workers,
                              network_name, num_cpu, mb_memory,
                              storage_profile_name, ssh_key_filepath,
                              enable_nfs, rollback):
        org = vcd_utils.get_org(self.tenant_client, org_name=org_name)
        vdc = vcd_utils.get_vdc(
            self.tenant_client, vdc_name=ovdc_name, org=org)

        LOGGER.debug(f"About to create cluster {cluster_name} on {ovdc_name}"
                     f" with {num_workers} worker nodes, "
                     f"storage profile={storage_profile_name}")
        try:
            self._update_task(
                TaskStatus.RUNNING,
                message=f"Creating cluster vApp {cluster_name}({cluster_id})")
            try:
                vapp_resource = \
                    vdc.create_vapp(cluster_name,
                                    description=f"cluster {cluster_name}",
                                    network=network_name,
                                    fence_mode='bridged')
            except Exception as e:
                msg = f"Error while creating vApp: {e}"
                LOGGER.debug(str(e))
                raise ClusterOperationError(msg)
            self.tenant_client.get_task_monitor().wait_for_status(vapp_resource.Tasks.Task[0]) # noqa: E501

            template = get_template(template_name, template_revision)

            tags = {
                ClusterMetadataKey.CLUSTER_ID: cluster_id,
                ClusterMetadataKey.CSE_VERSION: pkg_resources.require('container-service-extension')[0].version, # noqa: E501
                ClusterMetadataKey.TEMPLATE_NAME: template[LocalTemplateKey.NAME], # noqa: E501
                ClusterMetadataKey.TEMPLATE_REVISION: template[LocalTemplateKey.REVISION] # noqa: E501
            }
            vapp = VApp(self.tenant_client, href=vapp_resource.get('href'))
            task = vapp.set_multiple_metadata(tags)
            self.tenant_client.get_task_monitor().wait_for_status(task)

            self._update_task(
                TaskStatus.RUNNING,
                message=f"Creating master node for "
                        f"{cluster_name} ({cluster_id})")
            vapp.reload()
            server_config = utils.get_server_runtime_config()
            catalog_name = server_config['broker']['catalog']
            try:
                add_nodes(client=self.tenant_client,
                          num_nodes=num_workers,
                          node_type=NodeType.MASTER,
                          org=org,
                          vdc=vdc,
                          vapp=vapp,
                          catalog_name=catalog_name,
                          template=template,
                          network_name=network_name,
                          num_cpu=num_cpu,
                          memory_in_mb=mb_memory,
                          storage_profile=storage_profile_name,
                          ssh_key_filepath=ssh_key_filepath)
            except Exception as e:
                raise MasterNodeCreationError("Error adding master node:",
                                              str(e))

            self._update_task(
                TaskStatus.RUNNING,
                message=f"Initializing cluster {cluster_name} ({cluster_id})")
            vapp.reload()
            init_cluster(vapp, template[LocalTemplateKey.NAME],
                         template[LocalTemplateKey.REVISION])
            master_ip = get_master_ip(vapp)
            task = vapp.set_metadata('GENERAL', 'READWRITE', 'cse.master.ip',
                                     master_ip)
            self.tenant_client.get_task_monitor().wait_for_status(task)

            self._update_task(
                TaskStatus.RUNNING,
                message=f"Creating {num_workers} node(s) for "
                        f"{cluster_name}({cluster_id})")
            try:
                add_nodes(client=self.tenant_client,
                          num_nodes=num_workers,
                          node_type=NodeType.WORKER,
                          org=org,
                          vdc=vdc,
                          vapp=vapp,
                          catalog_name=catalog_name,
                          template=template,
                          network_name=network_name,
                          num_cpu=num_cpu,
                          memory_in_mb=mb_memory,
                          storage_profile=storage_profile_name,
                          ssh_key_filepath=ssh_key_filepath)
            except Exception as e:
                raise WorkerNodeCreationError("Error creating worker node:",
                                              str(e))

            self._update_task(
                TaskStatus.RUNNING,
                message=f"Adding {num_workers} node(s) to "
                        f"{cluster_name}({cluster_id})")
            vapp.reload()
            join_cluster(vapp, template[LocalTemplateKey.NAME],
                         template[LocalTemplateKey.REVISION])

            if enable_nfs:
                self._update_task(
                    TaskStatus.RUNNING,
                    message=f"Creating NFS node for "
                            f"{cluster_name} ({cluster_id})")
                try:
                    add_nodes(client=self.tenant_client,
                              num_nodes=1,
                              node_type=NodeType.NFS,
                              org=org,
                              vdc=vdc,
                              vapp=vapp,
                              catalog_name=catalog_name,
                              template=template,
                              network_name=network_name,
                              num_cpu=num_cpu,
                              memory_in_mb=mb_memory,
                              storage_profile=storage_profile_name,
                              ssh_key_filepath=ssh_key_filepath)
                except Exception as e:
                    raise NFSNodeCreationError("Error creating NFS node:",
                                               str(e))

            self._update_task(
                TaskStatus.SUCCESS,
                message=f"Created cluster {cluster_name} ({cluster_id})")
        except (MasterNodeCreationError, WorkerNodeCreationError,
                NFSNodeCreationError, ClusterJoiningError,
                ClusterInitializationError, ClusterOperationError) as e:
            if rollback:
                msg = f"Error creating cluster {cluster_name}. " \
                      f"Deleting cluster (rollback=True)"
                self._update_task(TaskStatus.RUNNING, message=msg)
                LOGGER.info(msg)
                try:
                    cluster = get_cluster(self.tenant_client,
                                          cluster_name,
                                          cluster_id=cluster_id,
                                          org_name=org_name,
                                          ovdc_name=ovdc_name)
                    self._delete_cluster(cluster_name=cluster_name,
                                         cluster_vdc_href=cluster['vdc_href'])
                except Exception:
                    LOGGER.error(f"Failed to delete cluster {cluster_name}",
                                 exc_info=True)
            LOGGER.error(f"Error creating cluster {cluster_name}",
                         exc_info=True)
            error_obj = error_to_json(e)
            stack_trace = ''.join(error_obj[ERROR_MESSAGE_KEY][ERROR_STACKTRACE_KEY]) # noqa: E501
            self._update_task(
                TaskStatus.ERROR,
                error_message=error_obj[ERROR_MESSAGE_KEY][ERROR_DESCRIPTION_KEY], # noqa: E501
                stack_trace=stack_trace)
            # raising an exception here prints a stacktrace to server console
        except Exception as e:
            LOGGER.error(f"Unknown error creating cluster {cluster_name}",
                         exc_info=True)
            error_obj = error_to_json(e)
            stack_trace = ''.join(error_obj[ERROR_MESSAGE_KEY][ERROR_STACKTRACE_KEY]) # noqa: E501
            self._update_task(
                TaskStatus.ERROR,
                error_message=error_obj[ERROR_MESSAGE_KEY][ERROR_DESCRIPTION_KEY], # noqa: E501
                stack_trace=stack_trace)
        finally:
            self.logout_sys_admin_client()

    @run_async
    def _create_nodes_async(self, *args,
                            cluster_name, cluster_vdc_href, cluster_vapp_href,
                            cluster_id, template_name, template_revision,
                            num_workers, network_name, num_cpu, mb_memory,
                            storage_profile_name, ssh_key_filepath, enable_nfs,
                            rollback):
        org = vcd_utils.get_org(self.tenant_client)
        vdc = VDC(self.tenant_client, href=cluster_vdc_href)
        vapp = VApp(self.tenant_client, href=cluster_vapp_href)
        template = get_template(name=template_name, revision=template_revision)
        msg = f"Creating {num_workers} node(s) from template " \
              f"'{template_name}' (revision {template_revision}) and " \
              f"adding to {cluster_name} ({cluster_id})"
        LOGGER.debug(msg)
        try:
            self._update_task(TaskStatus.RUNNING, message=msg)

            node_type = NodeType.WORKER
            if enable_nfs:
                node_type = NodeType.NFS

            server_config = utils.get_server_runtime_config()
            catalog_name = server_config['broker']['catalog']

            new_nodes = add_nodes(client=self.tenant_client,
                                  num_nodes=num_workers,
                                  node_type=node_type,
                                  org=org,
                                  vdc=vdc,
                                  vapp=vapp,
                                  catalog_name=catalog_name,
                                  template=template,
                                  network_name=network_name,
                                  num_cpu=num_cpu,
                                  memory_in_mb=mb_memory,
                                  storage_profile=storage_profile_name,
                                  ssh_key_filepath=ssh_key_filepath)

            if node_type == NodeType.NFS:
                self._update_task(
                    TaskStatus.SUCCESS,
                    message=f"Created {num_workers} node(s) for "
                            f"{cluster_name}({cluster_id})")
            elif node_type == NodeType.WORKER:
                self._update_task(
                    TaskStatus.RUNNING,
                    message=f"Adding {num_workers} node(s) to cluster "
                            f"{cluster_name}({cluster_id})")
                target_nodes = []
                for spec in new_nodes['specs']:
                    target_nodes.append(spec['target_vm_name'])
                vapp.reload()
                join_cluster(vapp, template[LocalTemplateKey.NAME],
                             template[LocalTemplateKey.REVISION], target_nodes)
                self._update_task(
                    TaskStatus.SUCCESS,
                    message=f"Added {num_workers} node(s) to cluster "
                            f"{cluster_name}({cluster_id})")
        except NodeCreationError as e:
            if rollback:
                msg = f"Error adding nodes to {cluster_name} {cluster_id}." \
                      f" Deleting nodes: {e.node_names} (rollback=True)"
                self._update_task(TaskStatus.RUNNING, message=msg)
                LOGGER.info(msg)
                try:
                    self._delete_nodes(cluster_name=cluster_name,
                                       cluster_vapp_href=cluster_vapp_href,
                                       node_names_list=e.node_names)
                except Exception:
                    LOGGER.error(f"Failed to delete nodes {e.node_names} "
                                 f"from cluster {cluster_name}",
                                 exc_info=True)
            LOGGER.error(f"Error adding nodes to {cluster_name}",
                         exc_info=True)
            error_obj = error_to_json(e)
            LOGGER.error(str(e), exc_info=True)
            stack_trace = ''.join(error_obj[ERROR_MESSAGE_KEY][ERROR_STACKTRACE_KEY]) # noqa: E501
            self._update_task(
                TaskStatus.ERROR,
                error_message=error_obj[ERROR_MESSAGE_KEY][ERROR_DESCRIPTION_KEY], # noqa: E501
                stack_trace=stack_trace)
            # raising an exception here prints a stacktrace to server console
        except Exception as e:
            error_obj = error_to_json(e)
            LOGGER.error(str(e), exc_info=True)
            stack_trace = ''.join(error_obj[ERROR_MESSAGE_KEY][ERROR_STACKTRACE_KEY]) # noqa: E501
            self._update_task(
                TaskStatus.ERROR,
                error_message=error_obj[ERROR_MESSAGE_KEY][ERROR_DESCRIPTION_KEY], # noqa: E501
                stack_trace=stack_trace)
        finally:
            self.logout_sys_admin_client()

    # all parameters following '*args' are required and keyword-only
    @run_async
    def _delete_nodes_async(self, *args,
                            cluster_name, cluster_vapp_href, node_names_list):
        try:
            self._update_task(
                TaskStatus.RUNNING,
                message=f"Deleting {len(node_names_list)} node(s) "
                        f"from cluster {cluster_name}")
            self._delete_nodes(cluster_name=cluster_name,
                               cluster_vapp_href=cluster_vapp_href,
                               node_names_list=node_names_list)
            self._update_task(
                TaskStatus.SUCCESS,
                message=f"Deleted {len(node_names_list)} node(s)"
                        f" to cluster {cluster_name}")
        except Exception as e:
            LOGGER.error(f"Unexpected error while deleting nodes "
                         f"{node_names_list}: {e}",
                         exc_info=True)
            error_obj = error_to_json(e)
            stack_trace = ''.join(error_obj[ERROR_MESSAGE_KEY][ERROR_STACKTRACE_KEY]) # noqa: E501
            self._update_task(
                TaskStatus.ERROR,
                error_message=error_obj[ERROR_MESSAGE_KEY][ERROR_DESCRIPTION_KEY], # noqa: E501
                stack_trace=stack_trace)
        finally:
            self.logout_sys_admin_client()

    # all parameters following '*args' are required and keyword-only
    @run_async
    def _delete_cluster_async(self, *args, cluster_name, cluster_vdc_href):
        try:
            self._update_task(
                TaskStatus.RUNNING,
                message=f"Deleting cluster {cluster_name}")
            self._delete_cluster(cluster_name=cluster_name,
                                 cluster_vdc_href=cluster_vdc_href)
            self._update_task(
                TaskStatus.SUCCESS,
                message=f"Deleted cluster {cluster_name}")
        except Exception as e:
            LOGGER.error(f"Unexpected error while deleting cluster: {e}",
                         exc_info=True)
            self._update_task(TaskStatus.ERROR, error_message=str(e))
        finally:
            self.logout_sys_admin_client()

    # all parameters following '*args' are required and keyword-only
    # synchronous cluster/node delete functions are required for rollback
    def _delete_cluster(self, *args, cluster_name, cluster_vdc_href):
        LOGGER.debug(f"About to delete cluster with name: {cluster_name}")
        vdc = VDC(self.tenant_client, href=cluster_vdc_href)
        task = vdc.delete_vapp(cluster_name, force=True)
        self.tenant_client.get_task_monitor().wait_for_status(task)

    # all parameters following '*args' are required and keyword-only
    def _delete_nodes(self, *args,
                      cluster_name, cluster_vapp_href, node_names_list):
        LOGGER.debug(f"About to delete nodes {node_names_list} "
                     f"from cluster {cluster_name}")
        vapp = VApp(self.tenant_client, href=cluster_vapp_href)
        try:
            delete_nodes_from_cluster(vapp, node_names_list)
        except Exception:
            LOGGER.error(f"Couldn't delete node {node_names_list} "
                         f"from cluster:{cluster_name}")
        for vm_name in node_names_list:
            vm = VM(self.tenant_client, resource=vapp.get_vm(vm_name))
            try:
                task = vm.undeploy()
                self.tenant_client.get_task_monitor().wait_for_status(task)
            except Exception:
                LOGGER.warning(f"Couldn't undeploy VM {vm_name}")
        task = vapp.delete_vms(node_names_list)
        self.tenant_client.get_task_monitor().wait_for_status(task)

    def _update_task(self, status, message='', error_message=None,
                     stack_trace=''):
        """Update task or create it if it does not exist.

        This function should only be used in the x_async functions, or in the
        6 common broker functions to create the required task.
        When this function is used, it logs in the sys admin client if it is
        not already logged in, but it does not log out. This is because many
        _update_task() calls are used in sequence until the task succeeds or
        fails. Once the task is updated to a success or failure state, then
        the sys admin client should be logged out.

        Another reason for decoupling sys admin logout and this function is
        because if any unknown errors occur during an operation, there should
        be a finally clause that takes care of logging out.
        """
        if not self.tenant_client.is_sysadmin():
            stack_trace = ''

        if self.task is None:
            self.task = Task(self.sys_admin_client)

        task_href = None
        if self.task_resource is not None:
            task_href = self.task_resource.get('href')

        org = vcd_utils.get_org(self.tenant_client)
        user_href = org.get_user(self.client_session.get('user')).get('href')

        self.task_resource = self.task.update(
            status=status.value,
            namespace='vcloud.cse',
            operation=message,
            operation_name='cluster operation',
            details='',
            progress=None,
            owner_href=self.tenant_org_href,
            owner_name=self.tenant_org_name,
            owner_type='application/vnd.vmware.vcloud.org+xml',
            user_href=user_href,
            user_name=self.tenant_user_name,
            org_href=self.tenant_org_href,
            task_href=task_href,
            error_message=error_message,
            stack_trace=stack_trace
        )

    def _get_nfs_exports(self, ip, vapp, vm_name):
        """Get the exports from remote NFS server (helper method).

        :param ip: (str): IP address of the NFS server
        :param vapp: (pyvcloud.vcd.vapp.VApp): The vApp or cluster
         to which node belongs
        :param vm_name: name of node's VM

        :return: (List): List of exports
        """
        script = f"#!/usr/bin/env bash\nshowmount -e {ip}"
        result = execute_script_in_nodes(vapp=vapp, node_names=[vm_name],
                                         script=script, check_tools=False)
        lines = result[0][1].content.decode().split('\n')
        exports = []
        for index in range(1, len(lines) - 1):
            export = lines[index].strip().split()[0]
            exports.append(export)
        return exports

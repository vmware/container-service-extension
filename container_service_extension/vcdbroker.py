# container-service-extension
# Copyright (c) 2017 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

import copy
import random
import re
import string
import time
import uuid

import pkg_resources
from pyvcloud.vcd.client import QueryResultFormat
from pyvcloud.vcd.client import TaskStatus
from pyvcloud.vcd.client import VCLOUD_STATUS_MAP
from pyvcloud.vcd.org import Org
from pyvcloud.vcd.task import Task
from pyvcloud.vcd.vapp import VApp
from pyvcloud.vcd.vdc import VDC
from pyvcloud.vcd.vm import VM
import requests
import semantic_version as semver

from container_service_extension.abstract_broker import AbstractBroker
from container_service_extension.authorization import secure
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
from container_service_extension.exceptions import NodeOperationError
from container_service_extension.exceptions import ScriptExecutionError
from container_service_extension.exceptions import WorkerNodeCreationError
import container_service_extension.local_template_manager as ltm
from container_service_extension.logger import SERVER_LOGGER as LOGGER
import container_service_extension.pyvcloud_utils as vcd_utils
import container_service_extension.request_handlers.request_utils as req_utils
from container_service_extension.server_constants import ClusterMetadataKey
from container_service_extension.server_constants import CSE_NATIVE_DEPLOY_RIGHT_NAME # noqa: E501
from container_service_extension.server_constants import K8S_PROVIDER_KEY
from container_service_extension.server_constants import K8sProvider
from container_service_extension.server_constants import LocalTemplateKey
from container_service_extension.server_constants import NodeType
from container_service_extension.server_constants import ScriptFile
from container_service_extension.server_constants import SYSTEM_ORG_NAME
from container_service_extension.shared_constants import RequestKey
from container_service_extension.telemetry.constants import CseOperation
from container_service_extension.telemetry.constants import PayloadKey
from container_service_extension.telemetry.telemetry_handler import \
    record_user_action_details
import container_service_extension.utils as utils
import container_service_extension.vsphere_utils as vs_utils


class VcdBroker(AbstractBroker):
    """Handles cluster operations for 'native' k8s provider."""

    def __init__(self, tenant_auth_token, is_jwt_token):
        self.tenant_client = None
        self.client_session = None
        self.tenant_user_name = None
        self.tenant_user_id = None
        self.tenant_org_name = None
        self.tenant_org_href = None
        # populates above attributes
        super().__init__(tenant_auth_token, is_jwt_token)

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
        defaults = {
            RequestKey.ORG_NAME: None,
            RequestKey.OVDC_NAME: None
        }
        validated_data = {**defaults, **data}
        req_utils.validate_payload(validated_data, required)

        cluster_name = validated_data[RequestKey.CLUSTER_NAME]
        cluster = get_cluster(self.tenant_client, cluster_name,
                              org_name=validated_data[RequestKey.ORG_NAME],
                              ovdc_name=validated_data[RequestKey.OVDC_NAME])

        # Record the telemetry data
        cse_params = copy.deepcopy(validated_data)
        cse_params[PayloadKey.CLUSTER_ID] = cluster[PayloadKey.CLUSTER_ID]
        record_user_action_details(cse_operation=CseOperation.CLUSTER_INFO,
                                   cse_params=cse_params)

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

        # Record the data for telemetry
        record_user_action_details(cse_operation=CseOperation.CLUSTER_LIST,
                                   cse_params=copy.deepcopy(validated_data))

        # "raw clusters" do not have well-defined cluster data keys
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
                'k8s_version': c.get('kubernetes_version'),
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
        defaults = {
            RequestKey.ORG_NAME: None,
            RequestKey.OVDC_NAME: None
        }
        validated_data = {**defaults, **data}
        req_utils.validate_payload(validated_data, required)

        cluster_name = validated_data[RequestKey.CLUSTER_NAME]
        cluster = get_cluster(self.tenant_client, cluster_name,
                              org_name=validated_data[RequestKey.ORG_NAME],
                              ovdc_name=validated_data[RequestKey.OVDC_NAME])
        vapp = VApp(self.tenant_client, href=cluster['vapp_href'])
        node_names = get_node_names(vapp, NodeType.MASTER)

        all_results = []

        # Record the telemetry data
        cse_params = copy.deepcopy(validated_data)
        cse_params[PayloadKey.CLUSTER_ID] = cluster[PayloadKey.CLUSTER_ID]
        record_user_action_details(cse_operation=CseOperation.CLUSTER_CONFIG,
                                   cse_params=cse_params)

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

    def get_cluster_upgrade_plan(self, data):
        """Get the template names/revisions that the cluster can upgrade to.

        Required data: cluster_name
        Optional data and default values: org_name=None, ovdc_name=None

        :return: A list of dictionaries with keys defined in LocalTemplateKey

        :rtype: List[Dict]
        """
        required = [
            RequestKey.CLUSTER_NAME
        ]
        defaults = {
            RequestKey.ORG_NAME: None,
            RequestKey.OVDC_NAME: None
        }
        validated_data = {**defaults, **data}
        req_utils.validate_payload(validated_data, required)

        cluster = get_cluster(self.tenant_client,
                              validated_data[RequestKey.CLUSTER_NAME],
                              org_name=validated_data[RequestKey.ORG_NAME],
                              ovdc_name=validated_data[RequestKey.OVDC_NAME])

        # Record the telemetry data
        cse_params = copy.deepcopy(validated_data)
        cse_params[PayloadKey.CLUSTER_ID] = cluster[PayloadKey.CLUSTER_ID]
        record_user_action_details(cse_operation=CseOperation.CLUSTER_UPGRADE_PLAN, cse_params=cse_params)  # noqa: E501

        src_name = cluster['template_name']
        src_rev = cluster['template_revision']

        upgrades = []
        config = utils.get_server_runtime_config()
        for t in config['broker']['templates']:
            if src_name in t[LocalTemplateKey.UPGRADE_FROM]:
                if t[LocalTemplateKey.NAME] == src_name and int(t[LocalTemplateKey.REVISION]) <= int(src_rev): # noqa: E501
                    continue
                upgrades.append(t)

        return upgrades

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
            mb_memory=None, storage_profile_name=None, ssh_key=None,
            template_name=default, template_revision=default, enable_nfs=False,
            rollback=True
        """
        required = [
            RequestKey.CLUSTER_NAME,
            RequestKey.ORG_NAME,
            RequestKey.OVDC_NAME,
            RequestKey.NETWORK_NAME
        ]
        cluster_name = data[RequestKey.CLUSTER_NAME]
        # check that cluster name is syntactically valid
        if not is_valid_cluster_name(cluster_name):
            raise CseServerError(f"Invalid cluster name '{cluster_name}'")
        # check that cluster name doesn't already exist
        try:
            get_cluster(self.tenant_client, cluster_name,
                        org_name=data[RequestKey.ORG_NAME],
                        ovdc_name=data[RequestKey.OVDC_NAME])
            raise ClusterAlreadyExistsError(f"Cluster '{cluster_name}' "
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
            RequestKey.SSH_KEY: None,
            RequestKey.TEMPLATE_NAME: template[LocalTemplateKey.NAME],
            RequestKey.TEMPLATE_REVISION: template[LocalTemplateKey.REVISION],
            RequestKey.ENABLE_NFS: False,
            RequestKey.ROLLBACK: True,
        }
        validated_data = {**defaults, **data}
        req_utils.validate_payload(validated_data, required)
        template_name = validated_data[RequestKey.TEMPLATE_NAME]
        template_revision = validated_data[RequestKey.TEMPLATE_REVISION]
        num_workers = validated_data[RequestKey.NUM_WORKERS]

        # check that requested number of worker nodes is at least more than 1
        if num_workers < 0:
            raise CseServerError(f"Worker node count must be >= 0 "
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
            ssh_key=validated_data[RequestKey.SSH_KEY],
            enable_nfs=validated_data[RequestKey.ENABLE_NFS],
            rollback=validated_data[RequestKey.ROLLBACK])

        # Record the data for telemetry
        cse_params = copy.deepcopy(validated_data)
        cse_params[PayloadKey.CLUSTER_ID] = cluster_id
        cse_params[LocalTemplateKey.MEMORY] = template.get(LocalTemplateKey.MEMORY)  # noqa: E501
        cse_params[LocalTemplateKey.CPU] = template.get(LocalTemplateKey.CPU)
        cse_params[LocalTemplateKey.KUBERNETES] = template.get(LocalTemplateKey.KUBERNETES)  # noqa: E501
        cse_params[LocalTemplateKey.KUBERNETES_VERSION] = template.get(LocalTemplateKey.KUBERNETES_VERSION)  # noqa: E501
        cse_params[LocalTemplateKey.OS] = template.get(LocalTemplateKey.OS)
        cse_params[LocalTemplateKey.CNI] = template.get(LocalTemplateKey.CNI)
        cse_params[LocalTemplateKey.CNI_VERSION] = template.get(LocalTemplateKey.CNI_VERSION)  # noqa: E501
        record_user_action_details(cse_operation=CseOperation.CLUSTER_CREATE,
                                   cse_params=cse_params)

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
        # default data values are taken care of in self.create_nodes()
        validated_data = data
        req_utils.validate_payload(validated_data, required)

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

        # Record the telemetry data
        cse_params = copy.deepcopy(validated_data)
        cse_params[PayloadKey.CLUSTER_ID] = cluster_info[PayloadKey.CLUSTER_ID]
        record_user_action_details(cse_operation=CseOperation.CLUSTER_RESIZE,
                                   cse_params=cse_params)

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
        defaults = {
            RequestKey.ORG_NAME: None,
            RequestKey.OVDC_NAME: None
        }
        validated_data = {**defaults, **data}
        req_utils.validate_payload(validated_data, required)

        cluster_name = validated_data[RequestKey.CLUSTER_NAME]

        cluster = get_cluster(self.tenant_client, cluster_name,
                              org_name=validated_data[RequestKey.ORG_NAME],
                              ovdc_name=validated_data[RequestKey.OVDC_NAME])
        cluster_id = cluster['cluster_id']

        # Record the telemetry data
        cse_params = copy.deepcopy(validated_data)
        cse_params[PayloadKey.CLUSTER_ID] = cluster_id
        record_user_action_details(cse_operation=CseOperation.CLUSTER_DELETE,
                                   cse_params=cse_params)

        # must _update_task here or else self.task_resource is None
        # do not logout of sys admin, or else in pyvcloud's session.request()
        # call, session becomes None
        self._update_task(
            TaskStatus.RUNNING,
            message=f"Deleting cluster '{cluster_name}' ({cluster_id})")
        self._delete_cluster_async(cluster_name=cluster_name,
                                   cluster_vdc_href=cluster['vdc_href'])

        return {
            'cluster_name': cluster_name,
            'task_href': self.task_resource.get('href')
        }

    @secure(required_rights=[CSE_NATIVE_DEPLOY_RIGHT_NAME])
    def upgrade_cluster(self, data):
        """Start the upgrade cluster operation.

        Validates data for 'upgrade cluster' operation.
        Upgrading cluster is an asynchronous task, so the returned
        `result['task_href']` can be polled to get updates on task progress.

        Required data: cluster_name, template_name, template_revision
        Optional data and default values: org_name=None, ovdc_name=None
        """
        required = [
            RequestKey.CLUSTER_NAME,
            RequestKey.TEMPLATE_NAME,
            RequestKey.TEMPLATE_REVISION
        ]
        defaults = {
            RequestKey.ORG_NAME: None,
            RequestKey.OVDC_NAME: None
        }
        validated_data = {**defaults, **data}
        req_utils.validate_payload(validated_data, required)

        cluster_name = validated_data[RequestKey.CLUSTER_NAME]
        template_name = validated_data[RequestKey.TEMPLATE_NAME]
        template_revision = validated_data[RequestKey.TEMPLATE_REVISION]

        # check that the specified template is a valid upgrade target
        template = {}
        valid_templates = self.get_cluster_upgrade_plan(validated_data)
        for t in valid_templates:
            if t[LocalTemplateKey.NAME] == template_name and t[LocalTemplateKey.REVISION] == str(template_revision): # noqa: E501
                template = t
                break
        if not template:
            # TODO all of these CseServerError instances related to request
            # should be changed to BadRequestError (400)
            raise CseServerError(
                f"Specified template/revision ({template_name} revision "
                f"{template_revision}) is not a valid upgrade target for "
                f"cluster '{cluster_name}'.")

        # get cluster data (including node names) to pass to async function
        cluster = self.get_cluster_info(validated_data)

        # Record the telemetry data
        cse_params = copy.deepcopy(validated_data)
        cse_params[PayloadKey.CLUSTER_ID] = cluster[PayloadKey.CLUSTER_ID]
        record_user_action_details(cse_operation=CseOperation.CLUSTER_UPGRADE,
                                   cse_params=cse_params)

        msg = f"Upgrading cluster '{cluster_name}' " \
              f"software to match template {template_name} (revision " \
              f"{template_revision}): Kubernetes: " \
              f"{cluster['kubernetes_version']} -> " \
              f"{template[LocalTemplateKey.KUBERNETES_VERSION]}, Docker-CE: " \
              f"{cluster['docker_version']} -> " \
              f"{template[LocalTemplateKey.DOCKER_VERSION]}, CNI: " \
              f"{cluster['cni']} {cluster['cni_version']} -> " \
              f"{template[LocalTemplateKey.CNI_VERSION]}"
        self._update_task(TaskStatus.RUNNING, message=msg)
        LOGGER.info(f"{msg} ({cluster['vapp_href']})")
        self._upgrade_cluster_async(cluster=cluster, template=template)

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
        defaults = {
            RequestKey.ORG_NAME: None,
            RequestKey.OVDC_NAME: None
        }
        validated_data = {**defaults, **data}
        req_utils.validate_payload(validated_data, required)

        cluster_name = validated_data[RequestKey.CLUSTER_NAME]
        node_name = validated_data[RequestKey.NODE_NAME]

        cluster = get_cluster(self.tenant_client, cluster_name,
                              org_name=validated_data[RequestKey.ORG_NAME],
                              ovdc_name=validated_data[RequestKey.OVDC_NAME])

        # Record the telemetry data
        cse_params = copy.deepcopy(validated_data)
        cse_params[PayloadKey.CLUSTER_ID] = cluster[PayloadKey.CLUSTER_ID]
        record_user_action_details(cse_operation=CseOperation.NODE_INFO, cse_params=cse_params)  # noqa: E501

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
                node_info['exports'] = get_nfs_exports(node_info['ipAddress'], vapp, vm_name) # noqa: E501
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
            mb_memory=None, storage_profile_name=None, ssh_key=None,
            template_name=default, template_revision=default, enable_nfs=False,
            rollback=True
        """
        required = [
            RequestKey.CLUSTER_NAME,
            RequestKey.NETWORK_NAME
        ]
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
            RequestKey.SSH_KEY: None,
            RequestKey.TEMPLATE_NAME: template[LocalTemplateKey.NAME],
            RequestKey.TEMPLATE_REVISION: template[LocalTemplateKey.REVISION],
            RequestKey.ENABLE_NFS: False,
            RequestKey.ROLLBACK: True,
        }
        validated_data = {**defaults, **data}
        req_utils.validate_payload(validated_data, required)

        cluster_name = validated_data[RequestKey.CLUSTER_NAME]
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

        # Record the data for telemetry
        cse_params = copy.deepcopy(validated_data)
        cse_params[PayloadKey.CLUSTER_ID] = cluster_id
        cse_params[LocalTemplateKey.MEMORY] = template.get(LocalTemplateKey.MEMORY)  # noqa: E501
        cse_params[LocalTemplateKey.CPU] = template.get(LocalTemplateKey.CPU)
        cse_params[LocalTemplateKey.KUBERNETES] = template.get(LocalTemplateKey.KUBERNETES)  # noqa: E501
        cse_params[LocalTemplateKey.KUBERNETES_VERSION] = template.get(LocalTemplateKey.KUBERNETES_VERSION)  # noqa: E501
        cse_params[LocalTemplateKey.OS] = template.get(LocalTemplateKey.OS)
        cse_params[LocalTemplateKey.CNI] = template.get(LocalTemplateKey.CNI)
        cse_params[LocalTemplateKey.CNI_VERSION] = template.get(LocalTemplateKey.CNI_VERSION)  # noqa: E501
        record_user_action_details(cse_operation=CseOperation.NODE_CREATE,
                                   cse_params=cse_params)

        # must _update_task here or else self.task_resource is None
        # do not logout of sys admin, or else in pyvcloud's session.request()
        # call, session becomes None
        self._update_task(
            TaskStatus.RUNNING,
            message=f"Creating {num_workers} node(s) from template "
                    f"'{template_name}' (revision {template_revision}) and "
                    f"adding to cluster '{cluster_name}' ({cluster_id})")
        self._create_nodes_async(
            cluster_name=cluster_name,
            cluster_vdc_href=cluster['vdc_href'],
            vapp_href=cluster['vapp_href'],
            cluster_id=cluster_id,
            template_name=template_name,
            template_revision=template_revision,
            num_workers=validated_data[RequestKey.NUM_WORKERS],
            network_name=validated_data[RequestKey.NETWORK_NAME],
            num_cpu=validated_data[RequestKey.NUM_CPU],
            mb_memory=validated_data[RequestKey.MB_MEMORY],
            storage_profile_name=validated_data[RequestKey.STORAGE_PROFILE_NAME], # noqa: E501
            ssh_key=validated_data[RequestKey.SSH_KEY],
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
        defaults = {
            RequestKey.ORG_NAME: None,
            RequestKey.OVDC_NAME: None
        }
        validated_data = {**defaults, **data}
        req_utils.validate_payload(validated_data, required)

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

        # Record the telemetry data; record separate data for each node
        cse_params = copy.deepcopy(validated_data)
        cse_params[PayloadKey.CLUSTER_ID] = cluster[PayloadKey.CLUSTER_ID]
        for node in node_names_list:
            cse_params[PayloadKey.NODE_NAME] = node
            record_user_action_details(cse_operation=CseOperation.NODE_DELETE, cse_params=cse_params)  # noqa: E501

        # must _update_task here or else self.task_resource is None
        # do not logout of sys admin, or else in pyvcloud's session.request()
        # call, session becomes None
        self._update_task(
            TaskStatus.RUNNING,
            message=f"Deleting {len(node_names_list)} node(s)"
                    f" from cluster '{cluster_name}'({cluster_id})")

        self._delete_nodes_async(
            cluster_name=cluster_name,
            vapp_href=cluster['vapp_href'],
            node_names_list=validated_data[RequestKey.NODE_NAMES_LIST])

        return {
            'cluster_name': cluster_name,
            'task_href': self.task_resource.get('href')
        }

    # all parameters following '*args' are required and keyword-only
    @utils.run_async
    def _create_cluster_async(self, *args,
                              org_name, ovdc_name, cluster_name, cluster_id,
                              template_name, template_revision, num_workers,
                              network_name, num_cpu, mb_memory,
                              storage_profile_name, ssh_key, enable_nfs,
                              rollback):
        org = vcd_utils.get_org(self.tenant_client, org_name=org_name)
        vdc = vcd_utils.get_vdc(
            self.tenant_client, vdc_name=ovdc_name, org=org)

        LOGGER.debug(f"About to create cluster '{cluster_name}' on {ovdc_name}"
                     f" with {num_workers} worker nodes, "
                     f"storage profile={storage_profile_name}")
        try:
            self._update_task(
                TaskStatus.RUNNING,
                message=f"Creating cluster vApp {cluster_name} ({cluster_id})")
            try:
                vapp_resource = \
                    vdc.create_vapp(cluster_name,
                                    description=f"cluster '{cluster_name}'",
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
                ClusterMetadataKey.TEMPLATE_REVISION: template[LocalTemplateKey.REVISION], # noqa: E501
                ClusterMetadataKey.OS: template[LocalTemplateKey.OS], # noqa: E501
                ClusterMetadataKey.DOCKER_VERSION: template[LocalTemplateKey.DOCKER_VERSION], # noqa: E501
                ClusterMetadataKey.KUBERNETES: template[LocalTemplateKey.KUBERNETES], # noqa: E501
                ClusterMetadataKey.KUBERNETES_VERSION: template[LocalTemplateKey.KUBERNETES_VERSION], # noqa: E501
                ClusterMetadataKey.CNI: template[LocalTemplateKey.CNI],
                ClusterMetadataKey.CNI_VERSION: template[LocalTemplateKey.CNI_VERSION] # noqa: E501
            }
            vapp = VApp(self.tenant_client, href=vapp_resource.get('href'))
            task = vapp.set_multiple_metadata(tags)
            self.tenant_client.get_task_monitor().wait_for_status(task)

            self._update_task(
                TaskStatus.RUNNING,
                message=f"Creating master node for "
                        f"cluster '{cluster_name}' ({cluster_id})")
            vapp.reload()
            server_config = utils.get_server_runtime_config()
            catalog_name = server_config['broker']['catalog']
            try:
                add_nodes(client=self.tenant_client,
                          num_nodes=1,
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
                          ssh_key=ssh_key)
            except Exception as e:
                raise MasterNodeCreationError("Error adding master node:",
                                              str(e))

            self._update_task(
                TaskStatus.RUNNING,
                message=f"Initializing cluster '{cluster_name}' "
                        f"({cluster_id})")
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
                        f"cluster '{cluster_name}' ({cluster_id})")
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
                          ssh_key=ssh_key)
            except Exception as e:
                raise WorkerNodeCreationError("Error creating worker node:",
                                              str(e))

            self._update_task(
                TaskStatus.RUNNING,
                message=f"Adding {num_workers} node(s) to "
                        f"cluster '{cluster_name}' ({cluster_id})")
            vapp.reload()
            join_cluster(vapp, template[LocalTemplateKey.NAME],
                         template[LocalTemplateKey.REVISION])

            if enable_nfs:
                self._update_task(
                    TaskStatus.RUNNING,
                    message=f"Creating NFS node for "
                            f"cluster '{cluster_name}' ({cluster_id})")
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
                              ssh_key=ssh_key)
                except Exception as e:
                    raise NFSNodeCreationError("Error creating NFS node:",
                                               str(e))

            self._update_task(
                TaskStatus.SUCCESS,
                message=f"Created cluster '{cluster_name}' ({cluster_id})")
        except (MasterNodeCreationError, WorkerNodeCreationError,
                NFSNodeCreationError, ClusterJoiningError,
                ClusterInitializationError, ClusterOperationError) as e:
            if rollback:
                msg = f"Error creating cluster '{cluster_name}'. " \
                      f"Deleting cluster (rollback=True)"
                self._update_task(TaskStatus.RUNNING, message=msg)
                LOGGER.info(msg)
                try:
                    cluster = get_cluster(self.tenant_client,
                                          cluster_name,
                                          cluster_id=cluster_id,
                                          org_name=org_name,
                                          ovdc_name=ovdc_name)
                    _delete_vapp(self.tenant_client, cluster['vdc_href'],
                                 cluster_name)
                except Exception:
                    LOGGER.error(f"Failed to delete cluster '{cluster_name}'",
                                 exc_info=True)
            LOGGER.error(f"Error creating cluster '{cluster_name}'",
                         exc_info=True)
            self._update_task(TaskStatus.ERROR, error_message=str(e))
            # raising an exception here prints a stacktrace to server console
        except Exception as e:
            LOGGER.error(f"Unknown error creating cluster '{cluster_name}'",
                         exc_info=True)
            self._update_task(TaskStatus.ERROR, error_message=str(e))
        finally:
            self.logout_sys_admin_client()

    # all parameters following '*args' are required and keyword-only
    @utils.run_async
    def _create_nodes_async(self, *args,
                            cluster_name, cluster_vdc_href, vapp_href,
                            cluster_id, template_name, template_revision,
                            num_workers, network_name, num_cpu, mb_memory,
                            storage_profile_name, ssh_key, enable_nfs,
                            rollback):
        org = vcd_utils.get_org(self.tenant_client)
        vdc = VDC(self.tenant_client, href=cluster_vdc_href)
        vapp = VApp(self.tenant_client, href=vapp_href)
        template = get_template(name=template_name, revision=template_revision)
        msg = f"Creating {num_workers} node(s) from template " \
              f"'{template_name}' (revision {template_revision}) and " \
              f"adding to cluster '{cluster_name}' ({cluster_id})"
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
                                  ssh_key=ssh_key)

            if node_type == NodeType.NFS:
                self._update_task(
                    TaskStatus.SUCCESS,
                    message=f"Created {num_workers} node(s) for "
                            f"cluster '{cluster_name}' ({cluster_id})")
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
                msg = f"Error adding nodes to cluster '{cluster_name}' " \
                      f"({cluster_id}). Deleting nodes: {e.node_names} " \
                      f"(rollback=True)"
                self._update_task(TaskStatus.RUNNING, message=msg)
                LOGGER.info(msg)
                try:
                    _delete_nodes(self.tenant_client, vapp_href, e.node_names,
                                  cluster_name=cluster_name)
                except Exception:
                    LOGGER.error(f"Failed to delete nodes {e.node_names} "
                                 f"from cluster '{cluster_name}'",
                                 exc_info=True)
            LOGGER.error(f"Error adding nodes to cluster '{cluster_name}'",
                         exc_info=True)
            LOGGER.error(str(e), exc_info=True)
            self._update_task(TaskStatus.ERROR, error_message=str(e))
            # raising an exception here prints a stacktrace to server console
        except Exception as e:
            LOGGER.error(str(e), exc_info=True)
            self._update_task(TaskStatus.ERROR, error_message=str(e))
        finally:
            self.logout_sys_admin_client()

    # all parameters following '*args' are required and keyword-only
    @utils.run_async
    def _delete_nodes_async(self, *args,
                            cluster_name, vapp_href, node_names_list):
        try:
            self._update_task(
                TaskStatus.RUNNING,
                message=f"Draining {len(node_names_list)} node(s) "
                        f"from cluster '{cluster_name}': {node_names_list}")

            # if nodes fail to drain, continue with node deletion anyways
            try:
                _drain_nodes(self.tenant_client, vapp_href, node_names_list,
                             cluster_name=cluster_name)
            except (NodeOperationError, ScriptExecutionError) as err:
                LOGGER.warning(f"Failed to drain nodes: {node_names_list} in "
                               f"cluster '{cluster_name}'. "
                               f"Continuing node delete...\nError: {err}")

            self._update_task(
                TaskStatus.RUNNING,
                message=f"Deleting {len(node_names_list)} node(s)"
                        f" from cluster '{cluster_name}': {node_names_list}")

            _delete_nodes(self.tenant_client, vapp_href, node_names_list,
                          cluster_name=cluster_name)

            self._update_task(
                TaskStatus.SUCCESS,
                message=f"Deleted {len(node_names_list)} node(s)"
                        f" to cluster '{cluster_name}'")
        except Exception as e:
            LOGGER.error(f"Unexpected error while deleting nodes "
                         f"{node_names_list}: {e}",
                         exc_info=True)
            self._update_task(TaskStatus.ERROR, error_message=str(e))
        finally:
            self.logout_sys_admin_client()

    # all parameters following '*args' are required and keyword-only
    @utils.run_async
    def _delete_cluster_async(self, *args, cluster_name, cluster_vdc_href):
        try:
            self._update_task(
                TaskStatus.RUNNING,
                message=f"Deleting cluster '{cluster_name}'")
            _delete_vapp(self.tenant_client, cluster_vdc_href, cluster_name)
            self._update_task(
                TaskStatus.SUCCESS,
                message=f"Deleted cluster '{cluster_name}'")
        except Exception as e:
            LOGGER.error(f"Unexpected error while deleting cluster: {e}",
                         exc_info=True)
            self._update_task(TaskStatus.ERROR, error_message=str(e))
        finally:
            self.logout_sys_admin_client()

    # all parameters following '*args' are required and keyword-only
    @utils.run_async
    def _upgrade_cluster_async(self, *args, cluster, template):
        try:
            cluster_name = cluster['name']
            master_node_names = [n['name'] for n in cluster['master_nodes']]
            worker_node_names = [n['name'] for n in cluster['nodes']]
            all_node_names = master_node_names + worker_node_names
            vapp_href = cluster['vapp_href']
            template_name = template[LocalTemplateKey.NAME]
            template_revision = template[LocalTemplateKey.REVISION]

            # semantic version doesn't allow leading zeros
            # docker's version format YY.MM.patch allows us to directly use
            # lexicographical string comparison
            c_docker = cluster['docker_version']
            t_docker = template[LocalTemplateKey.DOCKER_VERSION]
            c_k8s = semver.Version(cluster['kubernetes_version'])
            t_k8s = semver.Version(template[LocalTemplateKey.KUBERNETES_VERSION]) # noqa: E501
            c_cni = semver.Version(cluster['cni_version'])
            t_cni = semver.Version(template[LocalTemplateKey.CNI_VERSION])

            upgrade_docker = t_docker > c_docker
            upgrade_k8s = t_k8s > c_k8s
            upgrade_cni = t_cni > c_cni or t_k8s.major > c_k8s.major or t_k8s.minor > c_k8s.minor # noqa: E501

            if upgrade_k8s:
                self._update_task(
                    TaskStatus.RUNNING,
                    message=f"Draining master node {master_node_names}"
                )
                _drain_nodes(self.tenant_client, vapp_href,
                             master_node_names, cluster_name=cluster_name)

                self._update_task(
                    TaskStatus.RUNNING,
                    message=f"Upgrading Kubernetes ({c_k8s} -> {t_k8s}) "
                            f"in master node {master_node_names}"
                )
                filepath = ltm.get_script_filepath(template_name,
                                                   template_revision,
                                                   ScriptFile.MASTER_K8S_UPGRADE) # noqa: E501
                script = utils.read_data_file(filepath, logger=LOGGER)
                run_script_in_nodes(self.tenant_client, vapp_href,
                                    master_node_names, script)

                self._update_task(
                    TaskStatus.RUNNING,
                    message=f"Uncordoning master node {master_node_names}"
                )
                _uncordon_nodes(self.tenant_client, vapp_href,
                                master_node_names,
                                cluster_name=cluster_name)

                filepath = ltm.get_script_filepath(template_name,
                                                    template_revision,
                                                    ScriptFile.WORKER_K8S_UPGRADE) # noqa: E501
                script = utils.read_data_file(filepath, logger=LOGGER)
                for node in worker_node_names:
                    self._update_task(
                        TaskStatus.RUNNING,
                        message=f"Draining node {node}"
                    )
                    _drain_nodes(self.tenant_client, vapp_href, [node],
                                 cluster_name=cluster_name)

                    self._update_task(
                        TaskStatus.RUNNING,
                        message=f"Upgrading Kubernetes ({c_k8s} -> {t_k8s}) "
                                f"in node {node}"
                    )
                    run_script_in_nodes(self.tenant_client, vapp_href, [node],
                                        script)

                    self._update_task(
                        TaskStatus.RUNNING,
                        message=f"Uncordoning node {node}"
                    )
                    _uncordon_nodes(self.tenant_client, vapp_href, [node],
                                    cluster_name=cluster_name)

            if upgrade_docker or upgrade_cni:
                self._update_task(
                    TaskStatus.RUNNING,
                    message=f"Draining all nodes {all_node_names}"
                )
                _drain_nodes(self.tenant_client, vapp_href, all_node_names,
                             cluster_name=cluster_name)

            if upgrade_docker:
                self._update_task(
                    TaskStatus.RUNNING,
                    message=f"Upgrading Docker-CE ({c_docker} -> {t_docker}) "
                            f"in nodes {all_node_names}"
                )
                filepath = ltm.get_script_filepath(template_name,
                                                   template_revision,
                                                   ScriptFile.DOCKER_UPGRADE)
                script = utils.read_data_file(filepath, logger=LOGGER)
                run_script_in_nodes(self.tenant_client, vapp_href,
                                    all_node_names, script)

            if upgrade_cni:
                self._update_task(
                    TaskStatus.RUNNING,
                    message=f"Applying CNI ({cluster['cni']} {c_cni} -> "
                            f"{t_cni}) in master node {master_node_names}"
                )
                filepath = ltm.get_script_filepath(template_name,
                                                   template_revision,
                                                   ScriptFile.MASTER_CNI_APPLY)
                script = utils.read_data_file(filepath, logger=LOGGER)
                run_script_in_nodes(self.tenant_client, vapp_href,
                                    master_node_names, script)

            # uncordon all nodes (sometimes redundant)
            self._update_task(
                TaskStatus.RUNNING,
                message=f"Uncordoning all nodes {all_node_names}"
            )
            _uncordon_nodes(self.tenant_client, vapp_href, all_node_names,
                            cluster_name=cluster_name)

            # update cluster metadata
            self._update_task(
                TaskStatus.RUNNING,
                message=f"Updating metadata for cluster '{cluster_name}'"
            )
            metadata = {
                ClusterMetadataKey.TEMPLATE_NAME: template[LocalTemplateKey.NAME], # noqa: E501
                ClusterMetadataKey.TEMPLATE_REVISION: template[LocalTemplateKey.REVISION], # noqa: E501
                ClusterMetadataKey.DOCKER_VERSION: template[LocalTemplateKey.DOCKER_VERSION], # noqa: E501
                ClusterMetadataKey.KUBERNETES_VERSION: template[LocalTemplateKey.KUBERNETES_VERSION], # noqa: E501
                ClusterMetadataKey.CNI: template[LocalTemplateKey.CNI],
                ClusterMetadataKey.CNI_VERSION: template[LocalTemplateKey.CNI_VERSION] # noqa: E501
            }
            vapp = VApp(self.tenant_client, href=vapp_href)
            task = vapp.set_multiple_metadata(metadata)
            self.tenant_client.get_task_monitor().wait_for_status(task)

            msg = f"Successfully upgraded cluster '{cluster_name}' software " \
                  f"to match template {template_name} (revision " \
                  f"{template_revision}): Kubernetes: {c_k8s} -> {t_k8s}, " \
                  f"Docker-CE: {c_docker} -> {t_docker}, " \
                  f"CNI: {c_cni} -> {t_cni}"
            self._update_task(TaskStatus.SUCCESS, message=msg)
            LOGGER.info(f"{msg} ({vapp_href})")
        except Exception as e:
            msg = f"Unexpected error while upgrading cluster " \
                  f"'{cluster_name}': {e}"
            LOGGER.error(msg, exc_info=True)
            self._update_task(TaskStatus.ERROR, error_message=msg)
        finally:
            self.logout_sys_admin_client()

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


def _drain_nodes(client, vapp_href, node_names, cluster_name=''):
    LOGGER.debug(f"Draining nodes {node_names} in cluster '{cluster_name}' "
                 f"(vapp: {vapp_href})")
    script = f"#!/usr/bin/env bash\n"
    for node_name in node_names:
        script += f"kubectl drain {node_name} " \
                  f"--ignore-daemonsets --timeout=60s --delete-local-data\n"

    try:
        vapp = VApp(client, href=vapp_href)
        master_node_names = get_node_names(vapp, NodeType.MASTER)
        run_script_in_nodes(client, vapp_href, [master_node_names[0]], script)
    except Exception as e:
        LOGGER.warning(f"Failed to drain nodes {node_names} in cluster "
                       f"'{cluster_name}' (vapp: {vapp_href}) with error: {e}")
        raise

    LOGGER.debug(f"Successfully drained nodes {node_names} in cluster "
                 f"'{cluster_name}' (vapp: {vapp_href})")


def _uncordon_nodes(client, vapp_href, node_names, cluster_name=''):
    LOGGER.debug(f"Uncordoning nodes {node_names} in cluster '{cluster_name}' "
                 f"(vapp: {vapp_href})")
    script = f"#!/usr/bin/env bash\n"
    for node_name in node_names:
        script += f"kubectl uncordon {node_name}\n"

    try:
        vapp = VApp(client, href=vapp_href)
        master_node_names = get_node_names(vapp, NodeType.MASTER)
        run_script_in_nodes(client, vapp_href, [master_node_names[0]], script)
    except Exception as e:
        LOGGER.warning(f"Failed to uncordon nodes {node_names} in cluster "
                       f"'{cluster_name}' (vapp: {vapp_href}) with error: {e}")
        raise

    LOGGER.debug(f"Successfully uncordoned nodes {node_names} in cluster "
                 f"'{cluster_name}' (vapp: {vapp_href})")


def _delete_vapp(client, vdc_href, vapp_name):
    LOGGER.debug(f"Deleting vapp {vapp_name} (vdc: {vdc_href})")

    try:
        vdc = VDC(client, href=vdc_href)
        task = vdc.delete_vapp(vapp_name, force=True)
        client.get_task_monitor().wait_for_status(task)
    except Exception as e:
        LOGGER.warning(f"Failed to delete vapp {vapp_name} "
                       f"(vdc: {vdc_href}) with error: {e}")
        raise

    LOGGER.debug(f"Deleted vapp {vapp_name} (vdc: {vdc_href})")


def _delete_nodes(client, vapp_href, node_names, cluster_name=''):
    LOGGER.debug(f"Deleting node(s) {node_names} from cluster '{cluster_name}'"
                 f" (vapp: {vapp_href})")
    script = "#!/usr/bin/env bash\nkubectl delete node "
    for node_name in node_names:
        script += f' {node_name}'
    script += '\n'

    vapp = VApp(client, href=vapp_href)
    try:
        master_node_names = get_node_names(vapp, NodeType.MASTER)
        run_script_in_nodes(client, vapp_href, [master_node_names[0]], script)
    except Exception:
        LOGGER.warning(f"Failed to delete node(s) {node_names} from cluster "
                       f"'{cluster_name}' using kubectl (vapp: {vapp_href})")

    vapp = VApp(client, href=vapp_href)
    for vm_name in node_names:
        vm = VM(client, resource=vapp.get_vm(vm_name))
        try:
            task = vm.undeploy()
            client.get_task_monitor().wait_for_status(task)
        except Exception:
            LOGGER.warning(f"Failed to undeploy VM {vm_name} "
                           f"(vapp: {vapp_href})")

    task = vapp.delete_vms(node_names)
    client.get_task_monitor().wait_for_status(task)
    LOGGER.debug(f"Successfully deleted node(s) {node_names} from "
                 f"cluster '{cluster_name}' (vapp: {vapp_href})")


def get_nfs_exports(ip, vapp, vm_name):
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


def is_valid_cluster_name(name):
    """Validate that the cluster name against the pattern."""
    if len(name) > 25:
        return False
    if name[-1] == '.':
        name = name[:-1]
    allowed = re.compile(r"(?!-)[A-Z\d-]{1,63}(?<!-)$", re.IGNORECASE)
    return all(allowed.match(x) for x in name.split("."))


def get_all_clusters(client, cluster_name=None, cluster_id=None,
                     org_name=None, ovdc_name=None):
    """Get list of dictionaries containing data for each visible cluster.

    TODO define these cluster data dictionary keys better:
        'name', 'vapp_id', 'vapp_href', 'vdc_name', 'vdc_href', 'vdc_id',
        'leader_endpoint', 'master_nodes', 'nodes', 'nfs_nodes',
        'number_of_vms', 'template_name', 'template_revision',
        'cse_version', 'cluster_id', 'status', 'os', 'docker_version',
        'kubernetes', 'kubernetes_version', 'cni', 'cni_version'
    """
    query_filter = f'metadata:{ClusterMetadataKey.CLUSTER_ID}==STRING:*'
    if cluster_id is not None:
        query_filter = f'metadata:{ClusterMetadataKey.CLUSTER_ID}==STRING:{cluster_id}' # noqa: E501
    if cluster_name is not None:
        query_filter += f';name=={cluster_name}'
    if ovdc_name is not None:
        query_filter += f";vdcName=={ovdc_name}"
    resource_type = 'vApp'
    if client.is_sysadmin():
        resource_type = 'adminVApp'
        if org_name is not None and org_name.lower() != SYSTEM_ORG_NAME.lower(): # noqa: E501
            org_resource = client.get_org_by_name(org_name)
            org = Org(client, resource=org_resource)
            query_filter += f";org=={org.resource.get('id')}"

    # 2 queries are required because each query can only return 8 metadata
    q = client.get_typed_query(
        resource_type,
        query_result_format=QueryResultFormat.ID_RECORDS,
        qfilter=query_filter,
        fields=f'metadata:{ClusterMetadataKey.CLUSTER_ID}'
               f',metadata:{ClusterMetadataKey.MASTER_IP}'
               f',metadata:{ClusterMetadataKey.CSE_VERSION}'
               f',metadata:{ClusterMetadataKey.TEMPLATE_NAME}'
               f',metadata:{ClusterMetadataKey.TEMPLATE_REVISION}'
               f',metadata:{ClusterMetadataKey.BACKWARD_COMPATIBILE_TEMPLATE_NAME}' # noqa: E501
               f',metadata:{ClusterMetadataKey.OS}')
    q2 = client.get_typed_query(
        resource_type,
        query_result_format=QueryResultFormat.ID_RECORDS,
        qfilter=query_filter,
        fields=f'metadata:{ClusterMetadataKey.DOCKER_VERSION}'
               f',metadata:{ClusterMetadataKey.KUBERNETES}'
               f',metadata:{ClusterMetadataKey.KUBERNETES_VERSION}'
               f',metadata:{ClusterMetadataKey.CNI}'
               f',metadata:{ClusterMetadataKey.CNI_VERSION}')

    metadata_key_to_cluster_key = {
        ClusterMetadataKey.CLUSTER_ID: 'cluster_id',
        ClusterMetadataKey.CSE_VERSION: 'cse_version',
        ClusterMetadataKey.MASTER_IP: 'leader_endpoint',
        ClusterMetadataKey.TEMPLATE_NAME: 'template_name',
        ClusterMetadataKey.TEMPLATE_REVISION: 'template_revision',
        ClusterMetadataKey.OS: 'os',
        ClusterMetadataKey.DOCKER_VERSION: 'docker_version',
        ClusterMetadataKey.KUBERNETES: 'kubernetes',
        ClusterMetadataKey.KUBERNETES_VERSION: 'kubernetes_version',
        ClusterMetadataKey.CNI: 'cni',
        ClusterMetadataKey.CNI_VERSION: 'cni_version'
    }

    clusters = {}
    for record in q.execute():
        vapp_id = record.get('id').split(':')[-1]
        vdc_id = record.get('vdc').split(':')[-1]
        vapp_href = f'{client.get_api_uri()}/vApp/vapp-{vapp_id}'

        # TODO THIS CLUSTER DICTIONARY NEEDS TO BE MORE WELL-DEFINED
        clusters[vapp_id] = {
            'name': record.get('name'),
            'vapp_id': vapp_id,
            'vapp_href': vapp_href,
            'vdc_name': record.get('vdcName'),
            'vdc_href': f'{client.get_api_uri()}/vdc/{vdc_id}',
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
            'status': record.get('status'),
            'os': '',
            'docker_version': '',
            'kubernetes': '',
            'kubernetes_version': '',
            'cni': '',
            'cni_version': ''
        }

        if hasattr(record, 'Metadata'):
            for element in record.Metadata.MetadataEntry:
                if element.Key in metadata_key_to_cluster_key:
                    clusters[vapp_id][metadata_key_to_cluster_key[element.Key]] = str(element.TypedValue.Value) # noqa: E501
                # for pre-2.5.0 cluster backwards compatibility
                elif element.Key == ClusterMetadataKey.BACKWARD_COMPATIBILE_TEMPLATE_NAME and clusters[vapp_id]['template_name'] == '': # noqa: E501
                    clusters[vapp_id]['template_name'] = str(element.TypedValue.Value) # noqa: E501

        # pre-2.6 clusters may not have kubernetes version metadata
        if clusters[vapp_id]['kubernetes_version'] == '':
            clusters[vapp_id]['kubernetes_version'] = ltm.get_template_k8s_version(clusters[vapp_id]['template_name']) # noqa: E501

    # api query can fetch only 8 metadata at a time
    # since we have more than 8 metadata, we need to use 2 queries
    for record in q2.execute():
        vapp_id = record.get('id').split(':')[-1]
        if hasattr(record, 'Metadata'):
            for element in record.Metadata.MetadataEntry:
                if element.Key in metadata_key_to_cluster_key:
                    clusters[vapp_id][metadata_key_to_cluster_key[element.Key]] = str(element.TypedValue.Value) # noqa: E501
                # for pre-2.5.0 cluster backwards compatibility
                elif element.Key == ClusterMetadataKey.BACKWARD_COMPATIBILE_TEMPLATE_NAME and clusters[vapp_id]['template_name'] == '': # noqa: E501
                    clusters[vapp_id]['template_name'] = str(element.TypedValue.Value) # noqa: E501

    return list(clusters.values())


def get_cluster(client, cluster_name, cluster_id=None, org_name=None,
                ovdc_name=None):
    clusters = get_all_clusters(client, cluster_name=cluster_name,
                                cluster_id=cluster_id, org_name=org_name,
                                ovdc_name=ovdc_name)
    if len(clusters) > 1:
        raise CseDuplicateClusterError(f"Found multiple clusters named"
                                       f" '{cluster_name}'.")
    if len(clusters) == 0:
        raise ClusterNotFoundError(f"Cluster '{cluster_name}' not found.")

    return clusters[0]


def get_template(name=None, revision=None):
    if (name is None and revision is not None) or (name is not None and revision is None): # noqa: E501
        raise ValueError(f"If template revision is specified, then template "
                         f"name must also be specified (and vice versa).")
    server_config = utils.get_server_runtime_config()
    name = name or server_config['broker']['default_template_name']
    revision = revision or server_config['broker']['default_template_revision']
    for template in server_config['broker']['templates']:
        if template[LocalTemplateKey.NAME] == name and str(template[LocalTemplateKey.REVISION]) == str(revision): # noqa: E501
            return template
    raise Exception(f"Template '{name}' at revision {revision} not found.")


def add_nodes(client, num_nodes, node_type, org, vdc, vapp, catalog_name,
              template, network_name, num_cpu=None, memory_in_mb=None,
              storage_profile=None, ssh_key=None):
    specs = []
    try:
        if num_nodes < 1:
            return None

        # DEV NOTE: With api v33.0 and onwards, get_catalog operation will fail
        # for non admin users of an an org which is not hosting the catalog,
        # even if the catalog is explicitly shared with the org in question.
        # This happens because for api v 33.0 and onwards, the Org XML no
        # longer returns the href to catalogs accessible to the org, and typed
        # queries hide the catalog link from non admin users.
        # As a workaround, we will use a sys admin client to get the href and
        # pass it forward. Do note that the catalog itself can still be
        # accessed by these non admin users, just that they can't find by the
        # href on their own.

        sys_admin_client = None
        try:
            sys_admin_client = vcd_utils.get_sys_admin_client()
            org_name = org.get_name()
            org_resource = sys_admin_client.get_org_by_name(org_name)
            org_sa = Org(sys_admin_client, resource=org_resource)
            catalog_item = org_sa.get_catalog_item(
                catalog_name, template[LocalTemplateKey.CATALOG_ITEM_NAME])
            catalog_item_href = catalog_item.Entity.get('href')
        finally:
            if sys_admin_client:
                sys_admin_client.logout()

        source_vapp = VApp(client, href=catalog_item_href)
        source_vm = source_vapp.get_all_vms()[0].get('name')
        if storage_profile is not None:
            storage_profile = vdc.get_storage_profile(storage_profile)

        cust_script = None
        if ssh_key is not None:
            cust_script = \
                "#!/usr/bin/env bash\n" \
                "if [ x$1=x\"postcustomization\" ];\n" \
                "then\n" \
                "mkdir -p /root/.ssh\n" \
                f"echo '{ssh_key}' >> /root/.ssh/authorized_keys\n" \
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
                'password_auto': True,
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
                script_filepath = ltm.get_script_filepath(
                    template[LocalTemplateKey.NAME],
                    template[LocalTemplateKey.REVISION],
                    ScriptFile.NFSD)
                script = utils.read_data_file(script_filepath, logger=LOGGER)
                exec_results = execute_script_in_nodes(
                    vapp=vapp, node_names=[vm_name], script=script)
                errors = get_script_execution_errors(exec_results)
                if errors:
                    raise ScriptExecutionError(
                        f"VM customization script execution failed on node "
                        f"{vm_name}:{errors}")
    except Exception as e:
        # TODO: get details of the exception to determine cause of failure,
        # e.g. not enough resources available.
        node_list = [entry.get('target_vm_name') for entry in specs]
        raise NodeCreationError(node_list, str(e))

    vapp.reload()
    return {'task': task, 'specs': specs}


def get_node_names(vapp, node_type):
    return [vm.get('name') for vm in vapp.get_all_vms() if vm.get('name').startswith(node_type)] # noqa: E501


def _wait_for_tools_ready_callback(message, exception=None):
    LOGGER.debug(f"waiting for guest tools, status: {message}")
    if exception is not None:
        LOGGER.error(f"exception: {str(exception)}")


def _wait_for_guest_execution_callback(message, exception=None):
    LOGGER.debug(message)
    if exception is not None:
        LOGGER.error(f"exception: {str(exception)}")


def get_master_ip(vapp):
    LOGGER.debug(f"Getting master IP for vapp: "
                 f"{vapp.get_resource().get('name')}")
    script = "#!/usr/bin/env bash\n" \
             "ip route get 1 | awk '{print $NF;exit}'\n" \

    node_names = get_node_names(vapp, NodeType.MASTER)
    result = execute_script_in_nodes(vapp=vapp, node_names=node_names,
                                     script=script, check_tools=False)
    errors = get_script_execution_errors(result)
    if errors:
        raise ScriptExecutionError(
            f"Get master IP script execution failed on master node "
            f"{node_names}:{errors}")
    master_ip = result[0][1].content.decode().split()[0]
    LOGGER.debug(f"Retrieved master IP for vapp: "
                 f"{vapp.get_resource().get('name')}, ip: {master_ip}")
    return master_ip


def init_cluster(vapp, template_name, template_revision):
    try:
        script_filepath = ltm.get_script_filepath(template_name,
                                                  template_revision,
                                                  ScriptFile.MASTER)
        script = utils.read_data_file(script_filepath, logger=LOGGER)
        node_names = get_node_names(vapp, NodeType.MASTER)
        result = execute_script_in_nodes(vapp=vapp, node_names=node_names,
                                         script=script)
        errors = get_script_execution_errors(result)
        if errors:
            raise ScriptExecutionError(
                f"Initialize cluster script execution failed on node "
                f"{node_names}:{errors}")
        if result[0][0] != 0:
            raise ClusterInitializationError(f"Couldn't initialize cluster:\n{result[0][2].content.decode()}") # noqa: E501
    except Exception as e:
        LOGGER.error(e, exc_info=True)
        raise ClusterInitializationError(
            f"Couldn't initialize cluster: {str(e)}")


def join_cluster(vapp, template_name, template_revision, target_nodes=None):
    script = "#!/usr/bin/env bash\n" \
             "kubeadm token create\n" \
             "ip route get 1 | awk '{print $NF;exit}'\n"
    node_names = get_node_names(vapp, NodeType.MASTER)
    master_result = execute_script_in_nodes(vapp=vapp, node_names=node_names,
                                            script=script)
    errors = get_script_execution_errors(master_result)
    if errors:
        raise ScriptExecutionError(
            f"Join cluster script execution failed on master node "
            f"{node_names}:{errors}")
    init_info = master_result[0][1].content.decode().split()

    node_names = get_node_names(vapp, NodeType.WORKER)
    if target_nodes is not None:
        node_names = [name for name in node_names if name in target_nodes]
    tmp_script_filepath = ltm.get_script_filepath(template_name,
                                                  template_revision,
                                                  ScriptFile.NODE)
    tmp_script = utils.read_data_file(tmp_script_filepath, logger=LOGGER)
    script = tmp_script.format(token=init_info[0], ip=init_info[1])
    worker_results = execute_script_in_nodes(vapp=vapp, node_names=node_names,
                                             script=script)
    errors = get_script_execution_errors(worker_results)
    if errors:
        raise ScriptExecutionError(
            f"Join cluster script execution failed on worker node "
            f"{node_names}:{errors}")
    for result in worker_results:
        if result[0] != 0:
            raise ClusterJoiningError(f"Couldn't join cluster:"
                                      f"\n{result[2].content.decode()}")


def _wait_until_ready_to_exec(vs, vm, password, tries=30):
    ready = False
    script = "#!/usr/bin/env bash\n" \
             "uname -a\n"
    for _ in range(tries):
        result = vs.execute_script_in_guest(
            vm, 'root', password, script,
            target_file=None,
            wait_for_completion=True,
            wait_time=5,
            get_output=True,
            delete_script=True,
            callback=_wait_for_guest_execution_callback)
        if result[0] == 0:
            ready = True
            break
        LOGGER.info(f"Script returned {result[0]}; VM is not "
                    f"ready to execute scripts, yet")
        time.sleep(2)

    if not ready:
        raise CseServerError('VM is not ready to execute scripts')


def execute_script_in_nodes(vapp, node_names, script, check_tools=True,
                            wait=True):
    all_results = []
    sys_admin_client = None
    try:
        sys_admin_client = vcd_utils.get_sys_admin_client()
        for node_name in node_names:
            LOGGER.debug(f"will try to execute script on {node_name}:\n"
                         f"{script}")

            vs = vs_utils.get_vsphere(sys_admin_client, vapp,
                                      vm_name=node_name, logger=LOGGER)
            vs.connect()
            moid = vapp.get_vm_moid(node_name)
            vm = vs.get_vm_by_moid(moid)
            password = vapp.get_admin_password(node_name)
            if check_tools:
                LOGGER.debug(f"waiting for tools on {node_name}")
                vs.wait_until_tools_ready(
                    vm,
                    sleep=5,
                    callback=_wait_for_tools_ready_callback)
                _wait_until_ready_to_exec(vs, vm, password)
            LOGGER.debug(f"about to execute script on {node_name} "
                         f"(vm={vm}), wait={wait}")
            if wait:
                result = \
                    vs.execute_script_in_guest(
                        vm, 'root', password, script,
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
                    vs.execute_program_in_guest(vm,
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


def run_script_in_nodes(client, vapp_href, node_names, script):
    """Run script in all specified nodes.

    Wrapper around `execute_script_in_nodes()`. Use when we don't care about
    preserving script results

    :param pyvcloud.vcd.client.Client client:
    :param str vapp_href:
    :param List[str] node_names:
    :param str script:
    """
    # when is tools checking necessary?
    vapp = VApp(client, href=vapp_href)
    results = execute_script_in_nodes(vapp=vapp,
                                      node_names=node_names,
                                      script=script,
                                      check_tools=False)
    errors = get_script_execution_errors(results)
    if errors:
        raise ScriptExecutionError(f"Script execution failed on node "
                                   f"{node_names}\nErrors: {errors}")
    if results[0][0] != 0:
        raise NodeOperationError(f"Error during node operation:\n"
                                 f"{results[0][2].content.decode()}")


def get_script_execution_errors(results):
    return [result[2].content.decode() for result in results if result[0] != 0]

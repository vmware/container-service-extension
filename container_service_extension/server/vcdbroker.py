# container-service-extension
# Copyright (c) 2017 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

import copy
import random
import re
import string
import time
from typing import Dict, List, Optional, Union
import urllib
import uuid

import pkg_resources
import pyvcloud.vcd.client as vcd_client
import pyvcloud.vcd.org as vcd_org
import pyvcloud.vcd.task as vcd_task
import pyvcloud.vcd.vapp as vcd_vapp
from pyvcloud.vcd.vdc import VDC
import pyvcloud.vcd.vm as vcd_vm
import requests
import semantic_version as semver

from container_service_extension.common.constants.server_constants import ClusterMetadataKey  # noqa: E501
from container_service_extension.common.constants.server_constants import CSE_CLUSTER_KUBECONFIG_PATH  # noqa: E501
from container_service_extension.common.constants.server_constants import CSE_NATIVE_DEPLOY_RIGHT_NAME  # noqa: E501
from container_service_extension.common.constants.server_constants import K8S_PROVIDER_KEY  # noqa: E501
from container_service_extension.common.constants.server_constants import K8sProvider  # noqa: E501
from container_service_extension.common.constants.server_constants import KwargKey  # noqa: E501
from container_service_extension.common.constants.server_constants import LocalTemplateKey  # noqa: E501
from container_service_extension.common.constants.server_constants import NodeType  # noqa: E501
from container_service_extension.common.constants.server_constants import RemoteTemplateCookbookVersion  # noqa: E501
from container_service_extension.common.constants.server_constants import ScriptFile  # noqa: E501
from container_service_extension.common.constants.server_constants import ThreadLocalData  # noqa: E501
from container_service_extension.common.constants.shared_constants import \
    ClusterDetailsKey, SYSTEM_ORG_NAME
from container_service_extension.common.constants.shared_constants import CSE_PAGINATION_DEFAULT_PAGE_SIZE  # noqa: E501
from container_service_extension.common.constants.shared_constants import CSE_PAGINATION_FIRST_PAGE_NUMBER  # noqa: E501
from container_service_extension.common.constants.shared_constants import PaginationKey  # noqa: E501
from container_service_extension.common.constants.shared_constants import RequestKey  # noqa: E501
import container_service_extension.common.thread_local_data as thread_local_data  # noqa: E501
import container_service_extension.common.utils.core_utils as utils
import container_service_extension.common.utils.pyvcloud_utils as vcd_utils
import container_service_extension.common.utils.server_utils as server_utils
import container_service_extension.common.utils.thread_utils as thread_utils
import container_service_extension.common.utils.vsphere_utils as vs_utils
import container_service_extension.exception.exceptions as e
import container_service_extension.installer.templates.local_template_manager as ltm   # noqa: E501
from container_service_extension.lib.telemetry.constants import CseOperation
from container_service_extension.lib.telemetry.constants import PayloadKey
from container_service_extension.lib.telemetry.telemetry_handler import \
    record_user_action_details
from container_service_extension.logging.logger import SERVER_LOGGER as LOGGER
import container_service_extension.security.authorization as auth
import container_service_extension.security.context.operation_context as ctx
import container_service_extension.server.abstract_broker as abstract_broker
import container_service_extension.server.request_handlers.request_utils as req_utils  # noqa: E501

DEFAULT_API_VERSION = vcd_client.ApiVersion.VERSION_33.value


class VcdBroker(abstract_broker.AbstractBroker):
    """Handles cluster operations for 'native' k8s provider."""

    def __init__(self, op_ctx: ctx.OperationContext):
        self.context: Optional[ctx.OperationContext] = None
        # populates above attributes
        super().__init__(op_ctx)

        self.task = None
        self.task_resource = None

    def get_cluster_info(self, **kwargs):
        """Get cluster metadata as well as node data.

        Common broker function that validates data for the 'cluster info'
        operation and returns cluster/node metadata as dictionary.

        **data: Required
            Required data: cluster_name
            Optional data and default values: org_name=None, ovdc_name=None
        **telemetry: Optional
        """
        data = kwargs[KwargKey.DATA]
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
        client_v33 = self.context.get_client(api_version=DEFAULT_API_VERSION)
        cluster = _get_cluster(client_v33, cluster_name,
                               org_name=validated_data[RequestKey.ORG_NAME],
                               ovdc_name=validated_data[RequestKey.OVDC_NAME])

        if kwargs.get(KwargKey.TELEMETRY, True):
            # Record the telemetry data
            cse_params = copy.deepcopy(validated_data)
            cse_params[PayloadKey.CLUSTER_ID] = cluster[ClusterDetailsKey.CLUSTER_ID.value]  # noqa: E501
            cse_params[PayloadKey.SOURCE_DESCRIPTION] = thread_local_data.get_thread_local_data(ThreadLocalData.USER_AGENT)  # noqa: E501
            record_user_action_details(cse_operation=CseOperation.CLUSTER_INFO,
                                       cse_params=cse_params)

        cluster[K8S_PROVIDER_KEY] = K8sProvider.NATIVE
        _update_cluster_dict_with_node_info(client_v33, cluster)

        return cluster

    def get_clusters_by_page(self, **kwargs):
        """Get native clusters by page and their relevant metadata.

        :return: paginated dictionary containing list of clusters in
            that page as values.

        **data: Optional
            Optional data and default values: org_name=None, ovdc_name=None
        **telemetry: Optional
        """
        data = kwargs.get(KwargKey.DATA, {})
        page_number = kwargs.get('page_number',
                                 CSE_PAGINATION_FIRST_PAGE_NUMBER)
        page_size = kwargs.get('page_size',
                               CSE_PAGINATION_DEFAULT_PAGE_SIZE)

        defaults = {
            RequestKey.ORG_NAME: None,
            RequestKey.OVDC_NAME: None,
        }
        validated_data = {**defaults, **data}

        if kwargs.get(KwargKey.TELEMETRY, True):
            # Record the data for telemetry
            record_user_action_details(
                cse_operation=CseOperation.CLUSTER_LIST,
                cse_params=copy.deepcopy(validated_data))

        client_v33 = self.context.get_client(api_version=DEFAULT_API_VERSION)
        # "raw clusters" do not have well-defined cluster data keys
        raw_clusters_info = get_all_clusters(
            client_v33,
            org_name=validated_data[RequestKey.ORG_NAME],
            ovdc_name=validated_data[RequestKey.OVDC_NAME],
            page_number=page_number,
            page_size=page_size)

        sysadmin_client_v33 = \
            self.context.get_sysadmin_client(api_version=DEFAULT_API_VERSION)
        raw_clusters_info[PaginationKey.VALUES] = \
            _extract_cse_cluster_list_info(sysadmin_client_v33,
                                           raw_clusters_info[PaginationKey.VALUES])  # noqa: E501
        return raw_clusters_info

    def list_clusters(self, **kwargs):
        """List all native clusters and their relevant metadata.

        :return: a list of all clusters if 'page_number' or 'page_size' are
            not part of the kwargs. If 'page_number' or 'page_size' is present,
            a paginated response is returned.

        Common broker function that validates data for the 'list clusters'
        operation and returns a list of cluster data.

        **data: Optional
            Optional data and default values: org_name=None, ovdc_name=None
        **telemetry: Optional
        """
        data = kwargs.get(KwargKey.DATA, {})
        defaults = {
            RequestKey.ORG_NAME: None,
            RequestKey.OVDC_NAME: None
        }
        validated_data = {**defaults, **data}

        cse_params = copy.deepcopy(validated_data)
        cse_params[PayloadKey.SOURCE_DESCRIPTION] = thread_local_data.get_thread_local_data(ThreadLocalData.USER_AGENT)  # noqa: E501
        if kwargs.get(KwargKey.TELEMETRY, True):
            # Record the data for telemetry
            record_user_action_details(
                cse_operation=CseOperation.CLUSTER_LIST,
                cse_params=cse_params)

        client_v33 = self.context.get_client(api_version=DEFAULT_API_VERSION)
        # "raw clusters" do not have well-defined cluster data keys
        raw_clusters_info = get_all_clusters(
            client_v33,
            org_name=validated_data[RequestKey.ORG_NAME],
            ovdc_name=validated_data[RequestKey.OVDC_NAME])
        if isinstance(raw_clusters_info, list):
            raw_clusters = raw_clusters_info
        else:
            raw_clusters = raw_clusters_info[PaginationKey.VALUES]

        sysadmin_client_v33 = \
            self.context.get_sysadmin_client(api_version=DEFAULT_API_VERSION)
        return _extract_cse_cluster_list_info(sysadmin_client_v33,
                                              raw_clusters)

    def get_cluster_config(self, **kwargs):
        """Get the cluster's kube config contents.

        Common broker function that validates data for 'cluster config'
        operation and returns the cluster's kube config file contents
        as a string.

        **data: Required
            Required data: cluster_name
            Optional data and default values: org_name=None, ovdc_name=None
        **telemetry: Optional
        """
        data = kwargs[KwargKey.DATA]
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
        client_v33 = self.context.get_client(api_version=DEFAULT_API_VERSION)
        cluster = _get_cluster(client_v33, cluster_name,
                               org_name=validated_data[RequestKey.ORG_NAME],
                               ovdc_name=validated_data[RequestKey.OVDC_NAME])
        vapp = vcd_vapp.VApp(client_v33, href=cluster[ClusterDetailsKey.VAPP_HREF])  # noqa: E501
        node_names = _get_node_names(vapp, NodeType.CONTROL_PLANE)

        all_results = []

        if kwargs.get(KwargKey.TELEMETRY, True):
            # Record the telemetry data
            cse_params = copy.deepcopy(validated_data)
            cse_params[PayloadKey.SOURCE_DESCRIPTION] = thread_local_data.get_thread_local_data(ThreadLocalData.USER_AGENT)  # noqa: E501
            cse_params[PayloadKey.CLUSTER_ID] = cluster[ClusterDetailsKey.CLUSTER_ID.value]  # noqa: E501
            record_user_action_details(
                cse_operation=CseOperation.CLUSTER_CONFIG,
                cse_params=cse_params)

        for node_name in node_names:
            LOGGER.debug(f"getting file from node {node_name}")
            password = vapp.get_admin_password(node_name)
            sysadmin_client_v33 = self.context.get_sysadmin_client(
                api_version=DEFAULT_API_VERSION)
            vs = vs_utils.get_vsphere(sysadmin_client_v33, vapp,
                                      vm_name=node_name, logger=LOGGER)
            vs.connect()
            moid = vapp.get_vm_moid(node_name)
            vm = vs.get_vm_by_moid(moid)
            result = vs.download_file_from_guest(vm, 'root', password,
                                                 CSE_CLUSTER_KUBECONFIG_PATH)
            all_results.append(result)

        if len(all_results) == 0 or all_results[0].status_code != requests.codes.ok:  # noqa: E501
            raise e.ClusterOperationError("Couldn't get cluster configuration")
        return all_results[0].content.decode()

    def get_cluster_upgrade_plan(self, **kwargs):
        """Get the template names/revisions that the cluster can upgrade to.

        **data: Required
            Required data: cluster_name
            Optional data and default values: org_name=None, ovdc_name=None
        **telemetry: Optional

        :return: A list of dictionaries with keys defined in LocalTemplateKey

        :rtype: List[Dict]
        """
        data = kwargs[KwargKey.DATA]
        required = [
            RequestKey.CLUSTER_NAME
        ]
        defaults = {
            RequestKey.ORG_NAME: None,
            RequestKey.OVDC_NAME: None
        }
        validated_data = {**defaults, **data}
        req_utils.validate_payload(validated_data, required)

        client_v33 = self.context.get_client(api_version=DEFAULT_API_VERSION)
        cluster = _get_cluster(client_v33,
                               validated_data[RequestKey.CLUSTER_NAME],
                               org_name=validated_data[RequestKey.ORG_NAME],
                               ovdc_name=validated_data[RequestKey.OVDC_NAME])

        if kwargs.get(KwargKey.TELEMETRY, True):
            # Record the telemetry data
            cse_params = copy.deepcopy(validated_data)
            cse_params[PayloadKey.CLUSTER_ID] = cluster[ClusterDetailsKey.CLUSTER_ID.value]  # noqa: E501
            record_user_action_details(
                cse_operation=CseOperation.CLUSTER_UPGRADE_PLAN,
                cse_params=cse_params)

        src_name = cluster[ClusterDetailsKey.TEMPLATE_NAME]
        src_rev = cluster[ClusterDetailsKey.TEMPLATE_REVISION]

        upgrades = []
        config = server_utils.get_server_runtime_config()
        for t in config['broker']['templates']:
            if src_name in t[LocalTemplateKey.UPGRADE_FROM]:
                if t[LocalTemplateKey.NAME] == src_name and int(t[LocalTemplateKey.REVISION]) <= int(src_rev):  # noqa: E501
                    continue
                upgrades.append(t)

        return upgrades

    @auth.secure(required_rights=[CSE_NATIVE_DEPLOY_RIGHT_NAME])
    def create_cluster(self, **kwargs):
        """Start the cluster creation operation.

        Common broker function that validates data for the 'create cluster'
        operation and returns a dictionary with cluster detail and task
        information. Calls the asynchronous cluster create function that
        actually performs the work. The returned `result['task_href']` can
        be polled to get updates on task progress.

        **data: Required
            Required data: cluster_name, org_name, ovdc_name, network_name
            Optional data and default values: num_nodes=2, num_cpu=None,
                mb_memory=None, storage_profile_name=None, ssh_key=None,
                template_name=default, template_revision=default,
                enable_nfs=False,rollback=True
        **telemetry: Optional
        """
        data = kwargs[KwargKey.DATA]
        required = [
            RequestKey.CLUSTER_NAME,
            RequestKey.ORG_NAME,
            RequestKey.OVDC_NAME,
            RequestKey.NETWORK_NAME
        ]
        cluster_name = data[RequestKey.CLUSTER_NAME]
        # check that cluster name is syntactically valid
        if not _is_valid_cluster_name(cluster_name):
            raise e.CseServerError(f"Invalid cluster name '{cluster_name}'")
        # check that cluster name doesn't already exist
        client_v33 = self.context.get_client(api_version=DEFAULT_API_VERSION)
        try:
            _get_cluster(client_v33, cluster_name,
                         org_name=data[RequestKey.ORG_NAME],
                         ovdc_name=data[RequestKey.OVDC_NAME])
            raise e.ClusterAlreadyExistsError(
                f"Cluster '{cluster_name}' already exists.")
        except e.ClusterNotFoundError:
            pass
        # check that requested/default template is valid
        template = _get_template(
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

        # check that requested number of worker nodes is 0 or more
        if num_workers < 0:
            raise e.CseServerError(
                f"Worker node count must be >= 0 (received {num_workers}).")

        cluster_id = str(uuid.uuid4())

        # must _update_task or else self.task_resource is None
        # do not logout of sys admin, or else in pyvcloud's session.request()
        # call, session becomes None
        msg = f"Creating cluster vApp '{cluster_name}' ({cluster_id}) " \
              f"from template '{template_name}' (revision {template_revision})"
        LOGGER.debug(msg)
        self._update_task(vcd_client.TaskStatus.RUNNING, message=msg)
        self.context.is_async = True
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
            storage_profile_name=validated_data[RequestKey.STORAGE_PROFILE_NAME],  # noqa: E501
            ssh_key=validated_data[RequestKey.SSH_KEY],
            enable_nfs=validated_data[RequestKey.ENABLE_NFS],
            rollback=validated_data[RequestKey.ROLLBACK])

        if kwargs.get(KwargKey.TELEMETRY, True):
            # Record the data for telemetry
            cse_params = copy.deepcopy(validated_data)
            cse_params[PayloadKey.CLUSTER_ID] = cluster_id
            cse_params[LocalTemplateKey.MEMORY] = validated_data.get(RequestKey.MB_MEMORY)  # noqa: E501
            cse_params[LocalTemplateKey.CPU] = validated_data.get(RequestKey.NUM_CPU)  # noqa: E501
            cse_params[LocalTemplateKey.KUBERNETES] = template.get(LocalTemplateKey.KUBERNETES)  # noqa: E501
            cse_params[LocalTemplateKey.KUBERNETES_VERSION] = template.get(LocalTemplateKey.KUBERNETES_VERSION)  # noqa: E501
            cse_params[LocalTemplateKey.OS] = template.get(LocalTemplateKey.OS)
            cse_params[LocalTemplateKey.CNI] = template.get(LocalTemplateKey.CNI)  # noqa: E501
            cse_params[LocalTemplateKey.CNI_VERSION] = template.get(LocalTemplateKey.CNI_VERSION)  # noqa: E501
            cse_params[PayloadKey.SOURCE_DESCRIPTION] = thread_local_data.get_thread_local_data(ThreadLocalData.USER_AGENT)  # noqa: E501
            record_user_action_details(
                cse_operation=CseOperation.CLUSTER_CREATE,
                cse_params=cse_params)

        return {
            'name': cluster_name,
            'cluster_id': cluster_id,
            'task_href': self.task_resource.get('href')
        }

    @auth.secure(required_rights=[CSE_NATIVE_DEPLOY_RIGHT_NAME])
    def resize_cluster(self, **kwargs):
        """Start the resize cluster operation.

        Common broker function that validates data for the 'resize cluster'
        operation. Native clusters cannot be resized down. Creating nodes is an
        asynchronous task, so the returned `result['task_href']` can be polled
        to get updates on task progress.

        **data: Required
            Required data: cluster_name, network, num_nodes
            Optional data and default values: org_name=None, ovdc_name=None,
                rollback=True, template_name=None, template_revision=None
        **telemetry: Optional
        """
        data = kwargs[KwargKey.DATA]
        # TODO default template for resizing should be control_plane's template
        required = [
            RequestKey.CLUSTER_NAME,
            RequestKey.NUM_WORKERS,
            RequestKey.NETWORK_NAME
        ]
        defaults = {
            RequestKey.ORG_NAME: None,
            RequestKey.OVDC_NAME: None,
            RequestKey.NUM_WORKERS: None,
            RequestKey.NUM_CPU: None,
            RequestKey.MB_MEMORY: None,
            RequestKey.STORAGE_PROFILE_NAME: None,
            RequestKey.SSH_KEY: None,
            RequestKey.ENABLE_NFS: False,
            RequestKey.ROLLBACK: True,
        }
        validated_data: Dict[str, Union[Optional, str, int]] = {**defaults, **data}  # noqa: E501
        req_utils.validate_payload(validated_data, required)

        cluster_name = validated_data[RequestKey.CLUSTER_NAME]
        num_workers_wanted = validated_data[RequestKey.NUM_WORKERS]

        if num_workers_wanted is None or num_workers_wanted < 0:
            raise e.CseServerError(f"Worker node count must be >= 0 (received"
                                   f" {num_workers_wanted}).")

        # cluster_handler.py already makes a cluster info API call to vCD, but
        # that call does not return any node info, so this additional
        # cluster info call must be made
        cluster_info = self.get_cluster_info(data=validated_data,
                                             telemetry=False)
        num_workers = len(cluster_info['nodes'])
        if num_workers == num_workers_wanted:
            raise e.CseServerError(f"Cluster '{cluster_name}' already has "
                                   f"{num_workers} worker nodes.")

        if kwargs.get(KwargKey.TELEMETRY, True):
            # Record the telemetry data
            cse_params = copy.deepcopy(validated_data)
            cse_params[PayloadKey.CLUSTER_ID] = cluster_info[ClusterDetailsKey.CLUSTER_ID.value]  # noqa: E501
            cse_params[LocalTemplateKey.MEMORY] = validated_data.get(RequestKey.MB_MEMORY)  # noqa: E501
            cse_params[LocalTemplateKey.CPU] = validated_data.get(RequestKey.NUM_CPU)  # noqa: E501
            cse_params[PayloadKey.SOURCE_DESCRIPTION] = thread_local_data.get_thread_local_data(ThreadLocalData.USER_AGENT)  # noqa: E501
            record_user_action_details(
                cse_operation=CseOperation.CLUSTER_RESIZE,
                cse_params=cse_params)

        if num_workers_wanted > num_workers:
            validated_data[RequestKey.NUM_WORKERS] = num_workers_wanted - num_workers  # noqa: E501
            return self.create_nodes(data=validated_data, telemetry=False)
        else:
            num_workers_to_be_deleted = num_workers - num_workers_wanted
            node_list: List[Dict[str, str]] = cluster_info[ClusterDetailsKey.WORKER_NODE_LIST]  # noqa: E501
            validated_data[RequestKey.NODE_NAMES_LIST] = [node['name'] for node in node_list[0:num_workers_to_be_deleted]]  # noqa: E501
            return self.delete_nodes(data=validated_data, telemetry=False)

    @auth.secure(required_rights=[CSE_NATIVE_DEPLOY_RIGHT_NAME])
    def delete_cluster(self, **kwargs):
        """Start the delete cluster operation.

        Common broker function that validates data for 'delete cluster'
        operation. Deleting nodes is an asynchronous task, so the returned
        `result['task_href']` can be polled to get updates on task progress.

        **data: Required
            Required data: cluster_name
            Optional data and default values: org_name=None, ovdc_name=None
        **telemetry: Optional
        """
        data = kwargs[KwargKey.DATA]
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
        client_v33 = self.context.get_client(api_version=DEFAULT_API_VERSION)
        cluster = _get_cluster(client_v33, cluster_name,
                               org_name=validated_data[RequestKey.ORG_NAME],
                               ovdc_name=validated_data[RequestKey.OVDC_NAME])
        cluster_id = cluster[ClusterDetailsKey.CLUSTER_ID.value]

        if kwargs.get(KwargKey.TELEMETRY, True):
            # Record the telemetry data
            cse_params = copy.deepcopy(validated_data)
            cse_params[PayloadKey.CLUSTER_ID] = cluster_id
            cse_params[PayloadKey.SOURCE_DESCRIPTION] = thread_local_data.get_thread_local_data(ThreadLocalData.USER_AGENT)  # noqa: E501
            record_user_action_details(
                cse_operation=CseOperation.CLUSTER_DELETE,
                cse_params=cse_params)

        # must _update_task here or else self.task_resource is None
        # do not logout of sys admin, or else in pyvcloud's session.request()
        # call, session becomes None
        msg = f"Deleting cluster '{cluster_name}' ({cluster_id})"
        LOGGER.debug(msg)
        self._update_task(vcd_client.TaskStatus.RUNNING, message=msg)
        self.context.is_async = True
        self._delete_cluster_async(cluster_name=cluster_name,
                                   cluster_vdc_href=cluster[ClusterDetailsKey.VDC_HREF])  # noqa: E501

        return {
            'cluster_name': cluster_name,
            'task_href': self.task_resource.get('href')
        }

    @auth.secure(required_rights=[CSE_NATIVE_DEPLOY_RIGHT_NAME])
    def upgrade_cluster(self, **kwargs):
        """Start the upgrade cluster operation.

        Validates data for 'upgrade cluster' operation.
        Upgrading cluster is an asynchronous task, so the returned
        `result['task_href']` can be polled to get updates on task progress.

        **data: Required
            Required data: cluster_name, template_name, template_revision
            Optional data and default values: org_name=None, ovdc_name=None
        **telemetry: Optional
        """
        data = kwargs[KwargKey.DATA]
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
        valid_templates = self.get_cluster_upgrade_plan(data=validated_data,
                                                        telemetry=False)
        for t in valid_templates:
            if (t[LocalTemplateKey.NAME], str(t[LocalTemplateKey.REVISION])) == (template_name, str(template_revision)):  # noqa: E501
                template = t
                break
        if not template:
            # TODO all of these e.CseServerError instances related to request
            # should be changed to BadRequestError (400)
            raise e.CseServerError(
                f"Specified template/revision ({template_name} revision "
                f"{template_revision}) is not a valid upgrade target for "
                f"cluster '{cluster_name}'.")

        # get cluster data (including node names) to pass to async function
        cluster = self.get_cluster_info(data=validated_data, telemetry=False)

        if kwargs.get(KwargKey.TELEMETRY, True):
            # Record the telemetry data
            cse_params = copy.deepcopy(validated_data)
            cse_params[PayloadKey.CLUSTER_ID] = cluster[ClusterDetailsKey.CLUSTER_ID.value]  # noqa: E501
            cse_params[PayloadKey.SOURCE_DESCRIPTION] = thread_local_data.get_thread_local_data(ThreadLocalData.USER_AGENT)  # noqa: E501
            record_user_action_details(
                cse_operation=CseOperation.CLUSTER_UPGRADE,
                cse_params=cse_params)

        msg = f"Upgrading cluster '{cluster_name}' " \
              f"software to match template {template_name} (revision " \
              f"{template_revision}): Kubernetes: " \
              f"{cluster[ClusterDetailsKey.KUBERNETES_VERSION]} -> " \
              f"{template[LocalTemplateKey.KUBERNETES_VERSION]}, Docker-CE: " \
              f"{cluster[ClusterDetailsKey.DOCKER_VERSION]} -> " \
              f"{template[LocalTemplateKey.DOCKER_VERSION]}, CNI: " \
              f"{cluster[ClusterDetailsKey.CNI_NAME]} {cluster[ClusterDetailsKey.CNI_VERSION]} -> " \
              f"{template[LocalTemplateKey.CNI_VERSION]}"  # noqa: E501
        LOGGER.debug(msg)
        self._update_task(vcd_client.TaskStatus.RUNNING, message=msg)
        LOGGER.info(f"{msg} ({cluster[ClusterDetailsKey.VAPP_HREF]})")
        self.context.is_async = True
        self._upgrade_cluster_async(cluster=cluster, template=template)

        return {
            'cluster_name': cluster_name,
            'task_href': self.task_resource.get('href')
        }

    def get_node_info(self, **kwargs):
        """Get node metadata as dictionary.

        **data: Required
            Required data: cluster_name, node_name
            Optional data and default values: org_name=None, ovdc_name=None
        **telemetry: Optional
        """
        data = kwargs[KwargKey.DATA]
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

        client_v33 = self.context.get_client(api_version=DEFAULT_API_VERSION)
        cluster = _get_cluster(client_v33, cluster_name,
                               org_name=validated_data[RequestKey.ORG_NAME],
                               ovdc_name=validated_data[RequestKey.OVDC_NAME])

        if kwargs.get(KwargKey.TELEMETRY, True):
            # Record the telemetry data
            cse_params = copy.deepcopy(validated_data)
            cse_params[PayloadKey.CLUSTER_ID] = cluster[ClusterDetailsKey.CLUSTER_ID.value]  # noqa: E501
            cse_params[PayloadKey.SOURCE_DESCRIPTION] = thread_local_data.get_thread_local_data(ThreadLocalData.USER_AGENT)  # noqa: E501
            record_user_action_details(
                cse_operation=CseOperation.NODE_INFO,
                cse_params=cse_params)

        vapp = vcd_vapp.VApp(client_v33, href=cluster[ClusterDetailsKey.VAPP_HREF])  # noqa: E501
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
                'status': vcd_client.VCLOUD_STATUS_MAP.get(int(vm.get('status'))),  # noqa: E501
                'ipAddress': ''
            }
            if hasattr(vm, 'VmSpecSection'):
                node_info['numberOfCpus'] = vm.VmSpecSection.NumCpus.text
                node_info['memoryMB'] = vm.VmSpecSection.MemoryResourceMb.Configured.text  # noqa: E501
            try:
                node_info['ipAddress'] = vapp.get_primary_ip(vm_name)
            except Exception:
                LOGGER.debug(f"Unable to get ip address of node {vm_name}")
            if vm_name.startswith(NodeType.CONTROL_PLANE):
                node_info['node_type'] = 'control_plane'
            elif vm_name.startswith(NodeType.WORKER):
                node_info['node_type'] = 'worker'
            elif vm_name.startswith(NodeType.NFS):
                node_info['node_type'] = 'nfs'
                sysadmin_client_v33 = self.context.get_sysadmin_client(
                    api_version=DEFAULT_API_VERSION)
                node_info['exports'] = _get_nfs_exports(sysadmin_client_v33, node_info['ipAddress'], vapp, vm_name)  # noqa: E501
        if node_info is None:
            raise e.NodeNotFoundError(f"Node '{node_name}' not found in "
                                      f"cluster '{cluster_name}'")
        return node_info

    @auth.secure(required_rights=[CSE_NATIVE_DEPLOY_RIGHT_NAME])
    def create_nodes(self, **kwargs):
        """Start the create nodes operation.

        Validates data for 'node create' operation. Creating nodes is an
        asynchronous task, so the returned `result['task_href']` can be polled
        to get updates on task progress.

        **data: Required
            Required data: cluster_name, network_name
            Optional data and default values: num_nodes=2, num_cpu=None,
                mb_memory=None, storage_profile_name=None, ssh_key=None,
                template_name=default, template_revision=default,
                enable_nfs=False, rollback=True
        **telemetry: Optional
        """
        data = kwargs[KwargKey.DATA]
        required = [
            RequestKey.CLUSTER_NAME,
            RequestKey.NETWORK_NAME
        ]
        # check that requested/default template is valid
        template = _get_template(
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

        num_cpu = template.get(LocalTemplateKey.CPU)
        if validated_data[RequestKey.NUM_CPU]:
            num_cpu = validated_data[RequestKey.NUM_CPU]

        mb_memory = template.get(LocalTemplateKey.MEMORY)
        if validated_data[RequestKey.MB_MEMORY]:
            mb_memory = validated_data[RequestKey.MB_MEMORY]

        if num_workers < 1:
            raise e.CseServerError(f"Worker node count must be > 0 "
                                   f"(received {num_workers}).")

        client_v33 = self.context.get_client(api_version=DEFAULT_API_VERSION)
        cluster = _get_cluster(client_v33, cluster_name,
                               org_name=validated_data[RequestKey.ORG_NAME],
                               ovdc_name=validated_data[RequestKey.OVDC_NAME])
        cluster_id = cluster[ClusterDetailsKey.CLUSTER_ID.value]

        if kwargs.get(KwargKey.TELEMETRY, True):
            # Record the data for telemetry
            cse_params = copy.deepcopy(validated_data)
            cse_params[PayloadKey.CLUSTER_ID] = cluster_id
            cse_params[LocalTemplateKey.MEMORY] = validated_data.get(RequestKey.MB_MEMORY)  # noqa: E501
            cse_params[LocalTemplateKey.CPU] = validated_data.get(RequestKey.NUM_CPU)  # noqa: E501
            cse_params[LocalTemplateKey.KUBERNETES] = template.get(LocalTemplateKey.KUBERNETES)  # noqa: E501
            cse_params[LocalTemplateKey.KUBERNETES_VERSION] = template.get(LocalTemplateKey.KUBERNETES_VERSION)  # noqa: E501
            cse_params[LocalTemplateKey.OS] = template.get(LocalTemplateKey.OS)
            cse_params[LocalTemplateKey.CNI] = template.get(LocalTemplateKey.CNI)  # noqa: E501
            cse_params[LocalTemplateKey.CNI_VERSION] = template.get(LocalTemplateKey.CNI_VERSION)  # noqa: E501
            cse_params[PayloadKey.SOURCE_DESCRIPTION] = thread_local_data.get_thread_local_data(ThreadLocalData.USER_AGENT)  # noqa: E501
            record_user_action_details(cse_operation=CseOperation.NODE_CREATE,
                                       cse_params=cse_params)

        # must _update_task here or else self.task_resource is None
        # do not logout of sys admin, or else in pyvcloud's session.request()
        # call, session becomes None
        msg = f"Creating {num_workers} node(s) from template " \
              f"'{template_name}' (revision {template_revision}) and " \
              f"adding to cluster '{cluster_name}' ({cluster_id})"
        LOGGER.debug(msg)
        self._update_task(vcd_client.TaskStatus.RUNNING, message=msg)
        self.context.is_async = True
        self._create_nodes_async(
            cluster_name=cluster_name,
            cluster_vdc_href=cluster[ClusterDetailsKey.VDC_HREF],
            vapp_href=cluster[ClusterDetailsKey.VAPP_HREF],
            cluster_id=cluster_id,
            template_name=template_name,
            template_revision=template_revision,
            num_workers=validated_data[RequestKey.NUM_WORKERS],
            network_name=validated_data[RequestKey.NETWORK_NAME],
            num_cpu=num_cpu,
            mb_memory=mb_memory,
            storage_profile_name=validated_data[RequestKey.STORAGE_PROFILE_NAME],  # noqa: E501
            ssh_key=validated_data[RequestKey.SSH_KEY],
            enable_nfs=validated_data[RequestKey.ENABLE_NFS],
            rollback=validated_data[RequestKey.ROLLBACK])

        return {
            'cluster_name': cluster_name,
            'task_href': self.task_resource.get('href')
        }

    @auth.secure(required_rights=[CSE_NATIVE_DEPLOY_RIGHT_NAME])
    def delete_nodes(self, **kwargs):
        """Start the delete nodes operation.

        Validates data for the 'delete nodes' operation. Deleting nodes is an
        asynchronous task, so the returned `result['task_href']` can be polled
        to get updates on task progress.

        **data: Required
            Required data: cluster_name, node_names_list
            Optional data and default values: org_name=None, ovdc_name=None
        **telemetry: Optional
        """
        data = kwargs[KwargKey.DATA]
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
        # check that control plane node is not in specified nodes
        for node in node_names_list:
            if node.startswith(NodeType.CONTROL_PLANE):
                raise e.CseServerError(f"Can't delete control plane node: '{node}'.")  # noqa: E501

        client_v33 = self.context.get_client(api_version=DEFAULT_API_VERSION)
        cluster = _get_cluster(client_v33, cluster_name,
                               org_name=validated_data[RequestKey.ORG_NAME],
                               ovdc_name=validated_data[RequestKey.OVDC_NAME])
        cluster_id = cluster[ClusterDetailsKey.CLUSTER_ID.value]

        if kwargs.get(KwargKey.TELEMETRY, True):
            # Record the telemetry data; record separate data for each node
            cse_params = copy.deepcopy(validated_data)
            cse_params[PayloadKey.CLUSTER_ID] = cluster[ClusterDetailsKey.CLUSTER_ID.value]  # noqa: E501
            cse_params[PayloadKey.SOURCE_DESCRIPTION] = thread_local_data.get_thread_local_data(ThreadLocalData.USER_AGENT)  # noqa: E501
            for node in node_names_list:
                cse_params[PayloadKey.NODE_NAME] = node
                record_user_action_details(
                    cse_operation=CseOperation.NODE_DELETE,
                    cse_params=cse_params)

        # must _update_task here or else self.task_resource is None
        # do not logout of sys admin, or else in pyvcloud's session.request()
        # call, session becomes None
        msg = f"Deleting {len(node_names_list)} node(s) " \
              f"from cluster '{cluster_name}'({cluster_id})"
        LOGGER.debug(msg)
        self._update_task(vcd_client.TaskStatus.RUNNING, message=msg)
        self.context.is_async = True
        self._delete_nodes_async(
            cluster_name=cluster_name,
            vapp_href=cluster[ClusterDetailsKey.VAPP_HREF],
            node_names_list=validated_data[RequestKey.NODE_NAMES_LIST])

        return {
            'cluster_name': cluster_name,
            'task_href': self.task_resource.get('href')
        }

    # all parameters following '*args' are required and keyword-only
    @thread_utils.run_async
    def _create_cluster_async(self, *args,
                              org_name, ovdc_name, cluster_name, cluster_id,
                              template_name, template_revision, num_workers,
                              network_name, num_cpu, mb_memory,
                              storage_profile_name, ssh_key, enable_nfs,
                              rollback):
        client_v33 = self.context.get_client(api_version=DEFAULT_API_VERSION)
        try:
            org = vcd_utils.get_org(client_v33, org_name=org_name)
            vdc = vcd_utils.get_vdc(client_v33,
                                    vdc_name=ovdc_name,
                                    org=org)

            LOGGER.debug(f"About to create cluster '{cluster_name}' on "
                         f"{ovdc_name} with {num_workers} worker nodes, "
                         f"storage profile={storage_profile_name}")
            msg = f"Creating cluster vApp {cluster_name} ({cluster_id})"
            LOGGER.debug(msg)
            self._update_task(vcd_client.TaskStatus.RUNNING, message=msg)
            try:
                vapp_resource = vdc.create_vapp(
                    cluster_name,
                    description=f"cluster '{cluster_name}'",
                    network=network_name,
                    fence_mode='bridged')
            except Exception as err:
                msg = f"Error while creating vApp: {err}"
                LOGGER.debug(str(err))
                raise e.ClusterOperationError(msg)
            client_v33.get_task_monitor().wait_for_status(vapp_resource.Tasks.Task[0])  # noqa: E501

            template = _get_template(template_name, template_revision)

            LOGGER.debug(f"Setting metadata on cluster vApp '{cluster_name}'")
            tags = {
                ClusterMetadataKey.CLUSTER_ID: cluster_id,
                ClusterMetadataKey.CSE_VERSION: pkg_resources.require('container-service-extension')[0].version,  # noqa: E501
                ClusterMetadataKey.TEMPLATE_NAME: template[LocalTemplateKey.NAME],  # noqa: E501
                ClusterMetadataKey.TEMPLATE_REVISION: template[LocalTemplateKey.REVISION],  # noqa: E501
                ClusterMetadataKey.OS: template[LocalTemplateKey.OS],  # noqa: E501
                ClusterMetadataKey.DOCKER_VERSION: template[LocalTemplateKey.DOCKER_VERSION],  # noqa: E501
                ClusterMetadataKey.KUBERNETES: template[LocalTemplateKey.KUBERNETES],  # noqa: E501
                ClusterMetadataKey.KUBERNETES_VERSION: template[LocalTemplateKey.KUBERNETES_VERSION],  # noqa: E501
                ClusterMetadataKey.CNI: template[LocalTemplateKey.CNI],
                ClusterMetadataKey.CNI_VERSION: template[LocalTemplateKey.CNI_VERSION]  # noqa: E501
            }
            vapp = vcd_vapp.VApp(client_v33,
                                 href=vapp_resource.get('href'))
            task = vapp.set_multiple_metadata(tags)
            client_v33.get_task_monitor().wait_for_status(task)

            msg = f"Creating control plane node for cluster '{cluster_name}'" \
                  f" ({cluster_id})"
            LOGGER.debug(msg)
            self._update_task(vcd_client.TaskStatus.RUNNING, message=msg)
            vapp.reload()
            server_config = server_utils.get_server_runtime_config()
            catalog_name = server_config['broker']['catalog']
            try:
                _add_nodes(client_v33,
                           num_nodes=1,
                           node_type=NodeType.CONTROL_PLANE,
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
            except Exception as err:
                raise e.ControlPlaneNodeCreationError(
                    "Error adding control plane node:",
                    str(err))

            msg = f"Initializing cluster '{cluster_name}' ({cluster_id})"
            LOGGER.debug(msg)
            self._update_task(vcd_client.TaskStatus.RUNNING, message=msg)
            vapp.reload()
            sysadmin_client_v33 = self.context.get_sysadmin_client(
                api_version=DEFAULT_API_VERSION)
            _init_cluster(sysadmin_client_v33,
                          vapp,
                          template[LocalTemplateKey.NAME],
                          template[LocalTemplateKey.REVISION])
            control_plane_ip = _get_control_plane_ip(sysadmin_client_v33, vapp)  # noqa: E501
            task = vapp.set_metadata('GENERAL', 'READWRITE', 'cse.master.ip',
                                     control_plane_ip)
            client_v33.get_task_monitor().wait_for_status(task)

            msg = f"Creating {num_workers} node(s) for cluster " \
                  f"'{cluster_name}' ({cluster_id})"
            LOGGER.debug(msg)
            self._update_task(vcd_client.TaskStatus.RUNNING, message=msg)
            try:
                _add_nodes(client_v33,
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
            except Exception as err:
                raise e.WorkerNodeCreationError("Error creating worker node:",
                                                str(err))

            msg = f"Adding {num_workers} node(s) to cluster " \
                  f"'{cluster_name}' ({cluster_id})"
            LOGGER.debug(msg)
            self._update_task(vcd_client.TaskStatus.RUNNING, message=msg)
            vapp.reload()
            _join_cluster(sysadmin_client_v33,
                          vapp,
                          template[LocalTemplateKey.NAME],
                          template[LocalTemplateKey.REVISION])

            if enable_nfs:
                msg = f"Creating NFS node for cluster " \
                      f"'{cluster_name}' ({cluster_id})"
                LOGGER.debug(msg)
                self._update_task(vcd_client.TaskStatus.RUNNING, message=msg)
                try:
                    _add_nodes(client_v33,
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
                except Exception as err:
                    raise e.NFSNodeCreationError("Error creating NFS node:",
                                                 str(err))

            msg = f"Created cluster '{cluster_name}' ({cluster_id})"
            LOGGER.debug(msg)
            self._update_task(vcd_client.TaskStatus.SUCCESS, message=msg)
        except (e.ControlPlaneNodeCreationError, e.WorkerNodeCreationError,
                e.NFSNodeCreationError, e.ClusterJoiningError,
                e.ClusterInitializationError, e.ClusterOperationError) as err:
            if rollback:
                msg = f"Error creating cluster '{cluster_name}'. " \
                      f"Deleting cluster (rollback=True)"
                LOGGER.debug(msg)
                self._update_task(vcd_client.TaskStatus.RUNNING, message=msg)
                try:
                    cluster = _get_cluster(client_v33,
                                           cluster_name,
                                           cluster_id=cluster_id,
                                           org_name=org_name,
                                           ovdc_name=ovdc_name)
                    _delete_vapp(client_v33, cluster[ClusterDetailsKey.VDC_HREF],  # noqa: E501
                                 cluster_name)
                except Exception:
                    LOGGER.error(f"Failed to delete cluster '{cluster_name}'",
                                 exc_info=True)
            msg = f"Error creating cluster '{cluster_name}'"
            LOGGER.error(msg, exc_info=True)
            self._update_task(vcd_client.TaskStatus.ERROR,
                              message=msg,
                              error_message=str(err))
            # raising an exception here prints a stacktrace to server console
        except Exception as err:
            msg = "Unknown error occurred while creating " \
                  f"cluster '{cluster_name}'"
            LOGGER.error(msg, exc_info=True)
            self._update_task(vcd_client.TaskStatus.ERROR,
                              message=msg,
                              error_message=str(err))
        finally:
            self.context.end()

    # all parameters following '*args' are required and keyword-only
    @thread_utils.run_async
    def _create_nodes_async(self, *args,
                            cluster_name, cluster_vdc_href, vapp_href,
                            cluster_id, template_name, template_revision,
                            num_workers, network_name, num_cpu, mb_memory,
                            storage_profile_name, ssh_key, enable_nfs,
                            rollback):
        sysadmin_client_v33 = \
            self.context.get_sysadmin_client(api_version=DEFAULT_API_VERSION)
        try:
            client_v33 = self.context.get_client(
                api_version=DEFAULT_API_VERSION)
            org = vcd_utils.get_org(client_v33)
            vdc = VDC(client_v33, href=cluster_vdc_href)
            vapp = vcd_vapp.VApp(client_v33, href=vapp_href)
            template = _get_template(name=template_name,
                                     revision=template_revision)
            server_config = server_utils.get_server_runtime_config()
            catalog_name = server_config['broker']['catalog']

            node_type = NodeType.WORKER
            if enable_nfs:
                node_type = NodeType.NFS

            msg = f"Creating {num_workers} node(s) from template " \
                f"'{template_name}' (revision {template_revision}) and " \
                f"adding to cluster '{cluster_name}' ({cluster_id})"
            LOGGER.debug(msg)
            self._update_task(vcd_client.TaskStatus.RUNNING, message=msg)

            new_nodes = _add_nodes(client_v33,
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
                msg = f"Created {num_workers} node(s) for cluster " \
                      f"'{cluster_name}' ({cluster_id})"
                LOGGER.debug(msg)
                self._update_task(vcd_client.TaskStatus.SUCCESS, message=msg)
            elif node_type == NodeType.WORKER:
                msg = f"Adding {num_workers} node(s) to cluster " \
                      f"{cluster_name}({cluster_id})"
                LOGGER.debug(msg)
                self._update_task(vcd_client.TaskStatus.RUNNING, message=msg)
                target_nodes = []
                for spec in new_nodes['specs']:
                    target_nodes.append(spec['target_vm_name'])
                vapp.reload()

                _join_cluster(sysadmin_client_v33,
                              vapp,
                              template[LocalTemplateKey.NAME],
                              template[LocalTemplateKey.REVISION],
                              target_nodes)
                msg = f"Added {num_workers} node(s) to cluster " \
                      f"{cluster_name}({cluster_id})"
                LOGGER.debug(msg)
                self._update_task(vcd_client.TaskStatus.SUCCESS, message=msg)
        except e.NodeCreationError as err:
            if rollback:
                msg = f"Error adding nodes to cluster '{cluster_name}' " \
                      f"({cluster_id}). Deleting nodes: {err.node_names} " \
                      f"(rollback=True)"
                LOGGER.debug(msg)
                self._update_task(vcd_client.TaskStatus.RUNNING, message=msg)
                try:
                    _delete_nodes(sysadmin_client_v33,
                                  vapp_href,
                                  err.node_names,
                                  cluster_name=cluster_name)
                except Exception:
                    LOGGER.error(f"Failed to delete nodes {err.node_names} "
                                 f"from cluster '{cluster_name}'",
                                 exc_info=True)
            msg = f"Error adding nodes to cluster '{cluster_name}' ({cluster_id})"  # noqa: E501
            LOGGER.error(msg, exc_info=True)
            self._update_task(vcd_client.TaskStatus.ERROR,
                              message=msg,
                              error_message=str(err))
            # raising an exception here prints a stacktrace to server console
        except Exception as err:
            msg = "Unexpected error while adding nodes for " \
                  f"cluster {cluster_name}"
            LOGGER.error(msg, exc_info=True)
            self._update_task(vcd_client.TaskStatus.ERROR,
                              message=msg,
                              error_message=str(err))
        finally:
            self.context.end()

    # all parameters following '*args' are required and keyword-only
    @thread_utils.run_async
    def _delete_nodes_async(self, *args,
                            cluster_name, vapp_href, node_names_list):
        try:
            msg = f"Draining {len(node_names_list)} node(s) from cluster " \
                  f"'{cluster_name}': {node_names_list}"
            LOGGER.debug(msg)
            self._update_task(vcd_client.TaskStatus.RUNNING, message=msg)

            sysadmin_client_v33 = self.context.get_sysadmin_client(
                api_version=DEFAULT_API_VERSION)
            # if nodes fail to drain, continue with node deletion anyways
            try:
                _drain_nodes(sysadmin_client_v33,
                             vapp_href,
                             node_names_list,
                             cluster_name=cluster_name)
            except (e.NodeOperationError, e.ScriptExecutionError) as err:
                LOGGER.warning(f"Failed to drain nodes: {node_names_list} in "
                               f"cluster '{cluster_name}'. "
                               f"Continuing node delete...\nError: {err}")

            msg = f"Deleting {len(node_names_list)} node(s) from cluster " \
                  f"'{cluster_name}': {node_names_list}"
            LOGGER.debug(msg)
            self._update_task(vcd_client.TaskStatus.RUNNING, message=msg)

            _delete_nodes(sysadmin_client_v33,
                          vapp_href,
                          node_names_list,
                          cluster_name=cluster_name)

            msg = f"Deleted {len(node_names_list)} node(s)" \
                  f" to cluster '{cluster_name}'"
            LOGGER.debug(msg)
            self._update_task(vcd_client.TaskStatus.SUCCESS, message=msg)
        except Exception as err:
            msg = "Unexpected error while deleting nodes for " \
                  f"cluster {cluster_name}. nodes: {node_names_list}"
            LOGGER.error(msg, exc_info=True)
            self._update_task(vcd_client.TaskStatus.ERROR,
                              message=msg,
                              error_message=str(err))
        finally:
            self.context.end()

    # all parameters following '*args' are required and keyword-only
    @thread_utils.run_async
    def _delete_cluster_async(self, *args, cluster_name, cluster_vdc_href):
        try:
            msg = f"Deleting cluster '{cluster_name}'"
            LOGGER.debug(msg)
            self._update_task(vcd_client.TaskStatus.RUNNING, message=msg)
            client_v33 = self.context.get_client(
                api_version=DEFAULT_API_VERSION)
            _delete_vapp(client_v33, cluster_vdc_href, cluster_name)
            msg = f"Deleted cluster '{cluster_name}'"
            LOGGER.debug(msg)
            self._update_task(vcd_client.TaskStatus.SUCCESS, message=msg)
        except Exception as err:
            msg = f"Unexpected error while deleting cluster {cluster_name}"
            LOGGER.error(msg, exc_info=True)
            self._update_task(vcd_client.TaskStatus.ERROR,
                              message=msg,
                              error_message=str(err))
        finally:
            self.context.end()

    # all parameters following '*args' are required and keyword-only
    @thread_utils.run_async
    def _upgrade_cluster_async(self, *args, cluster, template):
        try:
            cluster_name = cluster[ClusterDetailsKey.CLUSTER_NAME]
            control_plane_node_names = [n['name'] for n in cluster[ClusterDetailsKey.CONTROL_PLANE_NODE_LIST]]  # noqa: E501
            worker_node_names = [n['name'] for n in cluster['nodes']]
            all_node_names = control_plane_node_names + worker_node_names
            vapp_href = cluster[ClusterDetailsKey.VAPP_HREF]
            template_name = template[LocalTemplateKey.NAME]
            template_revision = template[LocalTemplateKey.REVISION]

            # semantic version doesn't allow leading zeros
            # docker's version format YY.MM.patch allows us to directly use
            # lexicographical string comparison
            c_docker = cluster[ClusterDetailsKey.DOCKER_VERSION]
            t_docker = template[LocalTemplateKey.DOCKER_VERSION]
            c_k8s = semver.Version(cluster[ClusterDetailsKey.KUBERNETES_VERSION])  # noqa: E501
            t_k8s = semver.Version(template[LocalTemplateKey.KUBERNETES_VERSION])  # noqa: E501
            c_cni = semver.Version(cluster[ClusterDetailsKey.CNI_VERSION])
            t_cni = semver.Version(template[LocalTemplateKey.CNI_VERSION])

            upgrade_docker = t_docker > c_docker
            upgrade_k8s = t_k8s >= c_k8s
            upgrade_cni = t_cni > c_cni or t_k8s.major > c_k8s.major or t_k8s.minor > c_k8s.minor  # noqa: E501

            sysadmin_client_v33 = self.context.get_sysadmin_client(
                api_version=DEFAULT_API_VERSION)

            if upgrade_k8s:
                msg = f"Draining control plane node {control_plane_node_names}"
                LOGGER.debug(msg)
                self._update_task(vcd_client.TaskStatus.RUNNING, message=msg)
                _drain_nodes(sysadmin_client_v33, vapp_href,
                             control_plane_node_names, cluster_name=cluster_name)  # noqa: E501

                msg = f"Upgrading Kubernetes ({c_k8s} -> {t_k8s}) " \
                      f"in control plane node {control_plane_node_names}"
                LOGGER.debug(msg)
                self._update_task(vcd_client.TaskStatus.RUNNING, message=msg)
                filepath = ltm.get_script_filepath(
                    RemoteTemplateCookbookVersion.Version1.value,
                    template_name,
                    template_revision,
                    ScriptFile.CONTROL_PLANE_K8S_UPGRADE)
                script = utils.read_data_file(filepath, logger=LOGGER)
                _run_script_in_nodes(sysadmin_client_v33, vapp_href,
                                     control_plane_node_names, script)

                msg = f"Uncordoning control plane node {control_plane_node_names}"  # noqa: E501
                LOGGER.debug(msg)
                self._update_task(vcd_client.TaskStatus.RUNNING, message=msg)
                _uncordon_nodes(sysadmin_client_v33,
                                vapp_href,
                                control_plane_node_names,
                                cluster_name=cluster_name)

                filepath = ltm.get_script_filepath(
                    RemoteTemplateCookbookVersion.Version1.value,
                    template_name,
                    template_revision,
                    ScriptFile.WORKER_K8S_UPGRADE)
                script = utils.read_data_file(filepath, logger=LOGGER)
                for node in worker_node_names:
                    msg = f"Draining node {node}"
                    LOGGER.debug(msg)
                    self._update_task(vcd_client.TaskStatus.RUNNING,
                                      message=msg)
                    _drain_nodes(sysadmin_client_v33,
                                 vapp_href,
                                 [node],
                                 cluster_name=cluster_name)

                    msg = f"Upgrading Kubernetes ({c_k8s} " \
                          f"-> {t_k8s}) in node {node}"
                    LOGGER.debug(msg)
                    self._update_task(vcd_client.TaskStatus.RUNNING,
                                      message=msg)
                    _run_script_in_nodes(sysadmin_client_v33,
                                         vapp_href, [node], script)

                    msg = f"Uncordoning node {node}"
                    LOGGER.debug(msg)
                    self._update_task(vcd_client.TaskStatus.RUNNING,
                                      message=msg)
                    _uncordon_nodes(sysadmin_client_v33,
                                    vapp_href, [node],
                                    cluster_name=cluster_name)

            if upgrade_docker or upgrade_cni:
                msg = f"Draining all nodes {all_node_names}"
                LOGGER.debug(msg)
                self._update_task(vcd_client.TaskStatus.RUNNING, message=msg)
                _drain_nodes(sysadmin_client_v33,
                             vapp_href, all_node_names,
                             cluster_name=cluster_name)

            if upgrade_docker:
                msg = f"Upgrading Docker-CE ({c_docker} -> {t_docker}) " \
                      f"in nodes {all_node_names}"
                LOGGER.debug(msg)
                self._update_task(vcd_client.TaskStatus.RUNNING, message=msg)
                filepath = ltm.get_script_filepath(RemoteTemplateCookbookVersion.Version1.value,  # noqa: E501
                                                   template_name,
                                                   template_revision,
                                                   ScriptFile.DOCKER_UPGRADE)
                script = utils.read_data_file(filepath, logger=LOGGER)
                _run_script_in_nodes(sysadmin_client_v33, vapp_href,
                                     all_node_names, script)

            if upgrade_cni:
                msg = f"Applying CNI ({cluster[ClusterDetailsKey.CNI_NAME]} {c_cni} -> {t_cni}) " \
                      f"in control plane node {control_plane_node_names}"  # noqa: E501
                LOGGER.debug(msg)
                self._update_task(vcd_client.TaskStatus.RUNNING, message=msg)
                filepath = ltm.get_script_filepath(RemoteTemplateCookbookVersion.Version1.value,  # noqa: E501
                                                   template_name,
                                                   template_revision,
                                                   ScriptFile.CONTROL_PLANE_CNI_APPLY)  # noqa: E501
                script = utils.read_data_file(filepath, logger=LOGGER)
                _run_script_in_nodes(sysadmin_client_v33, vapp_href,
                                     control_plane_node_names, script)

            # uncordon all nodes (sometimes redundant)
            msg = f"Uncordoning all nodes {all_node_names}"
            LOGGER.debug(msg)
            self._update_task(vcd_client.TaskStatus.RUNNING, message=msg)
            _uncordon_nodes(sysadmin_client_v33, vapp_href,
                            all_node_names, cluster_name=cluster_name)

            # update cluster metadata
            msg = f"Updating metadata for cluster '{cluster_name}'"
            LOGGER.debug(msg)
            self._update_task(vcd_client.TaskStatus.RUNNING, message=msg)
            metadata = {
                ClusterMetadataKey.TEMPLATE_NAME: template[LocalTemplateKey.NAME],  # noqa: E501
                ClusterMetadataKey.TEMPLATE_REVISION: template[LocalTemplateKey.REVISION],  # noqa: E501
                ClusterMetadataKey.DOCKER_VERSION: template[LocalTemplateKey.DOCKER_VERSION],  # noqa: E501
                ClusterMetadataKey.KUBERNETES_VERSION: template[LocalTemplateKey.KUBERNETES_VERSION],  # noqa: E501
                ClusterMetadataKey.CNI: template[LocalTemplateKey.CNI],
                ClusterMetadataKey.CNI_VERSION: template[LocalTemplateKey.CNI_VERSION]  # noqa: E501
            }
            client_v33 = self.context.get_client(
                api_version=DEFAULT_API_VERSION)
            vapp = vcd_vapp.VApp(client_v33, href=vapp_href)
            task = vapp.set_multiple_metadata(metadata)
            client_v33.get_task_monitor().wait_for_status(task)

            msg = f"Successfully upgraded cluster '{cluster_name}' software " \
                  f"to match template {template_name} (revision " \
                  f"{template_revision}): Kubernetes: {c_k8s} -> {t_k8s}, " \
                  f"Docker-CE: {c_docker} -> {t_docker}, " \
                  f"CNI: {c_cni} -> {t_cni}"
            LOGGER.debug(f"{msg} ({vapp_href})")
            self._update_task(vcd_client.TaskStatus.SUCCESS, message=msg)
        except Exception as err:
            msg = f"Unexpected error while upgrading cluster {cluster.get(ClusterDetailsKey.CLUSTER_NAME)}"  # noqa: E501
            LOGGER.error(msg, exc_info=True)
            self._update_task(vcd_client.TaskStatus.ERROR,
                              message=msg,
                              error_message=str(err))
        finally:
            self.context.end()

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
        client_v33 = self.context.get_client(api_version=DEFAULT_API_VERSION)
        if not client_v33.is_sysadmin():
            stack_trace = ''

        if self.task is None:
            sysadmin_client_v33 = self.context.get_sysadmin_client(
                api_version=DEFAULT_API_VERSION)
            self.task = vcd_task.Task(sysadmin_client_v33)

        task_href = None
        if self.task_resource is not None:
            task_href = self.task_resource.get('href')

        org = vcd_utils.get_org(client_v33)
        user_href = org.get_user(self.context.user.name).get('href')

        self.task_resource = self.task.update(
            status=status.value,
            namespace='vcloud.cse',
            operation=message,
            operation_name='cluster operation',
            details='',
            progress=None,
            owner_href=self.context.user.org_href,
            owner_name=self.context.user.org_name,
            owner_type='application/vnd.vmware.vcloud.org+xml',
            user_href=user_href,
            user_name=self.context.user.name,
            org_href=self.context.user.org_href,
            task_href=task_href,
            error_message=error_message,
            stack_trace=stack_trace
        )


def _drain_nodes(sysadmin_client: vcd_client.Client, vapp_href, node_names,
                 cluster_name=''):
    LOGGER.debug(f"Draining nodes {node_names} in cluster '{cluster_name}' "
                 f"(vapp: {vapp_href})")
    script = "#!/usr/bin/env bash\n"
    for node_name in node_names:
        script += f"kubectl drain {node_name} " \
                  f"--ignore-daemonsets --timeout=60s --delete-local-data\n"

    try:
        vapp = vcd_vapp.VApp(sysadmin_client, href=vapp_href)
        control_plane_node_names = _get_node_names(vapp, NodeType.CONTROL_PLANE)  # noqa: E501
        _run_script_in_nodes(sysadmin_client,
                             vapp_href,
                             [control_plane_node_names[0]],
                             script)
    except Exception as err:
        LOGGER.warning(f"Failed to drain nodes {node_names} in cluster "
                       f"'{cluster_name}' (vapp: {vapp_href}) with "
                       f"error: {err}")
        raise

    LOGGER.debug(f"Successfully drained nodes {node_names} in cluster "
                 f"'{cluster_name}' (vapp: {vapp_href})")


def _uncordon_nodes(sysadmin_client: vcd_client.Client, vapp_href, node_names,
                    cluster_name=''):
    vcd_utils.raise_error_if_user_not_from_system_org(sysadmin_client)

    LOGGER.debug(f"Uncordoning nodes {node_names} in cluster '{cluster_name}' "
                 f"(vapp: {vapp_href})")
    script = "#!/usr/bin/env bash\n"
    for node_name in node_names:
        script += f"kubectl uncordon {node_name}\n"

    try:
        vapp = vcd_vapp.VApp(sysadmin_client, href=vapp_href)
        control_plane_node_names = _get_node_names(vapp, NodeType.CONTROL_PLANE)  # noqa: E501
        _run_script_in_nodes(sysadmin_client,
                             vapp_href,
                             [control_plane_node_names[0]],
                             script)
    except Exception as err:
        LOGGER.warning(f"Failed to uncordon nodes {node_names} in cluster "
                       f"'{cluster_name}' (vapp: {vapp_href}) "
                       f"with error: {err}")
        raise

    LOGGER.debug(f"Successfully uncordoned nodes {node_names} in cluster "
                 f"'{cluster_name}' (vapp: {vapp_href})")


def _delete_vapp(client, vdc_href, vapp_name):
    LOGGER.debug(f"Deleting vapp {vapp_name} (vdc: {vdc_href})")

    try:
        vdc = VDC(client, href=vdc_href)
        task = vdc.delete_vapp(vapp_name, force=True)
        client.get_task_monitor().wait_for_status(task)
    except Exception as err:
        LOGGER.warning(f"Failed to delete vapp {vapp_name} "
                       f"(vdc: {vdc_href}) with error: {err}")
        raise

    LOGGER.debug(f"Deleted vapp {vapp_name} (vdc: {vdc_href})")


def _delete_nodes(sysadmin_client: vcd_client.Client, vapp_href, node_names,
                  cluster_name=''):
    vcd_utils.raise_error_if_user_not_from_system_org(sysadmin_client)

    LOGGER.debug(f"Deleting node(s) {node_names} from cluster '{cluster_name}'"
                 f" (vapp: {vapp_href})")
    script = "#!/usr/bin/env bash\nkubectl delete node "
    are_there_workers_to_del = False
    for node_name in node_names:
        if node_name.startswith(NodeType.WORKER):
            script += f' {node_name}'
            are_there_workers_to_del = True
    script += '\n'

    vapp = vcd_vapp.VApp(sysadmin_client, href=vapp_href)
    try:
        if are_there_workers_to_del:
            control_plane_node_names = _get_node_names(vapp, NodeType.CONTROL_PLANE)  # noqa: E501
            _run_script_in_nodes(sysadmin_client, vapp_href,
                                 [control_plane_node_names[0]], script)
    except Exception as err:
        LOGGER.warning(f"Failed to delete node(s) {node_names} from "
                       f"cluster '{cluster_name}' using kubectl. "
                       f"(vapp: {vapp_href}): {err}")

    vapp = vcd_vapp.VApp(sysadmin_client, href=vapp_href)
    for vm_name in node_names:
        vm = vcd_vm.VM(sysadmin_client, resource=vapp.get_vm(vm_name))
        try:
            task = vm.undeploy()
            sysadmin_client.get_task_monitor().wait_for_status(task)
        except Exception:
            LOGGER.warning(f"Failed to undeploy VM {vm_name} "
                           f"(vapp: {vapp_href})")

    task = vapp.delete_vms(node_names)
    sysadmin_client.get_task_monitor().wait_for_status(task)
    LOGGER.debug(f"Successfully deleted node(s) {node_names} from "
                 f"cluster '{cluster_name}' (vapp: {vapp_href})")


def _get_nfs_exports(sysadmin_client: vcd_client.Client, ip, vapp, vm_name):
    """Get the exports from remote NFS server.

    :param pyvcloud.vcd.client.Client sysadmin_client:
    :param str ip: IP address of the NFS server
    :param pyvcloud.vcd.vapp.vcd_vapp.VApp vapp:
    :param str vm_name:

    :return: (List): List of exports
    """
    script = f"#!/usr/bin/env bash\nshowmount -e {ip}"
    result = _execute_script_in_nodes(sysadmin_client, vapp=vapp,
                                      node_names=[vm_name], script=script,
                                      check_tools=False)
    lines = result[0][1].content.decode().split('\n')
    exports = []
    for index in range(1, len(lines) - 1):
        export = lines[index].strip().split()[0]
        exports.append(export)
    return exports


def _is_valid_cluster_name(name):
    """Validate that the cluster name against the pattern."""
    if name and len(name) > 25:
        return False
    return re.match("^[a-zA-Z][A-Za-z0-9-]*$", name) is not None


def _update_cluster_dict_with_node_info(client, cluster):
    vapp = vcd_vapp.VApp(client, href=cluster['vapp_href'])
    vms = vapp.get_all_vms()
    for vm in vms:
        vm_name = vm.get('name')
        node_info = {
            'name': vm_name,
            'numberOfCpus': '',
            'memoryMB': '',
            'ipAddress': '',
            'exports': ''
        }

        if hasattr(vm, 'VmSpecSection'):
            node_info['numberOfCpus'] = vm.VmSpecSection.NumCpus.text
            node_info['memoryMB'] = vm.VmSpecSection.MemoryResourceMb.Configured.text  # noqa: E501

        try:
            node_info['ipAddress'] = vapp.get_primary_ip(vm_name)
        except Exception:
            LOGGER.debug(f"Unable to get ip address of node {vm_name}")

        if vm_name.startswith(NodeType.CONTROL_PLANE):
            cluster.get('master_nodes').append(node_info)
        elif vm_name.startswith(NodeType.WORKER):
            cluster.get('nodes').append(node_info)
        elif vm_name.startswith(NodeType.NFS):
            if client.is_sysadmin():
                node_info['exports'] = _get_nfs_exports(
                    client, node_info['ipAddress'], vapp, vm_name)
            cluster.get('nfs_nodes').append(node_info)


def get_all_clusters(client, cluster_name=None, cluster_id=None,
                     org_name=None, ovdc_name=None, fetch_details=False,
                     page_number=None, page_size=None):
    """Get list of dictionaries containing data for each visible cluster.

    :param vcd_client.Client client:
    :param str cluster_name: name of the cluster to search for
    :param str cluster_id: id of the cluster to search for
    :param str org_name: restrict the cluster search to a specific org with
        name org_name
    :param str ovdc_name: restrict the cluster search to a specific ovdc with
        name ovdc_name
    :param bool fetch_details: If set, will fetch additional information about
        each individual cluster e.g. network_name, org_name, org_href, list of
        control_plane/worker/nfs nodes and their ips.
    :param int page_number: return clusters in a specific page number
    :param int page_size: return page_size results
    :return: list of clusters if page_number is not specified. Else, a dict
        containing cluster list and pagination information

    NOTE: if page_number is provided, the return type will be a dictionary
        containing pagination information along with the cluster list
    TODO define these cluster data dictionary keys better:
        'name', 'vapp_id', 'vapp_href', 'vdc_name', 'vdc_href', 'vdc_id',
        'leader_endpoint', 'master_nodes', 'nodes', 'nfs_nodes',
        'number_of_vms', 'template_name', 'template_revision',
        'cse_version', 'cluster_id', 'status', 'os', 'docker_version',
        'kubernetes', 'kubernetes_version', 'cni', 'cni_version'
    """
    query_filter = f'metadata:{ClusterMetadataKey.CLUSTER_ID}==STRING:*'
    if cluster_id is not None:
        query_filter = f'metadata:{ClusterMetadataKey.CLUSTER_ID}==STRING:{urllib.parse.quote(cluster_id)}'  # noqa: E501
    if cluster_name is not None:
        query_filter += f';name=={urllib.parse.quote(cluster_name)}'
    if ovdc_name is not None:
        query_filter += f";vdcName=={urllib.parse.quote(ovdc_name)}"
    resource_type = vcd_client.ResourceType.VAPP.value
    if client.is_sysadmin():
        resource_type = vcd_client.ResourceType.ADMIN_VAPP.value
        if org_name is not None and org_name.lower() != SYSTEM_ORG_NAME.lower():  # noqa: E501
            org_resource = client.get_org_by_name(org_name)
            org = vcd_org.Org(client, resource=org_resource)
            query_filter += f";org=={urllib.parse.quote(org.resource.get('id'))}"  # noqa: E501

    # 2 queries are required because each query can only return 8 metadata
    q = client.get_typed_query(
        resource_type,
        query_result_format=vcd_client.QueryResultFormat.ID_RECORDS,
        qfilter=query_filter,
        fields=f'metadata:{ClusterMetadataKey.CLUSTER_ID}'
               f',metadata:{ClusterMetadataKey.CONTROL_PLANE_IP}'
               f',metadata:{ClusterMetadataKey.CSE_VERSION}'
               f',metadata:{ClusterMetadataKey.TEMPLATE_NAME}'
               f',metadata:{ClusterMetadataKey.TEMPLATE_REVISION}'
               f',metadata:{ClusterMetadataKey.OS}',
        page=page_number,
        page_size=page_size)
    q2 = client.get_typed_query(
        resource_type,
        query_result_format=vcd_client.QueryResultFormat.ID_RECORDS,
        qfilter=query_filter,
        fields=f'metadata:{ClusterMetadataKey.DOCKER_VERSION}'
               f',metadata:{ClusterMetadataKey.KUBERNETES}'
               f',metadata:{ClusterMetadataKey.KUBERNETES_VERSION}'
               f',metadata:{ClusterMetadataKey.CNI}'
               f',metadata:{ClusterMetadataKey.CNI_VERSION}',
        page=page_number,
        page_size=page_size)

    metadata_key_to_cluster_key = {
        ClusterMetadataKey.CLUSTER_ID: 'cluster_id',
        ClusterMetadataKey.CSE_VERSION: 'cse_version',
        ClusterMetadataKey.CONTROL_PLANE_IP: 'leader_endpoint',
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
    result_total = None
    if page_number:
        # since page_number is provided during query creation, the return type
        # from pyvcloud will be a dict containing pagination information
        clusters_info = q.execute()
        cluster_list = clusters_info['values']
        result_total = int(clusters_info.get('resultTotal'))
    else:
        cluster_list = q.execute()
    for record in cluster_list:
        vapp_id = record.get('id').split(':')[-1]
        vdc_id = record.get('vdc').split(':')[-1]
        vapp_href = f'{client.get_api_uri()}/vApp/vapp-{vapp_id}'

        clusters[vapp_id] = {
            ClusterDetailsKey.CLUSTER_ID: '',
            ClusterDetailsKey.CNI_NAME: '',
            ClusterDetailsKey.CNI_VERSION: '',
            ClusterDetailsKey.CSE_VERSION: '',
            ClusterDetailsKey.DOCKER_VERSION: '',
            ClusterDetailsKey.KUBERNETES_RUNTIME: '',
            ClusterDetailsKey.KUBERNETES_VERSION: '',
            ClusterDetailsKey.LEADER_ENDPOINT: '',
            ClusterDetailsKey.CONTROL_PLANE_NODE_LIST: [],
            ClusterDetailsKey.CLUSTER_NAME: record.get('name'),
            ClusterDetailsKey.NETWORK_NAME: '',
            ClusterDetailsKey.NFS_NODE_LIST: [],
            ClusterDetailsKey.WORKER_NODE_LIST: [],
            ClusterDetailsKey.VM_COUNT: record.get('numberOfVMs'),
            ClusterDetailsKey.ORG_NAME: '',
            ClusterDetailsKey.ORG_HREF: '',
            ClusterDetailsKey.OS: '',
            ClusterDetailsKey.OWNER_NAME: record.get('ownerName'),
            ClusterDetailsKey.STATUS: record.get('status'),
            ClusterDetailsKey.STORAGE_PROFILE_NAME: '',
            ClusterDetailsKey.TEMPLATE_NAME: '',
            ClusterDetailsKey.TEMPLATE_REVISION: '',
            ClusterDetailsKey.VAPP_HREF: vapp_href,
            ClusterDetailsKey.VAPP_ID: vapp_id,
            ClusterDetailsKey.VDC_HREF: f'{client.get_api_uri()}/vdc/{vdc_id}',
            ClusterDetailsKey.VDC_ID: vdc_id,
            ClusterDetailsKey.VDC_NAME: record.get('vdcName')
        }

        if hasattr(record, 'Metadata'):
            for element in record.Metadata.MetadataEntry:
                if element.Key in metadata_key_to_cluster_key:
                    clusters[vapp_id][metadata_key_to_cluster_key[element.Key]] = str(element.TypedValue.Value)  # noqa: E501

    if page_number:
        # since page_number is provided during query creation, the return type
        # from pyvcloud will be a dict containing pagination information
        clusters_info = q2.execute()
        cluster_list = clusters_info['values']
        result_total = int(clusters_info.get('resultTotal'))
    else:
        cluster_list = q2.execute()
    # api query can fetch only 8 metadata at a time
    # since we have more than 8 metadata, we need to use 2 queries
    for record in cluster_list:
        vapp_id = record.get('id').split(':')[-1]
        if hasattr(record, 'Metadata'):
            for element in record.Metadata.MetadataEntry:
                if element.Key in metadata_key_to_cluster_key:
                    clusters[vapp_id][metadata_key_to_cluster_key[element.Key]] = str(element.TypedValue.Value)  # noqa: E501

    if fetch_details:
        for cluster in clusters.values():
            vapp = vcd_vapp.VApp(client, href=cluster[ClusterDetailsKey.VAPP_HREF])  # noqa: E501
            cluster[ClusterDetailsKey.NETWORK_NAME] = \
                vcd_utils.get_parent_network_name_of_vapp(vapp)
            cluster[ClusterDetailsKey.STORAGE_PROFILE_NAME] = \
                vcd_utils.get_storage_profile_name_of_first_vm_in_vapp(vapp)
            _update_cluster_dict_with_node_info(client, cluster)
            if client.is_sysadmin():
                cluster[ClusterDetailsKey.ORG_NAME] = \
                    vcd_utils.get_org_name_from_ovdc_id(client, cluster[ClusterDetailsKey.VDC_ID])  # noqa: E501
                cluster[ClusterDetailsKey.ORG_HREF] = \
                    vcd_utils.get_org_href_from_ovdc_id(client, cluster[ClusterDetailsKey.VDC_ID])  # noqa: E501

    if page_number:
        # return pagination details as well
        return {
            PaginationKey.VALUES: list(clusters.values()),
            PaginationKey.RESULT_TOTAL: result_total
        }

    return list(clusters.values())


def _get_cluster(client, cluster_name, cluster_id=None, org_name=None,
                 ovdc_name=None):
    clusters = get_all_clusters(client, cluster_name=cluster_name,
                                cluster_id=cluster_id, org_name=org_name,
                                ovdc_name=ovdc_name)
    if len(clusters) > 1:
        raise e.CseDuplicateClusterError(f"Found multiple clusters named"
                                         f" '{cluster_name}'.")
    if len(clusters) == 0:
        raise e.ClusterNotFoundError(f"Cluster '{cluster_name}' not found.")

    return clusters[0]


def _get_template(name=None, revision=None):
    if (name is None and revision is not None) or (name is not None and revision is None):  # noqa: E501
        raise ValueError("If template revision is specified, then template "
                         "name must also be specified (and vice versa).")
    server_config = server_utils.get_server_runtime_config()
    name = name or server_config['broker']['default_template_name']
    revision = revision or server_config['broker']['default_template_revision']
    for template in server_config['broker']['templates']:
        if (template[LocalTemplateKey.NAME], str(template[LocalTemplateKey.REVISION])) == (name, str(revision)):  # noqa: E501
            return template
    raise Exception(f"Template '{name}' at revision {revision} not found.")


def _add_nodes(client, num_nodes, node_type, org, vdc, vapp,
               catalog_name, template, network_name, num_cpu=None,
               memory_in_mb=None, storage_profile=None, ssh_key=None):
    if num_nodes > 0:
        specs = []
        try:
            org_name = org.get_name()
            org_resource = client.get_org_by_name(org_name)
            org_sa = vcd_org.Org(client, resource=org_resource)
            catalog_item = org_sa.get_catalog_item(
                catalog_name, template[LocalTemplateKey.CATALOG_ITEM_NAME])
            catalog_item_href = catalog_item.Entity.get('href')

            source_vapp = vcd_vapp.VApp(
                client, href=catalog_item_href)
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

            vapp.reload()
            for n in range(num_nodes):
                while True:
                    name = f"{node_type}-{''.join(random.choices(string.ascii_lowercase + string.digits, k=4))}"  # noqa: E501
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
                vm = vcd_vm.VM(client, resource=vm_resource)

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
                        RemoteTemplateCookbookVersion.Version1.value,
                        template[LocalTemplateKey.NAME],
                        template[LocalTemplateKey.REVISION],
                        ScriptFile.NFSD)
                    script = utils.read_data_file(
                        script_filepath, logger=LOGGER)
                    exec_results = _execute_script_in_nodes(
                        client, vapp=vapp, node_names=[vm_name],
                        script=script)
                    errors = _get_script_execution_errors(exec_results)
                    if errors:
                        raise e.ScriptExecutionError(
                            "NFSD script execution failed on node "
                            f"{vm_name}:{errors}")
        except Exception as err:
            # TODO: get details of the exception to determine cause of failure,
            # e.g. not enough resources available.
            node_list = [entry.get('target_vm_name') for entry in specs]
            raise e.NodeCreationError(node_list, str(err))

        vapp.reload()
        return {'task': task, 'specs': specs}


def _extract_cse_cluster_list_info(sysadmin_client: vcd_client.Client,
                                   raw_clusters: list) -> list:
    clusters = []
    for c in raw_clusters:
        org_name = vcd_utils.get_org_name_from_ovdc_id(sysadmin_client,
                                                       c['vdc_id'])
        clusters.append({
            'name': c[ClusterDetailsKey.CLUSTER_NAME],
            'control_plane_ip': c[ClusterDetailsKey.LEADER_ENDPOINT],
            'template_name': c.get(ClusterDetailsKey.TEMPLATE_NAME),
            'template_revision': c.get(ClusterDetailsKey.TEMPLATE_REVISION),
            'k8s_type': c.get(ClusterDetailsKey.KUBERNETES_RUNTIME),
            'k8s_version': c.get(ClusterDetailsKey.KUBERNETES_VERSION),
            'VMs': c[ClusterDetailsKey.VM_COUNT],
            'vdc': c[ClusterDetailsKey.VDC_NAME],
            'status': c[ClusterDetailsKey.STATUS],
            'vdc_id': c[ClusterDetailsKey.VDC_ID],
            'org_name': org_name,
            'owner_name': c[ClusterDetailsKey.OWNER_NAME],
            K8S_PROVIDER_KEY: K8sProvider.NATIVE
        })
    return clusters


def _get_node_names(vapp, node_type):
    return [vm.get('name') for vm in vapp.get_all_vms() if vm.get('name').startswith(node_type)]  # noqa: E501


def _wait_for_tools_ready_callback(message, exception=None):
    LOGGER.debug(f"waiting for guest tools, status: {message}")
    if exception is not None:
        LOGGER.error(f"exception: {str(exception)}")


def _wait_for_guest_execution_callback(message, exception=None):
    LOGGER.debug(message)
    if exception is not None:
        LOGGER.error(f"exception: {str(exception)}")


def _get_control_plane_ip(sysadmin_client: vcd_client.Client, vapp):
    vcd_utils.raise_error_if_user_not_from_system_org(sysadmin_client)

    LOGGER.debug(f"Getting control plane IP for vapp: "
                 f"{vapp.get_resource().get('name')}")
    script = "#!/usr/bin/env bash\n" \
             "ip route get 1 | awk '{print $NF;exit}'\n" \

    node_names = _get_node_names(vapp, NodeType.CONTROL_PLANE)
    result = _execute_script_in_nodes(sysadmin_client, vapp=vapp,
                                      node_names=node_names, script=script,
                                      check_tools=False)
    errors = _get_script_execution_errors(result)
    if errors:
        raise e.ScriptExecutionError(f"Get control plane IP script execution "
                                     f"failed on control plane node"
                                     f" {node_names}:{errors}")
    control_plane_ip = result[0][1].content.decode().split()[0]
    LOGGER.debug(f"Retrieved control plane IP for vapp: "
                 f"{vapp.get_resource().get('name')}, ip: {control_plane_ip}")
    return control_plane_ip


def _init_cluster(sysadmin_client: vcd_client.Client, vapp, template_name,
                  template_revision):
    vcd_utils.raise_error_if_user_not_from_system_org(sysadmin_client)

    try:
        script_filepath = ltm.get_script_filepath(RemoteTemplateCookbookVersion.Version1.value,  # noqa: E501
                                                  template_name,
                                                  template_revision,
                                                  ScriptFile.CONTROL_PLANE)
        script = utils.read_data_file(script_filepath, logger=LOGGER)
        node_names = _get_node_names(vapp, NodeType.CONTROL_PLANE)
        result = _execute_script_in_nodes(sysadmin_client, vapp=vapp,
                                          node_names=node_names, script=script)
        errors = _get_script_execution_errors(result)
        if errors:
            raise e.ScriptExecutionError(
                f"Initialize cluster script execution failed on node "
                f"{node_names}:{errors}")
        if result[0][0] != 0:
            raise e.ClusterInitializationError(f"Couldn't initialize cluster:\n{result[0][2].content.decode()}")  # noqa: E501
    except Exception as err:
        LOGGER.error(err, exc_info=True)
        raise e.ClusterInitializationError(
            f"Couldn't initialize cluster: {str(err)}")


def _join_cluster(sysadmin_client: vcd_client.Client, vapp, template_name,
                  template_revision, target_nodes=None):
    vcd_utils.raise_error_if_user_not_from_system_org(sysadmin_client)
    try:
        script = "#!/usr/bin/env bash\n" \
                 "kubeadm token create\n" \
                 "ip route get 1 | awk '{print $NF;exit}'\n"
        node_names = _get_node_names(vapp, NodeType.CONTROL_PLANE)
        control_plane_result = _execute_script_in_nodes(sysadmin_client,
                                                        vapp=vapp,
                                                        node_names=node_names,
                                                        script=script)
        errors = _get_script_execution_errors(control_plane_result)
        if errors:
            raise e.ScriptExecutionError("Join cluster script execution "
                                         "failed on control plane node "
                                         f"{node_names}:{errors}")
        init_info = control_plane_result[0][1].content.decode().split()

        node_names = _get_node_names(vapp, NodeType.WORKER)
        if target_nodes is not None:
            node_names = [name for name in node_names if name in target_nodes]
        tmp_script_filepath = ltm.get_script_filepath(RemoteTemplateCookbookVersion.Version1.value,  # noqa: E501
                                                      template_name,
                                                      template_revision,
                                                      ScriptFile.NODE)
        tmp_script = utils.read_data_file(tmp_script_filepath, logger=LOGGER)
        script = tmp_script.format(token=init_info[0], ip=init_info[1])
        worker_results = _execute_script_in_nodes(sysadmin_client, vapp=vapp,
                                                  node_names=node_names,
                                                  script=script)
        errors = _get_script_execution_errors(worker_results)
        if errors:
            raise e.ScriptExecutionError("Join cluster script execution "
                                         "failed on worker node"
                                         f" {node_names}:{errors}")
        for result in worker_results:
            if result[0] != 0:
                raise e.ClusterJoiningError(f"Couldn't join cluster:"
                                            f"\n{result[2].content.decode()}")
    except Exception as err:
        LOGGER.error(err, exc_info=True)
        raise e.ClusterJoiningError(f"Couldn't join cluster: {str(err)}")


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
        raise e.CseServerError('VM is not ready to execute scripts')


def _execute_script_in_nodes(sysadmin_client: vcd_client.Client,
                             vapp, node_names, script,
                             check_tools=True, wait=True):
    vcd_utils.raise_error_if_user_not_from_system_org(sysadmin_client)
    all_results = []
    for node_name in node_names:
        try:
            LOGGER.debug(f"will try to execute script on {node_name}:\n"
                         f"{script}")

            vs = vs_utils.get_vsphere(sysadmin_client, vapp, vm_name=node_name,
                                      logger=LOGGER)
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
                result = vs.execute_script_in_guest(
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
                    vs.execute_program_in_guest(vm, 'root', password, script,
                                                wait_for_completion=False,
                                                get_output=False)
                ]
                result_stdout = ''
                result_stderr = ''
            LOGGER.debug(result[0])
            LOGGER.debug(result_stderr)
            LOGGER.debug(result_stdout)
            all_results.append(result)
        except Exception:
            raise e.ScriptExecutionError(f"Error executing script in node {node_name}: {str(e)}")  # noqa: E501
    return all_results


def _run_script_in_nodes(sysadmin_client: vcd_client.Client, vapp_href,
                         node_names, script):
    """Run script in all specified nodes.

    Wrapper around `execute_script_in_nodes()`. Use when we don't care about
    preserving script results

    :param pyvcloud.vcd.client.Client sysadmin_client:
    :param str vapp_href:
    :param List[str] node_names:
    :param str script:
    """
    vcd_utils.raise_error_if_user_not_from_system_org(sysadmin_client)

    # when is tools checking necessary?
    vapp = vcd_vapp.VApp(sysadmin_client, href=vapp_href)
    results = _execute_script_in_nodes(sysadmin_client,
                                       vapp=vapp,
                                       node_names=node_names,
                                       script=script,
                                       check_tools=False)
    errors = _get_script_execution_errors(results)
    if errors:
        raise e.ScriptExecutionError(f"Script execution failed on node "
                                     f"{node_names}\nErrors: {errors}")
    if results[0][0] != 0:
        raise e.NodeOperationError(f"Error during node operation:\n"
                                   f"{results[0][2].content.decode()}")


def _get_script_execution_errors(results):
    return [result[2].content.decode() for result in results if result[0] != 0]

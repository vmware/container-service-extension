# container-service-extension
# Copyright (c) 2020 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause
import random
import re
import string
import threading
import time
from typing import List, Optional
import urllib

import pkg_resources
import pyvcloud.vcd.client as vcd_client
from pyvcloud.vcd.exceptions import EntityNotFoundException
import pyvcloud.vcd.gateway as vcd_gateway
import pyvcloud.vcd.org as vcd_org
import pyvcloud.vcd.task as vcd_task
import pyvcloud.vcd.vapp as vcd_vapp
from pyvcloud.vcd.vdc import VDC
import pyvcloud.vcd.vdc_network as vdc_network
import pyvcloud.vcd.vm as vcd_vm
import semantic_version as semver

import container_service_extension.abstract_broker as abstract_broker
import container_service_extension.cloudapi.constants as cloudapi_constants
import container_service_extension.compute_policy_manager as compute_policy_manager  # noqa: E501
import container_service_extension.def_.entity_service as def_entity_svc
import container_service_extension.def_.models as def_models
import container_service_extension.def_.utils as def_utils
import container_service_extension.exceptions as E
import container_service_extension.local_template_manager as ltm
from container_service_extension.logger import SERVER_LOGGER as LOGGER
from container_service_extension.nsxt_backed_gateway_service import NsxtBackedGatewayService  # noqa: E501
import container_service_extension.operation_context as ctx
import container_service_extension.pyvcloud_utils as vcd_utils
from container_service_extension.server_constants import ClusterMetadataKey
from container_service_extension.server_constants import CSE_CLUSTER_KUBECONFIG_PATH # noqa: E501
from container_service_extension.server_constants import EXPOSE_CLUSTER_NAME_FRAGMENT  # noqa: E501
from container_service_extension.server_constants import IP_PORT_REGEX
from container_service_extension.server_constants import LocalTemplateKey
from container_service_extension.server_constants import NETWORK_URN_PREFIX
from container_service_extension.server_constants import NodeType
from container_service_extension.server_constants import ScriptFile
from container_service_extension.server_constants import SYSTEM_ORG_NAME
from container_service_extension.server_constants import TKGM_DEFAULT_POD_NETWORK_CIDR  # noqa: E501
from container_service_extension.server_constants import TKGM_DEFAULT_SERVICE_CIDR  # noqa: E501
from container_service_extension.server_constants import TKGM_TEMPLATE_NAME_FRAGMENT  # noqa: E501
from container_service_extension.server_constants import UBUNTU_20_TEMPLATE_NAME_FRAGMENT  # noqa: E501
from container_service_extension.server_constants import VdcNetworkInfoKey
from container_service_extension.shared_constants import CSE_PAGINATION_DEFAULT_PAGE_SIZE  # noqa: E501
from container_service_extension.shared_constants import CSE_PAGINATION_FIRST_PAGE_NUMBER  # noqa: E501
from container_service_extension.shared_constants import DefEntityOperation
from container_service_extension.shared_constants import DefEntityOperationStatus  # noqa: E501
from container_service_extension.shared_constants import DefEntityPhase
from container_service_extension.shared_constants import RequestMethod
import container_service_extension.telemetry.constants as telemetry_constants
import container_service_extension.telemetry.telemetry_handler as telemetry_handler  # noqa: E501
import container_service_extension.utils as utils
import container_service_extension.vsphere_utils as vs_utils


class ClusterService(abstract_broker.AbstractBroker):
    """Handles cluster operations for native DEF based clusters."""

    def __init__(self, op_ctx: ctx.OperationContext):
        # TODO(DEF) Once all the methods are modified to use defined entities,
        #  the param OperationContext needs to be replaced by CloudApiClient.
        self.context: Optional[ctx.OperationContext] = None
        # populates above attributes
        super().__init__(op_ctx)

        self.task = None
        self.task_resource = None
        self.task_update_lock = threading.Lock()
        self.entity_svc = def_entity_svc.DefEntityService(
            op_ctx.cloudapi_client)
        self.sysadmin_entity_svc = def_entity_svc.DefEntityService(
            op_ctx.sysadmin_cloudapi_client)

    def get_cluster_info(self, cluster_id: str) -> def_models.DefEntity:
        """Get the corresponding defined entity of the native cluster.

        This method ensures to return the latest state of the cluster vApp.
        It syncs the defined entity with the state of the cluster vApp before
        returning the defined entity.
        """
        telemetry_handler.record_user_action_details(
            cse_operation=telemetry_constants.CseOperation.V35_CLUSTER_INFO,
            cse_params={telemetry_constants.PayloadKey.CLUSTER_ID: cluster_id}
        )
        return self._sync_def_entity(cluster_id)

    def get_clusters_by_page(self, filters: dict = None,
                             page_number=CSE_PAGINATION_FIRST_PAGE_NUMBER,
                             page_size=CSE_PAGINATION_DEFAULT_PAGE_SIZE):
        """List clusters by page number and page size.

        :param dict filters: filters to use to filter the cluster response
        :param int page_number: page number of the clusters to be fetched
        :param int page_size: page size of the result
        :return: paginated response containing native clusters
        :rtype: dict
        """
        if not filters:
            filters = {}

        telemetry_handler.record_user_action_details(
            cse_operation=telemetry_constants.CseOperation.V35_CLUSTER_LIST,
            cse_params={telemetry_constants.PayloadKey.FILTER_KEYS: ','.join(filters.keys())}  # noqa: E501
        )

        ent_type: def_models.DefEntityType = def_utils.get_registered_def_entity_type()  # noqa: E501

        return self.entity_svc.get_entities_per_page_by_entity_type(
            vendor=ent_type.vendor,
            nss=ent_type.nss,
            version=ent_type.version,
            filters=filters,
            page_number=page_number,
            page_size=page_size)

    def list_clusters(self, filters: dict = None) -> list:
        """List corresponding defined entities of all native clusters.

        :param dict filters: filters to use to filter the cluster response
        :return: list of all native clusters
        :rtype: list
        """
        if not filters:
            filters = {}

        telemetry_handler.record_user_action_details(
            cse_operation=telemetry_constants.CseOperation.V35_CLUSTER_LIST,
            cse_params={telemetry_constants.PayloadKey.FILTER_KEYS: ','.join(filters.keys())}  # noqa: E501
        )

        ent_type: def_models.DefEntityType = def_utils.get_registered_def_entity_type()  # noqa: E501

        return self.entity_svc.list_entities_by_entity_type(
            vendor=ent_type.vendor,
            nss=ent_type.nss,
            version=ent_type.version,
            filters=filters)

    def get_cluster_config(self, cluster_id: str):
        """Get the cluster's kube config contents.

        :param str cluster_id:
        :return: Dictionary containing cluster config.
        :rtype: dict
        """
        curr_entity = self.entity_svc.get_entity(cluster_id)
        if curr_entity.state != def_utils.DEF_RESOLVED_STATE:
            raise E.CseServerError(
                f"Cluster {curr_entity.name} with id {cluster_id} is not in a "
                f"valid state for this operation. Please contact the administrator")  # noqa: E501

        telemetry_handler.record_user_action_details(
            cse_operation=telemetry_constants.CseOperation.V35_CLUSTER_CONFIG,
            cse_params=curr_entity)

        vapp = vcd_vapp.VApp(self.context.client, href=curr_entity.externalId)
        control_plane_node_name = curr_entity.entity.status.nodes.control_plane.name  # noqa: E501

        LOGGER.debug(f"getting file from node {control_plane_node_name}")
        password = vapp.get_admin_password(control_plane_node_name)
        vs = vs_utils.get_vsphere(self.context.sysadmin_client, vapp,
                                  vm_name=control_plane_node_name,
                                  logger=LOGGER)
        vs.connect()
        moid = vapp.get_vm_moid(control_plane_node_name)
        vm = vs.get_vm_by_moid(moid)
        result = vs.download_file_from_guest(vm, 'root', password,
                                             CSE_CLUSTER_KUBECONFIG_PATH)

        if not result:
            raise E.ClusterOperationError("Couldn't get cluster configuration")

        return result.content.decode()

    def create_cluster(self, cluster_spec: def_models.NativeEntity):
        """Start the cluster creation operation.

        Creates corresponding defined entity in vCD for every native cluster.
        Updates the defined entity with new properties after the cluster
        creation.

        **telemetry: Optional

        :return: Defined entity of the cluster
        :rtype: def_models.DefEntity
        """
        cluster_name = cluster_spec.metadata.cluster_name
        org_name = cluster_spec.metadata.org_name
        ovdc_name = cluster_spec.metadata.ovdc_name
        template_name = cluster_spec.spec.k8_distribution.template_name
        template_revision = cluster_spec.spec.k8_distribution.template_revision
        if not (template_name or template_revision):
            default_dist = utils.get_default_k8_distribution()
            cluster_spec.spec.k8_distribution = default_dist
            template_name = default_dist.template_name
            template_revision = default_dist.template_revision

        # check that cluster name is syntactically valid
        if not _is_valid_cluster_name(cluster_name):
            raise E.CseServerError(f"Invalid cluster name '{cluster_name}'")

        # Check that cluster name doesn't already exist.
        # Do not replace the below with the check to verify if defined entity
        # already exists. It will not give accurate result as even sys-admin
        # cannot view all the defined entities unless native entity type admin
        # view right is assigned.
        if _cluster_exists(self.context.client, cluster_name,
                           org_name=org_name,
                           ovdc_name=ovdc_name):
            raise E.ClusterAlreadyExistsError(
                f"Cluster '{cluster_name}' already exists.")

        # check that requested/default template is valid
        template = _get_template(
            name=template_name, revision=template_revision)

        # TODO(DEF) design and implement telemetry VCDA-1564 defined entity
        #  based clusters

        # create the corresponding defined entity .
        def_entity = def_models.DefEntity(entity=cluster_spec)
        def_entity.entity.status.phase = str(
            DefEntityPhase(DefEntityOperation.CREATE,
                           DefEntityOperationStatus.IN_PROGRESS))
        def_entity.entity.status.kubernetes = \
            _create_k8s_software_string(template[LocalTemplateKey.KUBERNETES],
                                        template[LocalTemplateKey.KUBERNETES_VERSION]) # noqa: E501
        def_entity.entity.status.cni = \
            _create_k8s_software_string(template[LocalTemplateKey.CNI],
                                        template[LocalTemplateKey.CNI_VERSION])
        def_entity.entity.status.docker_version = template[LocalTemplateKey.DOCKER_VERSION] # noqa: E501
        def_entity.entity.status.os = template[LocalTemplateKey.OS]
        # No need to set org context for non sysadmin users
        org_context = None
        if self.context.client.is_sysadmin():
            org_resource = vcd_utils.get_org(self.context.client,
                                             org_name=def_entity.entity.metadata.org_name)  # noqa: E501
            org_context = org_resource.href.split('/')[-1]
        msg = f"Creating cluster '{cluster_name}' " \
              f"from template '{template_name}' (revision {template_revision})"
        self._update_task(vcd_client.TaskStatus.RUNNING, message=msg)
        def_entity.entity.status.task_href = self.task_resource.get('href')
        try:
            self.entity_svc.create_entity(
                def_utils.get_registered_def_entity_type().id,
                entity=def_entity,
                tenant_org_context=org_context)
            def_entity = self.entity_svc.get_native_entity_by_name(cluster_name)  # noqa: E501
        except Exception as err:
            msg = f"Error creating the cluster '{cluster_name}'"
            LOGGER.error(f"{msg}: {err}")
            self._update_task(vcd_client.TaskStatus.ERROR,
                              message=msg,
                              error_message=str(err))
            raise
        self.context.is_async = True
        telemetry_handler.record_user_action_details(
            cse_operation=telemetry_constants.CseOperation.V35_CLUSTER_APPLY,
            cse_params=def_entity)
        self._create_cluster_async(def_entity.id, cluster_spec)
        return def_entity

    def resize_cluster(self, cluster_id: str,
                       cluster_spec: def_models.NativeEntity):
        """Start the resize cluster operation.

        :param str cluster_id: Defined entity Id of the cluster
        :param DefEntity cluster_spec: Input cluster spec
        :return: DefEntity of the cluster with the updated operation status
        and task_href.

        :rtype: DefEntity
        """
        # Get the existing defined entity for the given cluster id
        curr_entity: def_models.DefEntity = self.entity_svc.get_entity(cluster_id)  # noqa: E501
        cluster_name: str = curr_entity.name
        curr_worker_count: int = curr_entity.entity.spec.workers.count
        curr_nfs_count: int = curr_entity.entity.spec.nfs.count
        state: str = curr_entity.state
        phase: DefEntityPhase = DefEntityPhase.from_phase(
            curr_entity.entity.status.phase)

        # compute the values of workers and nfs to be added or removed by
        # comparing the desired and the current state. "num_workers_to_add"
        # can hold either +ve or -ve value.
        desired_worker_count: int = cluster_spec.spec.workers.count
        desired_nfs_count: int = cluster_spec.spec.nfs.count
        num_workers_to_add: int = desired_worker_count - curr_worker_count
        num_nfs_to_add: int = desired_nfs_count - curr_nfs_count

        # Check for un-exposing the cluster
        desired_expose_state: bool = cluster_spec.spec.expose
        is_exposed: bool = curr_entity.entity.status.exposed
        unexpose: bool = is_exposed and not desired_expose_state

        # Check if the desired worker and nfs count is valid and raise
        # an exception if the cluster does not need to be unexposed
        if not unexpose and num_workers_to_add == 0 and num_nfs_to_add == 0:
            raise E.CseServerError(f"Cluster '{cluster_name}' already has "
                                   f"{desired_worker_count} workers and "
                                   f"{desired_nfs_count} nfs nodes.")
        elif not unexpose and desired_worker_count < 0:
            raise E.CseServerError(
                f"Worker count must be >= 0 (received {desired_worker_count})")
        elif not unexpose and num_nfs_to_add < 0:
            raise E.CseServerError("Scaling down nfs nodes is not supported")

        # check if cluster is in a valid state
        if state != def_utils.DEF_RESOLVED_STATE or phase.is_entity_busy():
            raise E.CseServerError(
                f"Cluster {cluster_name} with id {cluster_id} is not in a "
                f"valid state to be resized. Please contact the administrator")

        # Record telemetry details
        telemetry_data: def_models.DefEntity = def_models.DefEntity(id=cluster_id, entity=cluster_spec)  # noqa: E501
        telemetry_handler.record_user_action_details(
            cse_operation=telemetry_constants.CseOperation.V35_CLUSTER_APPLY,
            cse_params=telemetry_data)

        # update the task and defined entity.
        msg = f"Resizing the cluster '{cluster_name}' ({cluster_id}) to the " \
              f"desired worker count {desired_worker_count} and " \
              f"nfs count {desired_nfs_count}"
        if unexpose:
            msg += " and un-exposing the cluster"
        self._update_task(vcd_client.TaskStatus.RUNNING, message=msg)
        curr_entity.entity.status.task_href = self.task_resource.get('href')
        curr_entity.entity.status.phase = str(
            DefEntityPhase(DefEntityOperation.UPDATE,
                           DefEntityOperationStatus.IN_PROGRESS))
        try:
            curr_entity = self.entity_svc.update_entity(cluster_id, curr_entity)  # noqa: E501
        except Exception as err:
            self._update_task(vcd_client.TaskStatus.ERROR,
                              message=msg,
                              error_message=str(err))
            LOGGER.error(str(err))
            raise
        # trigger async operation
        self.context.is_async = True
        self._monitor_update(cluster_id=cluster_id,
                             cluster_spec=cluster_spec)
        return curr_entity

    def delete_cluster(self, cluster_id):
        """Start the delete cluster operation."""
        # Get the current state of the defined entity
        curr_entity: def_models.DefEntity = self.entity_svc.get_entity(
            cluster_id)
        cluster_name: str = curr_entity.name
        org_name: str = curr_entity.entity.metadata.org_name
        ovdc_name: str = curr_entity.entity.metadata.ovdc_name
        phase: DefEntityPhase = DefEntityPhase.from_phase(
            curr_entity.entity.status.phase)

        # Check if cluster is busy
        if phase.is_entity_busy():
            raise E.CseServerError(
                f"Cluster {cluster_name} with id {cluster_id} is not in a "
                f"valid state to be deleted. Please contact administrator.")

        telemetry_handler.record_user_action_details(
            cse_operation=telemetry_constants.CseOperation.V35_CLUSTER_DELETE,
            cse_params=curr_entity)

        # must _update_task here or else self.task_resource is None
        # do not logout of sys admin, or else in pyvcloud's session.request()
        # call, session becomes None
        msg = f"Deleting cluster '{cluster_name}' ({cluster_id})"
        self._update_task(vcd_client.TaskStatus.RUNNING, message=msg)

        curr_entity.entity.status.task_href = self.task_resource.get('href')
        curr_entity.entity.status.phase = str(
            DefEntityPhase(DefEntityOperation.DELETE,
                           DefEntityOperationStatus.IN_PROGRESS))
        try:
            # attempt deleting the defined entity;
            # lets vCD authorize the user for delete operation.
            self.entity_svc.delete_entity(cluster_id)
        except Exception as err:
            self._update_task(vcd_client.TaskStatus.ERROR,
                              message=msg,
                              error_message=str(err))
            LOGGER.error(str(err))
            raise
        self.context.is_async = True
        self._delete_cluster_async(cluster_name=cluster_name,
                                   org_name=org_name, ovdc_name=ovdc_name,
                                   def_entity=curr_entity)
        return curr_entity

    def get_cluster_upgrade_plan(self, cluster_id: str):
        """Get the template names/revisions that the cluster can upgrade to.

        :param str cluster_id:
        :return: A list of dictionaries with keys defined in LocalTemplateKey

        :rtype: List[Dict]
        """
        curr_entity = self.entity_svc.get_entity(cluster_id)
        telemetry_handler.record_user_action_details(
            cse_operation=telemetry_constants.CseOperation.V35_CLUSTER_UPGRADE_PLAN,  # noqa: E501
            cse_params=curr_entity
        )

        return self._get_cluster_upgrade_plan(
            curr_entity.entity.spec.k8_distribution.template_name,
            curr_entity.entity.spec.k8_distribution.template_revision)

    def upgrade_cluster(self, cluster_id: str,
                        upgrade_spec: def_models.NativeEntity):
        """Start the upgrade cluster operation.

        Upgrading cluster is an asynchronous task, so the returned
        `result['task_href']` can be polled to get updates on task progress.

        :param str cluster_id: id of the cluster to be upgraded
        :param def_models.NativeEntity upgrade_spec: cluster spec with new
            kubernetes distribution and revision

        :return: Defined entity with upgrade in progress set
        :rtype: def_models.DefEntity representing the cluster
        """
        curr_entity = self.entity_svc.get_entity(cluster_id)
        cluster_name = curr_entity.entity.metadata.cluster_name
        new_template_name = upgrade_spec.spec.k8_distribution.template_name
        new_template_revision = upgrade_spec.spec.k8_distribution.template_revision # noqa: E501

        # check if cluster is in a valid state
        phase: DefEntityPhase = DefEntityPhase.from_phase(
            curr_entity.entity.status.phase)
        state: str = curr_entity.state
        if state != def_utils.DEF_RESOLVED_STATE or phase.is_entity_busy():
            raise E.CseServerError(
                f"Cluster {cluster_name} with id {cluster_id} is not in a "
                f"valid state to be upgraded. Please contact administrator.")

        # check that the specified template is a valid upgrade target
        template = {}
        valid_templates = self._get_cluster_upgrade_plan(
            curr_entity.entity.spec.k8_distribution.template_name,
            curr_entity.entity.spec.k8_distribution.template_revision)

        for t in valid_templates:
            if (t[LocalTemplateKey.NAME], str(t[LocalTemplateKey.REVISION])) == (new_template_name, str(new_template_revision)): # noqa: E501
                template = t
                break
        if not template:
            # TODO all of these e.CseServerError instances related to request
            # should be changed to BadRequestError (400)
            raise E.CseServerError(
                f"Specified template/revision ({new_template_name} revision "
                f"{new_template_revision}) is not a valid upgrade target for "
                f"cluster '{cluster_name}'.")

        telemetry_handler.record_user_action_details(
            telemetry_constants.CseOperation.V35_CLUSTER_UPGRADE,
            cse_params=curr_entity)

        msg = f"Upgrading cluster '{cluster_name}' " \
              f"software to match template {new_template_name} (revision " \
              f"{new_template_revision}): Kubernetes: " \
              f"{curr_entity.entity.status.kubernetes} -> " \
              f"{template[LocalTemplateKey.KUBERNETES_VERSION]}, Docker-CE: " \
              f"{curr_entity.entity.status.docker_version} -> " \
              f"{template[LocalTemplateKey.DOCKER_VERSION]}, CNI: " \
              f"{curr_entity.entity.status.cni} -> " \
              f"{template[LocalTemplateKey.CNI_VERSION]}"
        self._update_task(vcd_client.TaskStatus.RUNNING, message=msg)
        LOGGER.info(f"{msg} ({curr_entity.externalId})")

        curr_entity.entity.status.phase = str(
            DefEntityPhase(DefEntityOperation.UPGRADE, DefEntityOperationStatus.IN_PROGRESS))  # noqa: E501
        curr_entity.entity.status.task_href = self.task_resource.get('href')
        try:
            curr_entity = self.entity_svc.update_entity(cluster_id, curr_entity)  # noqa: E501
        except Exception as err:
            self._update_task(vcd_client.TaskStatus.ERROR,
                              message=msg,
                              error_message=str(err))
            LOGGER.error(str(err))
            raise

        self.context.is_async = True
        self._upgrade_cluster_async(cluster_id=cluster_id,
                                    template=template)
        return curr_entity

    def delete_nodes(self, cluster_id: str, nodes_to_del=None):
        """Start the delete nodes operation."""
        if nodes_to_del is None:
            nodes_to_del = []
        curr_entity: def_models.DefEntity = self.entity_svc.get_entity(
            cluster_id)

        if len(nodes_to_del) == 0:
            LOGGER.debug("No nodes specified to delete")
            return curr_entity

        # must _update_task here or else self.task_resource is None
        # do not logout of sys admin, or else in pyvcloud's session.request()
        # call, session becomes None

        msg = f"Deleting {', '.join(nodes_to_del)} node(s) from cluster " \
              f"'{curr_entity.entity.metadata.cluster_name}' ({cluster_id})"
        self._update_task(vcd_client.TaskStatus.RUNNING, message=msg)

        # TODO(DEF) design and implement telemetry VCDA-1564 defined entity
        #  based clusters

        curr_entity.entity.status.task_href = self.task_resource.get('href')
        curr_entity.entity.status.phase = str(
            DefEntityPhase(DefEntityOperation.UPDATE,
                           DefEntityOperationStatus.IN_PROGRESS))
        try:
            curr_entity = self.entity_svc.update_entity(cluster_id, curr_entity)  # noqa: E501
        except Exception as err:
            self._update_task(vcd_client.TaskStatus.ERROR,
                              message=msg,
                              error_message=str(err))
            LOGGER.error(str(err))
            raise

        self.context.is_async = True
        self._monitor_delete_nodes(cluster_id=cluster_id,
                                   nodes_to_del=nodes_to_del)
        return curr_entity

    @utils.run_async
    def _create_cluster_async(self, cluster_id: str,
                              cluster_spec: def_models.NativeEntity):
        vapp = None
        expose_ip: str = ''
        cluster_name = ''
        rollback = False
        org_name = ''
        ovdc_name = ''
        network_name = ''
        try:
            cluster_name = cluster_spec.metadata.cluster_name
            org_name = cluster_spec.metadata.org_name
            ovdc_name = cluster_spec.metadata.ovdc_name
            num_workers = cluster_spec.spec.workers.count
            control_plane_sizing_class = cluster_spec.spec.control_plane.sizing_class  # noqa: E501
            worker_sizing_class = cluster_spec.spec.workers.sizing_class
            control_plane_storage_profile = cluster_spec.spec.control_plane.storage_profile  # noqa: E501
            worker_storage_profile = cluster_spec.spec.workers.storage_profile  # noqa: E501
            nfs_count = cluster_spec.spec.nfs.count
            nfs_sizing_class = cluster_spec.spec.nfs.sizing_class
            nfs_storage_profile = cluster_spec.spec.nfs.storage_profile
            network_name = cluster_spec.spec.settings.network
            template_name = cluster_spec.spec.k8_distribution.template_name
            template_revision = cluster_spec.spec.k8_distribution.template_revision  # noqa: E501
            ssh_key = cluster_spec.spec.settings.ssh_key
            rollback = cluster_spec.spec.settings.rollback_on_failure
            expose = cluster_spec.spec.expose
            vapp = None
            org = vcd_utils.get_org(self.context.client, org_name=org_name)
            vdc = vcd_utils.get_vdc(self.context.client,
                                    vdc_name=ovdc_name,
                                    org=org)

            LOGGER.debug(f"About to create cluster '{cluster_name}' on "
                         f"{ovdc_name} with {num_workers} worker nodes, "
                         f"storage profile={worker_storage_profile}")
            msg = f"Creating cluster vApp {cluster_name} ({cluster_id})"
            self._update_task(vcd_client.TaskStatus.RUNNING, message=msg)
            try:
                vapp_resource = vdc.create_vapp(
                    cluster_name,
                    description=f"cluster '{cluster_name}'",
                    network=network_name,
                    fence_mode='bridged')
            except Exception as err:
                LOGGER.error(err, exc_info=True)
                raise E.ClusterOperationError(
                    f"Error while creating vApp: {err}")
            self.context.client.get_task_monitor().wait_for_status(vapp_resource.Tasks.Task[0]) # noqa: E501

            template = _get_template(template_name, template_revision)

            LOGGER.debug(f"Setting metadata on cluster vApp '{cluster_name}'")
            tags = {
                ClusterMetadataKey.CLUSTER_ID: cluster_id,
                ClusterMetadataKey.CSE_VERSION: pkg_resources.require('container-service-extension')[0].version, # noqa: E501
                ClusterMetadataKey.TEMPLATE_NAME: template[LocalTemplateKey.NAME], # noqa: E501
                ClusterMetadataKey.TEMPLATE_REVISION: template[LocalTemplateKey.REVISION], # noqa: E501
                ClusterMetadataKey.OS: template[LocalTemplateKey.OS],
                ClusterMetadataKey.DOCKER_VERSION: template[LocalTemplateKey.DOCKER_VERSION], # noqa: E501
                ClusterMetadataKey.KUBERNETES: template[LocalTemplateKey.KUBERNETES], # noqa: E501
                ClusterMetadataKey.KUBERNETES_VERSION: template[LocalTemplateKey.KUBERNETES_VERSION], # noqa: E501
                ClusterMetadataKey.CNI: template[LocalTemplateKey.CNI],
                ClusterMetadataKey.CNI_VERSION: template[LocalTemplateKey.CNI_VERSION] # noqa: E501
            }
            vapp = vcd_vapp.VApp(self.context.client,
                                 href=vapp_resource.get('href'))
            task = vapp.set_multiple_metadata(tags)
            self.context.client.get_task_monitor().wait_for_status(task)

            msg = f"Creating control plane node for cluster '{cluster_name}'" \
                  f" ({cluster_id})"
            LOGGER.debug(msg)
            self._update_task(vcd_client.TaskStatus.RUNNING, message=msg)
            vapp.reload()
            server_config = utils.get_server_runtime_config()
            catalog_name = server_config['broker']['catalog']
            try:
                _add_nodes(self.context.sysadmin_client,
                           num_nodes=1,
                           node_type=NodeType.CONTROL_PLANE,
                           org=org,
                           vdc=vdc,
                           vapp=vapp,
                           catalog_name=catalog_name,
                           template=template,
                           network_name=network_name,
                           storage_profile=control_plane_storage_profile,
                           ssh_key=ssh_key,
                           sizing_class_name=control_plane_sizing_class)
            except Exception as err:
                LOGGER.error(err, exc_info=True)
                raise E.ControlPlaneNodeCreationError(
                    f"Error adding control plane node: {err}")

            msg = f"Initializing cluster '{cluster_name}' ({cluster_id})"
            LOGGER.debug(msg)
            self._update_task(vcd_client.TaskStatus.RUNNING, message=msg)
            vapp.reload()
            is_ubuntu_20 = UBUNTU_20_TEMPLATE_NAME_FRAGMENT in template_name
            control_plane_ip = _get_control_plane_ip(
                self.context.sysadmin_client, vapp, check_tools=True,
                use_ubuntu_20_sleep=is_ubuntu_20)

            # Handle exposing cluster
            if expose:
                try:
                    expose_ip = _expose_cluster(
                        client=self.context.client,
                        org_name=org_name,
                        ovdc_name=ovdc_name,
                        network_name=cluster_spec.spec.settings.network,
                        cluster_name=cluster_name,
                        cluster_id=cluster_id,
                        internal_ip=control_plane_ip)
                    if expose_ip:
                        control_plane_ip = expose_ip
                except Exception as err:
                    LOGGER.error(f'Exposing cluster failed: {str(err)}')
                    expose_ip = ''

            _init_cluster(self.context.sysadmin_client,
                          vapp,
                          template[LocalTemplateKey.NAME],
                          template[LocalTemplateKey.REVISION],
                          expose_ip=expose_ip)

            task = vapp.set_metadata('GENERAL', 'READWRITE', 'cse.master.ip',
                                     control_plane_ip)
            self.context.client.get_task_monitor().wait_for_status(task)

            msg = f"Creating {num_workers} node(s) for cluster " \
                  f"'{cluster_name}' ({cluster_id})"
            LOGGER.debug(msg)
            self._update_task(vcd_client.TaskStatus.RUNNING, message=msg)
            try:
                _add_nodes(self.context.sysadmin_client,
                           num_nodes=num_workers,
                           node_type=NodeType.WORKER,
                           org=org,
                           vdc=vdc,
                           vapp=vapp,
                           catalog_name=catalog_name,
                           template=template,
                           network_name=network_name,
                           storage_profile=worker_storage_profile,
                           ssh_key=ssh_key,
                           sizing_class_name=worker_sizing_class)
            except Exception as err:
                LOGGER.error(err, exc_info=True)
                raise E.WorkerNodeCreationError(
                    f"Error creating worker node: {err}")

            msg = f"Adding {num_workers} node(s) to cluster " \
                  f"'{cluster_name}' ({cluster_id})"
            LOGGER.debug(msg)
            self._update_task(vcd_client.TaskStatus.RUNNING, message=msg)
            vapp.reload()
            _join_cluster(self.context.sysadmin_client,
                          vapp,
                          template[LocalTemplateKey.NAME],
                          template[LocalTemplateKey.REVISION])

            if nfs_count > 0:
                msg = f"Creating {nfs_count} NFS nodes for cluster " \
                      f"'{cluster_name}' ({cluster_id})"
                LOGGER.debug(msg)
                self._update_task(vcd_client.TaskStatus.RUNNING, message=msg)
                try:
                    _add_nodes(self.context.sysadmin_client,
                               num_nodes=nfs_count,
                               node_type=NodeType.NFS,
                               org=org,
                               vdc=vdc,
                               vapp=vapp,
                               catalog_name=catalog_name,
                               template=template,
                               network_name=network_name,
                               storage_profile=nfs_storage_profile,
                               ssh_key=ssh_key,
                               sizing_class_name=nfs_sizing_class)
                except Exception as err:
                    LOGGER.error(err, exc_info=True)
                    raise E.NFSNodeCreationError(
                        f"Error creating NFS node: {err}")

            # Update defined entity instance with new properties like vapp_id,
            # control plane_ip and nodes.
            msg = f"Updating cluster `{cluster_name}` ({cluster_id}) defined entity"  # noqa: E501
            LOGGER.debug(msg)
            self._update_task(vcd_client.TaskStatus.RUNNING, message=msg)
            def_entity: def_models.DefEntity = self.entity_svc.get_entity(cluster_id)  # noqa: E501
            def_entity.externalId = vapp_resource.get('href')
            def_entity.entity.status.phase = str(
                DefEntityPhase(DefEntityOperation.CREATE,
                               DefEntityOperationStatus.SUCCEEDED))
            def_entity.entity.status.nodes = _get_nodes_details(
                self.context.sysadmin_client, vapp)

            # Update defined entity with exposed status and exposed ip
            if expose_ip:
                def_entity.entity.status.exposed = True
                if def_entity.entity.status.nodes:
                    def_entity.entity.status.nodes.control_plane.ip = expose_ip

            self.entity_svc.update_entity(cluster_id, def_entity)
            self.entity_svc.resolve_entity(cluster_id)

            # cluster creation succeeded. Mark the task as success
            msg = f"Created cluster '{cluster_name}' ({cluster_id})"
            LOGGER.debug(msg)
            self._update_task(vcd_client.TaskStatus.SUCCESS, message=msg)
        except (E.ControlPlaneNodeCreationError, E.WorkerNodeCreationError,
                E.NFSNodeCreationError, E.ClusterJoiningError,
                E.ClusterInitializationError, E.ClusterOperationError) as err:
            msg = f"Error creating cluster '{cluster_name}'"
            LOGGER.error(msg, exc_info=True)
            if rollback:
                msg = f"Error creating cluster '{cluster_name}'. " \
                      f"Deleting cluster (rollback=True)"
                self._update_task(vcd_client.TaskStatus.RUNNING, message=msg)
                LOGGER.info(msg)
                try:
                    _delete_vapp(self.context.client,
                                 org_name,
                                 ovdc_name,
                                 cluster_name)
                except Exception:
                    LOGGER.error(f"Failed to delete cluster '{cluster_name}'",
                                 exc_info=True)

                if expose_ip:
                    try:
                        _handle_delete_expose_dnat_rule(
                            client=self.context.client,
                            org_name=org_name,
                            ovdc_name=ovdc_name,
                            network_name=network_name,
                            cluster_name=cluster_name,
                            cluster_id=cluster_id)
                        LOGGER.info(f'Deleted dnat rule for cluster '
                                    f'{cluster_name} ({cluster_id})')
                    except Exception as err:
                        LOGGER.error(f'Failed to delete dnat rule for '
                                     f'{cluster_name} ({cluster_id}) with '
                                     f'error: {str(err)}')

                try:
                    # Delete the corresponding defined entity
                    self.sysadmin_entity_svc.resolve_entity(cluster_id)
                    self.sysadmin_entity_svc.delete_entity(cluster_id)
                except Exception:
                    LOGGER.error("Failed to delete the defined entity for "
                                 f"cluster '{cluster_name}'", exc_info=True)
            else:
                # TODO Avoid many try-except block. Check if it is a good
                # practice
                try:
                    self._fail_operation(cluster_id, DefEntityOperation.CREATE)
                except Exception:
                    msg = f"Failed to update defined entity status for cluster {cluster_id}"  # noqa: E501
                    LOGGER.error(msg, exc_info=True)
                # NOTE: sync of the defined entity should happen before call
                # to resolve defined entity to prevent possible missing values
                # in the defined entity
                try:
                    self._sync_def_entity(cluster_id, vapp=vapp)
                except Exception:
                    msg = f"Failed to sync defined entity for cluster {cluster_id}"  # noqa: E501
                    LOGGER.error(msg, exc_info=True)
                try:
                    self.entity_svc.resolve_entity(cluster_id)
                except Exception:
                    msg = f"Failed to resolve defined entity for cluster {cluster_id}"  # noqa: E501
                    LOGGER.error(msg, exc_info=True)
            self._update_task(vcd_client.TaskStatus.ERROR,
                              message=msg,
                              error_message=str(err))
        except Exception as err:
            msg = f"Unknown error creating cluster '{cluster_name}'"
            LOGGER.error(msg, exc_info=True)
            # TODO Avoid many try-except block. Check if it is a good
            # practice
            try:
                self._fail_operation(cluster_id, DefEntityOperation.CREATE)
            except Exception:
                msg = f"Failed to update defined entity status for cluster {cluster_id}"  # noqa: E501
                LOGGER.error(msg, exc_info=True)
            # NOTE: sync of the defined entity should happen before call
            # to resolve defined entity to prevent possible missing values in
            # the defined entity
            try:
                self._sync_def_entity(cluster_id, vapp=vapp)
            except Exception:
                msg = f"Failed to sync defined entity for cluster {cluster_id}"  # noqa: E501
                LOGGER.error(msg, exc_info=True)
            try:
                self.entity_svc.resolve_entity(cluster_id)
            except Exception:
                msg = f"Failed to resolve defined entity for cluster {cluster_id}"  # noqa: E501
                LOGGER.error(msg, exc_info=True)
            self._update_task(vcd_client.TaskStatus.ERROR,
                              message=msg,
                              error_message=str(err))
        finally:
            # TODO re-organize updating defined entity and task update as per
            # https://stackoverflow.com/questions/49099637/how-to-determine-if-an-exception-was-raised-once-youre-in-the-finally-block
            # noqa: E501
            self.context.end()

    @utils.run_async
    def _monitor_update(self, cluster_id, cluster_spec):
        """Triggers and monitors one or more async threads of update.

        This method (or) thread triggers two async threads (for node
        addition and deletion) in parallel. It waits for both the threads to
        join before calling the resize operation complete.


        Performs below once child threads join back.
        - updates the defined entity
        - updates the task status to SUCCESS
        - ends the client context

        If the cluster is exposed and the spec shows to un-expose the cluster,
        it will be de-exposed.
        """
        cluster_name = ''
        try:
            curr_entity: def_models.DefEntity = self.entity_svc.get_entity(
                cluster_id)
            cluster_name: str = curr_entity.name
            curr_worker_count: int = curr_entity.entity.spec.workers.count
            curr_nfs_count: int = curr_entity.entity.spec.nfs.count
            template_name = curr_entity.entity.spec.k8_distribution.template_name  # noqa: E501
            template_revision = curr_entity.entity.spec.k8_distribution.template_revision  # noqa: E501

            desired_worker_count: int = cluster_spec.spec.workers.count
            desired_nfs_count: int = cluster_spec.spec.nfs.count
            num_workers_to_add: int = desired_worker_count - curr_worker_count
            num_nfs_to_add: int = desired_nfs_count - curr_nfs_count

            if num_workers_to_add > 0 or num_nfs_to_add > 0:
                _get_template(name=template_name, revision=template_revision)
                self._create_nodes_async(cluster_id=cluster_id,
                                         cluster_spec=cluster_spec)

                # TODO Below is the temporary fix to avoid parallel Recompose
                #  error between node creation and deletion threads. Below
                #  serializes the sequence of node creation and deletion.
                #  Remove the below block once the issue is fixed in pyvcloud.
                create_nodes_async_thread_name = utils.generate_thread_name(
                    self._create_nodes_async.__name__)
                for t in threading.enumerate():
                    if t.getName() == create_nodes_async_thread_name:
                        t.join()
            if num_workers_to_add < 0:
                self._delete_nodes_async(cluster_id=cluster_id,
                                         cluster_spec=cluster_spec)

            # Wait for the children threads of the current thread to join
            curr_thread_id = str(threading.current_thread().ident)
            for t in threading.enumerate():
                if t.getName().endswith(curr_thread_id):
                    t.join()

            # Handle deleting the dnat rule if the cluster was exposed and
            # the user's current desire is to un-expose the cluster
            desired_expose_state: bool = cluster_spec.spec.expose
            is_exposed: bool = curr_entity.entity.status.exposed
            unexpose: bool = is_exposed and not desired_expose_state
            unexpose_success: bool = False
            if unexpose:
                org_name: str = curr_entity.entity.metadata.org_name
                ovdc_name: str = curr_entity.entity.metadata.ovdc_name
                network_name: str = curr_entity.entity.spec.settings.network
                try:
                    # Get internal ip
                    vapp_href = curr_entity.externalId
                    vapp = vcd_vapp.VApp(self.context.client,
                                         href=vapp_href)
                    control_plane_internal_ip = _get_control_plane_ip(
                        sysadmin_client=self.context.sysadmin_client,
                        vapp=vapp,
                        check_tools=True)

                    # update kubeconfig with internal ip
                    self._replace_kubeconfig_expose_ip(
                        internal_ip=control_plane_internal_ip,
                        cluster_id=cluster_id,
                        vapp=vapp)

                    # Delete dnat rule
                    _handle_delete_expose_dnat_rule(
                        client=self.context.client,
                        org_name=org_name,
                        ovdc_name=ovdc_name,
                        network_name=network_name,
                        cluster_name=cluster_name,
                        cluster_id=cluster_id)

                    # Update RDE control plane ip to be internal ip
                    curr_entity.entity.status.nodes.control_plane.ip = control_plane_internal_ip  # noqa: E501
                    curr_entity.entity.status.exposed = False
                    unexpose_success = True
                except Exception as err:
                    LOGGER.error(
                        f'Failed to un-expose cluster with error: {str(err)}')  # noqa: E501

            # update the defined entity and the task status. Check if one of
            # the child threads had set the status to ERROR.
            curr_task_status = self.task_resource.get('status')
            if curr_task_status == vcd_client.TaskStatus.ERROR.value:
                # NOTE: Possible repetition of operation.
                # _create_node_async() and _delete_node_async() also
                # sets status to failed
                curr_entity.entity.status.phase = str(
                    DefEntityPhase(DefEntityOperation.UPDATE,
                                   DefEntityOperationStatus.FAILED))
            else:
                msg = f"Resized the cluster '{cluster_name}' ({cluster_id}) " \
                      f"to the desired worker count {desired_worker_count} " \
                      f"and nfs count {desired_nfs_count}"
                if unexpose_success:
                    msg += " and un-exposed the cluster"
                elif unexpose and not unexpose_success:
                    msg += " and failed to un-expose the cluster"

                self._update_task(vcd_client.TaskStatus.SUCCESS, message=msg)
                curr_entity.entity.status.phase = str(
                    DefEntityPhase(DefEntityOperation.UPDATE,
                                   DefEntityOperationStatus.SUCCEEDED))

            self._sync_def_entity(cluster_id, curr_entity)
        except Exception as err:
            msg = f"Unexpected error while resizing nodes for {cluster_name}" \
                  f" ({cluster_id})"
            LOGGER.error(f"{msg}",
                         exc_info=True)
            # TODO: Avoid many try-except block. Check if it is a good practice
            try:
                self._fail_operation(
                    cluster_id,
                    DefEntityOperation.UPDATE)
            except Exception:
                msg = f"Failed to update defined entity status " \
                      f" for cluster {cluster_id}"
                LOGGER.error(f"{msg}", exc_info=True)

            # NOTE: Since the defined entity is assumed to be
            # resolved during cluster creation, there is no need
            # to resolve the defined entity again
            try:
                self._sync_def_entity(cluster_id)
            except Exception:
                msg = f"Failed to sync defined entity for cluster {cluster_id}"  # noqa: E501
                LOGGER.error(msg, exc_info=True)
            self._update_task(vcd_client.TaskStatus.ERROR,
                              message=msg,
                              error_message=str(err))
        finally:
            # TODO re-organize updating defined entity and task update as per
            # https://stackoverflow.com/questions/49099637/how-to-determine-if-an-exception-was-raised-once-youre-in-the-finally-block
            # noqa: E501
            self.context.end()

    @utils.run_async
    def _create_nodes_async(self, cluster_id: str,
                            cluster_spec: def_models.NativeEntity):
        """Create worker and/or nfs nodes in vCD.

        This method is executed by a thread in an asynchronous manner.
        Do's:
        - Update the defined entity in except blocks.
        - Can set the self.task status either to Running or Error
        Dont's:
        - Do not set the self.task status to SUCCESS. This will prevent other
        parallel threads if any to update the status. vCD interprets SUCCESS
        as a terminal state.
        - Do not end the context.client.

        Let the caller monitor thread or method to set SUCCESS task status,
         end the client context
        """
        vapp = None
        cluster_name = ''
        rollback = False
        vapp_href = ''
        try:
            # get the current state of the defined entity
            curr_entity: def_models.DefEntity = self.entity_svc.get_entity(cluster_id)  # noqa: E501
            vapp_href = curr_entity.externalId
            cluster_name = curr_entity.entity.metadata.cluster_name
            org_name = curr_entity.entity.metadata.org_name
            ovdc_name = curr_entity.entity.metadata.ovdc_name
            curr_worker_count: int = curr_entity.entity.spec.workers.count
            curr_nfs_count: int = curr_entity.entity.spec.nfs.count

            # use the same settings with which cluster was originally created
            # viz., template, storage_profile, and network among others.
            worker_storage_profile = curr_entity.entity.spec.workers.storage_profile  # noqa: E501
            worker_sizing_class = curr_entity.entity.spec.workers.sizing_class
            nfs_storage_profile = curr_entity.entity.spec.nfs.storage_profile
            nfs_sizing_class = curr_entity.entity.spec.nfs.sizing_class
            network_name = curr_entity.entity.spec.settings.network
            ssh_key = curr_entity.entity.spec.settings.ssh_key
            rollback = cluster_spec.spec.settings.rollback_on_failure
            template_name = curr_entity.entity.spec.k8_distribution.template_name  # noqa: E501
            template_revision = curr_entity.entity.spec.k8_distribution.template_revision  # noqa: E501
            template = _get_template(template_name, template_revision)

            # compute the values of workers and nfs to be added or removed
            desired_worker_count: int = cluster_spec.spec.workers.count
            num_workers_to_add = desired_worker_count - curr_worker_count
            desired_nfs_count = cluster_spec.spec.nfs.count
            num_nfs_to_add = desired_nfs_count - curr_nfs_count

            server_config = utils.get_server_runtime_config()
            catalog_name = server_config['broker']['catalog']
            org = vcd_utils.get_org(self.context.client, org_name=org_name)
            ovdc = vcd_utils.get_vdc(self.context.client, vdc_name=ovdc_name, org=org)  # noqa: E501
            vapp = vcd_vapp.VApp(self.context.client, href=vapp_href)

            if num_workers_to_add > 0:
                msg = f"Creating {num_workers_to_add} workers from template" \
                      f"' {template_name}' (revision {template_revision}); " \
                      f"adding to cluster '{cluster_name}' ({cluster_id})"
                LOGGER.debug(msg)
                self._update_task(vcd_client.TaskStatus.RUNNING, message=msg)
                worker_nodes = _add_nodes(
                    self.context.sysadmin_client,
                    num_nodes=num_workers_to_add,
                    node_type=NodeType.WORKER,
                    org=org,
                    vdc=ovdc,
                    vapp=vapp,
                    catalog_name=catalog_name,
                    template=template,
                    network_name=network_name,
                    storage_profile=worker_storage_profile,
                    ssh_key=ssh_key,
                    sizing_class_name=worker_sizing_class)
                msg = f"Adding {num_workers_to_add} node(s) to cluster " \
                      f"{cluster_name}({cluster_id})"
                self._update_task(vcd_client.TaskStatus.RUNNING, message=msg)
                target_nodes = []
                for spec in worker_nodes['specs']:
                    target_nodes.append(spec['target_vm_name'])
                vapp.reload()
                _join_cluster(self.context.sysadmin_client,
                              vapp,
                              template[LocalTemplateKey.NAME],
                              template[LocalTemplateKey.REVISION],
                              target_nodes)
                msg = f"Added {num_workers_to_add} node(s) to cluster " \
                      f"{cluster_name}({cluster_id})"
                self._update_task(vcd_client.TaskStatus.RUNNING, message=msg)
            if num_nfs_to_add > 0:
                msg = f"Creating {num_nfs_to_add} nfs node(s) from template " \
                      f"'{template_name}' (revision {template_revision}) " \
                      f"for cluster '{cluster_name}' ({cluster_id})"
                LOGGER.debug(msg)
                self._update_task(vcd_client.TaskStatus.RUNNING, message=msg)
                _add_nodes(self.context.sysadmin_client,
                           num_nodes=num_nfs_to_add,
                           node_type=NodeType.NFS,
                           org=org,
                           vdc=ovdc,
                           vapp=vapp,
                           catalog_name=catalog_name,
                           template=template,
                           network_name=network_name,
                           storage_profile=nfs_storage_profile,
                           ssh_key=ssh_key,
                           sizing_class_name=nfs_sizing_class)
                msg = f"Created {num_nfs_to_add} nfs_node(s) for cluster " \
                      f"'{cluster_name}' ({cluster_id})"
                self._update_task(vcd_client.TaskStatus.RUNNING, message=msg)
            msg = f"Created {num_workers_to_add} workers & {num_nfs_to_add}" \
                  f" nfs nodes for '{cluster_name}' ({cluster_id}) "
            self._update_task(vcd_client.TaskStatus.RUNNING, message=msg)
        except (E.NodeCreationError, E.ClusterJoiningError) as err:
            msg = f"Error adding nodes to cluster '{cluster_name}'"
            LOGGER.error(msg, exc_info=True)
            if rollback:
                msg = f"Error adding nodes to cluster '{cluster_name}' " \
                      f"({cluster_id}). Deleting nodes: {err.node_names} " \
                      f"(rollback=True)"
                self._update_task(vcd_client.TaskStatus.RUNNING, message=msg)
                LOGGER.info(msg)
                try:
                    _delete_nodes(self.context.sysadmin_client,
                                  vapp_href,
                                  err.node_names,
                                  cluster_name=cluster_name)
                except Exception:
                    LOGGER.error(f"Failed to delete nodes {err.node_names} "
                                 f"from cluster '{cluster_name}'",
                                 exc_info=True)
            try:
                self._fail_operation(
                    cluster_id, DefEntityOperation.UPDATE)
            except Exception:
                msg = f"Failed to update defined entity status " \
                      f" for cluster {cluster_id}"
                LOGGER.error(msg, exc_info=True)

            # NOTE: Since the defined entity is assumed to be
            # resolved during cluster creation, there is no need
            # to resolve the defined entity again
            try:
                self._sync_def_entity(cluster_id, vapp=vapp)
            except Exception:
                msg = f"Failed to sync defined entity for cluster {cluster_id}"  # noqa: E501
                LOGGER.error(msg, exc_info=True)
            self._update_task(vcd_client.TaskStatus.ERROR,
                              message=msg,
                              error_message=str(err))
        except Exception as err:
            LOGGER.error(err, exc_info=True)
            msg = f"Error adding nodes to cluster '{cluster_name}'"
            try:
                self._fail_operation(
                    cluster_id, DefEntityOperation.UPDATE)
            except Exception:
                msg = f"Failed to update defined entity status " \
                      f" for cluster {cluster_id}"
                LOGGER.error(msg, exc_info=True)
            # NOTE: Since the defined entity is assumed to be
            # resolved during cluster creation, there is no need
            # to resolve the defined entity again
            try:
                self._sync_def_entity(cluster_id, vapp=vapp)
            except Exception:
                msg = f"Failed to sync defined entity for cluster {cluster_id}"  # noqa: E501
                LOGGER.error(msg, exc_info=True)
            self._update_task(vcd_client.TaskStatus.ERROR,
                              message=msg,
                              error_message=str(err))

    @utils.run_async
    def _delete_cluster_async(self, cluster_name, org_name, ovdc_name,
                              def_entity: def_models.DefEntity = None):
        """Delete the cluster asynchronously.

        :param cluster_name: Name of the cluster to be deleted.
        :param org_name: Name of the org where the cluster resides.
        :param ovdc_name: Name of the ovdc where the cluster resides.
        :param def_entity: Previously deleted defined entity object, which
        needs to be recreated in the failure case of cluster vapp deletion.
        """
        try:
            msg = f"Deleting cluster '{cluster_name}'"
            self._update_task(vcd_client.TaskStatus.RUNNING, message=msg)
            _delete_vapp(
                self.context.client, org_name, ovdc_name, cluster_name)

            # Handle deleting dnat rule is cluster is exposed
            exposed: bool = bool(def_entity) and def_entity.entity.status.exposed  # noqa: E501
            dnat_delete_success: bool = False
            if exposed:
                network_name: str = def_entity.entity.spec.settings.network
                cluster_id = def_entity.id
                try:
                    _handle_delete_expose_dnat_rule(
                        client=self.context.client,
                        org_name=org_name,
                        ovdc_name=ovdc_name,
                        network_name=network_name,
                        cluster_name=cluster_name,
                        cluster_id=cluster_id)
                    dnat_delete_success = True
                except Exception as err:
                    LOGGER.error(f'Failed to delete dnat rule for '
                                 f'{cluster_name} ({cluster_id}) with error: '
                                 f'{str(err)}')

            msg = f"Deleted cluster '{cluster_name}'"
            if exposed and not dnat_delete_success:
                msg += ' with failed dnat rule deletion'
            self._update_task(vcd_client.TaskStatus.SUCCESS, message=msg)
        except Exception as err:
            msg = f"Unexpected error while deleting cluster {cluster_name}"
            LOGGER.error(f"{msg}",
                         exc_info=True)
            self._update_task(vcd_client.TaskStatus.ERROR,
                              message=msg,
                              error_message=str(err))
        finally:
            # TODO re-organize updating defined entity and task update as per
            # https://stackoverflow.com/questions/49099637/how-to-determine-if-an-exception-was-raised-once-youre-in-the-finally-block
            # noqa: E501
            self.context.end()

    def _get_cluster_upgrade_plan(self, source_template_name, source_template_revision) -> List[dict]:  # noqa: E501
        """Get list of templates that a given cluster can upgrade to.

        :param str source_template_name:
        :param int source_template_revision:
        :return: List of dictionary containing templates
        :rtype: List[dict]
        """
        upgrades = []
        config = utils.get_server_runtime_config()
        for t in config['broker']['templates']:
            if source_template_name in t[LocalTemplateKey.UPGRADE_FROM]:
                if t[LocalTemplateKey.NAME] == source_template_name and \
                        int(t[LocalTemplateKey.REVISION]) <= source_template_revision: # noqa: E501
                    continue
                upgrades.append(t)

        return upgrades

    @utils.run_async
    def _upgrade_cluster_async(self, *args,
                               cluster_id: str,
                               template):
        vapp = None
        cluster_name = ''
        try:
            curr_entity: def_models.DefEntity = self.entity_svc.get_entity(cluster_id) # noqa: E501
            cluster_name = curr_entity.entity.metadata.cluster_name
            vapp_href = curr_entity.externalId

            # TODO use cluster status field to get the control plane and worker nodes  # noqa: E501
            vapp = vcd_vapp.VApp(self.context.client, href=vapp_href)
            all_node_names = [vm.get('name') for vm in vapp.get_all_vms() if not vm.get('name').startswith(NodeType.NFS)]  # noqa: E501
            control_plane_node_names = [curr_entity.entity.status.nodes.control_plane.name]  # noqa: E501
            worker_node_names = [worker.name for worker in curr_entity.entity.status.nodes.workers]  # noqa: E501

            template_name = template[LocalTemplateKey.NAME]
            template_revision = template[LocalTemplateKey.REVISION]

            # semantic version doesn't allow leading zeros
            # docker's version format YY.MM.patch allows us to directly use
            # lexicographical string comparison
            c_docker = curr_entity.entity.status.docker_version
            t_docker = template[LocalTemplateKey.DOCKER_VERSION]
            k8s_details = curr_entity.entity.status.kubernetes.split(' ')
            c_k8s = semver.Version(k8s_details[1])
            t_k8s = semver.Version(template[LocalTemplateKey.KUBERNETES_VERSION])  # noqa: E501
            cni_details = curr_entity.entity.status.cni.split(' ')
            c_cni = semver.Version(cni_details[1])
            t_cni = semver.Version(template[LocalTemplateKey.CNI_VERSION])

            upgrade_docker = t_docker > c_docker
            upgrade_k8s = t_k8s >= c_k8s
            upgrade_cni = t_cni > c_cni or t_k8s.major > c_k8s.major or t_k8s.minor > c_k8s.minor # noqa: E501

            if upgrade_k8s:
                msg = f"Draining control plane node {control_plane_node_names}"
                self._update_task(vcd_client.TaskStatus.RUNNING, message=msg)
                _drain_nodes(self.context.sysadmin_client, vapp_href,
                             control_plane_node_names, cluster_name=cluster_name)  # noqa: E501

                msg = f"Upgrading Kubernetes ({c_k8s} -> {t_k8s}) " \
                      f"in control plane node {control_plane_node_names}"
                self._update_task(vcd_client.TaskStatus.RUNNING, message=msg)
                filepath = ltm.get_script_filepath(template_name,
                                                   template_revision,
                                                   ScriptFile.CONTROL_PLANE_K8S_UPGRADE) # noqa: E501
                script = utils.read_data_file(filepath, logger=LOGGER)
                _run_script_in_nodes(self.context.sysadmin_client, vapp_href,
                                     control_plane_node_names, script)

                msg = f"Uncordoning control plane node {control_plane_node_names}"  # noqa: E501
                self._update_task(vcd_client.TaskStatus.RUNNING, message=msg)
                _uncordon_nodes(self.context.sysadmin_client,
                                vapp_href,
                                control_plane_node_names,
                                cluster_name=cluster_name)

                filepath = ltm.get_script_filepath(template_name,
                                                   template_revision,
                                                   ScriptFile.WORKER_K8S_UPGRADE) # noqa: E501
                script = utils.read_data_file(filepath, logger=LOGGER)
                for node in worker_node_names:
                    msg = f"Draining node {node}"
                    self._update_task(vcd_client.TaskStatus.RUNNING,
                                      message=msg)
                    _drain_nodes(self.context.sysadmin_client,
                                 vapp_href,
                                 [node],
                                 cluster_name=cluster_name)

                    msg = f"Upgrading Kubernetes ({c_k8s} " \
                          f"-> {t_k8s}) in node {node}"
                    self._update_task(vcd_client.TaskStatus.RUNNING,
                                      message=msg)
                    _run_script_in_nodes(self.context.sysadmin_client,
                                         vapp_href, [node], script)

                    msg = f"Uncordoning node {node}"
                    self._update_task(vcd_client.TaskStatus.RUNNING,
                                      message=msg)
                    _uncordon_nodes(self.context.sysadmin_client,
                                    vapp_href, [node],
                                    cluster_name=cluster_name)

            if upgrade_docker or upgrade_cni:
                msg = f"Draining all nodes {all_node_names}"
                self._update_task(vcd_client.TaskStatus.RUNNING, message=msg)
                _drain_nodes(self.context.sysadmin_client,
                             vapp_href, all_node_names,
                             cluster_name=cluster_name)

            if upgrade_docker:
                msg = f"Upgrading Docker-CE ({c_docker} -> {t_docker}) " \
                      f"in nodes {all_node_names}"
                self._update_task(vcd_client.TaskStatus.RUNNING, message=msg)
                filepath = ltm.get_script_filepath(template_name,
                                                   template_revision,
                                                   ScriptFile.DOCKER_UPGRADE)
                script = utils.read_data_file(filepath, logger=LOGGER)
                _run_script_in_nodes(self.context.sysadmin_client, vapp_href,
                                     all_node_names, script)

            if upgrade_cni:
                msg = "Applying CNI " \
                      f"({curr_entity.entity.status.cni} " \
                      f"-> {t_cni}) in control plane node {control_plane_node_names}"  # noqa: E501
                self._update_task(vcd_client.TaskStatus.RUNNING, message=msg)
                filepath = ltm.get_script_filepath(template_name,
                                                   template_revision,
                                                   ScriptFile.CONTROL_PLANE_CNI_APPLY)  # noqa: E501
                script = utils.read_data_file(filepath, logger=LOGGER)
                _run_script_in_nodes(self.context.sysadmin_client, vapp_href,
                                     control_plane_node_names, script)

            # uncordon all nodes (sometimes redundant)
            msg = f"Uncordoning all nodes {all_node_names}"
            self._update_task(vcd_client.TaskStatus.RUNNING, message=msg)
            _uncordon_nodes(self.context.sysadmin_client, vapp_href,
                            all_node_names, cluster_name=cluster_name)

            # update cluster metadata
            msg = f"Updating metadata for cluster '{cluster_name}'"
            self._update_task(vcd_client.TaskStatus.RUNNING, message=msg)
            metadata = {
                ClusterMetadataKey.TEMPLATE_NAME: template[LocalTemplateKey.NAME], # noqa: E501
                ClusterMetadataKey.TEMPLATE_REVISION: template[LocalTemplateKey.REVISION], # noqa: E501
                ClusterMetadataKey.DOCKER_VERSION: template[LocalTemplateKey.DOCKER_VERSION], # noqa: E501
                ClusterMetadataKey.KUBERNETES_VERSION: template[LocalTemplateKey.KUBERNETES_VERSION], # noqa: E501
                ClusterMetadataKey.CNI: template[LocalTemplateKey.CNI],
                ClusterMetadataKey.CNI_VERSION: template[LocalTemplateKey.CNI_VERSION] # noqa: E501
            }

            task = vapp.set_multiple_metadata(metadata)
            self.context.client.get_task_monitor().wait_for_status(task)

            # update defined entity of the cluster
            curr_entity.entity.spec.k8_distribution.template_name = \
                template[LocalTemplateKey.NAME]
            curr_entity.entity.spec.k8_distribution.template_revision = \
                int(template[LocalTemplateKey.REVISION])
            curr_entity.entity.status.cni = \
                _create_k8s_software_string(template[LocalTemplateKey.CNI],
                                            template[LocalTemplateKey.CNI_VERSION]) # noqa: E501
            curr_entity.entity.status.kubernetes = \
                _create_k8s_software_string(template[LocalTemplateKey.KUBERNETES], # noqa: E501
                                            template[LocalTemplateKey.KUBERNETES_VERSION]) # noqa: E501
            curr_entity.entity.status.docker_version = template[LocalTemplateKey.DOCKER_VERSION] # noqa: E501
            curr_entity.entity.status.os = template[LocalTemplateKey.OS]
            curr_entity.entity.status.phase = str(
                DefEntityPhase(DefEntityOperation.UPGRADE,
                               DefEntityOperationStatus.SUCCEEDED))
            self.entity_svc.update_entity(curr_entity.id, curr_entity)

            msg = f"Successfully upgraded cluster '{cluster_name}' software " \
                  f"to match template {template_name} (revision " \
                  f"{template_revision}): Kubernetes: {c_k8s} -> {t_k8s}, " \
                  f"Docker-CE: {c_docker} -> {t_docker}, " \
                  f"CNI: {c_cni} -> {t_cni}"
            self._update_task(vcd_client.TaskStatus.SUCCESS, message=msg)
            LOGGER.info(f"{msg} ({vapp_href})")
        except Exception as err:
            msg = f"Unexpected error while upgrading cluster " \
                  f"'{cluster_name}'"
            LOGGER.error(f"{msg}", exc_info=True)
            try:
                self._fail_operation(
                    cluster_id,
                    DefEntityOperation.UPGRADE)
            except Exception:
                msg = f"Failed to update defined entity status " \
                      f" for cluster {cluster_id}"
                LOGGER.error(f"{msg}", exc_info=True)
            # NOTE: Since the defined entity is assumed to be
            # resolved during cluster creation, there is no need
            # to resolve the defined entity again
            try:
                self._sync_def_entity(cluster_id, vapp=vapp)
            except Exception:
                msg = f"Failed to sync defined entity of the cluster {cluster_id}" # noqa: E501
                LOGGER.error(f"{msg}", exc_info=True)
            self._update_task(vcd_client.TaskStatus.ERROR,
                              message=msg, error_message=str(err))

        finally:
            # TODO re-organize updating defined entity and task update as per
            # https://stackoverflow.com/questions/49099637/how-to-determine-if-an-exception-was-raised-once-youre-in-the-finally-block
            # noqa: E501
            self.context.end()

    @utils.run_async
    def _monitor_delete_nodes(self, cluster_id, nodes_to_del):
        """Triggers and monitors delete thread.

        This method (or) thread waits for the thread(s) to join before
        - updating the defined entity
        - updating the task status to SUCCESS
        - ending the client context
        """
        cluster_name = ''
        try:
            curr_entity: def_models.DefEntity = self.entity_svc.get_entity(
                cluster_id)
            cluster_name: str = curr_entity.name
            self._delete_nodes_async(cluster_id=cluster_id,
                                     nodes_to_del=nodes_to_del)

            # wait for the children threads of the current thread to join
            curr_thread_id = str(threading.current_thread().ident)
            for t in threading.enumerate():
                if t.getName().endswith(curr_thread_id):
                    t.join()

            # update the defined entity and task status.
            curr_task_status = self.task_resource.get('status')
            if curr_task_status == vcd_client.TaskStatus.ERROR.value:
                curr_entity.entity.status.phase = str(
                    DefEntityPhase(DefEntityOperation.UPDATE,
                                   DefEntityOperationStatus.FAILED))
            else:
                msg = f"Deleted the {nodes_to_del} nodes  from cluster " \
                      f"'{cluster_name}' ({cluster_id}) "
                self._update_task(vcd_client.TaskStatus.SUCCESS, message=msg)
                curr_entity.entity.status.phase = str(
                    DefEntityPhase(DefEntityOperation.UPDATE,
                                   DefEntityOperationStatus.SUCCEEDED))
            self._sync_def_entity(cluster_id, curr_entity)
        except Exception as err:
            msg = f"Unexpected error while deleting nodes for " \
                  f"{cluster_name} ({cluster_id})"
            LOGGER.error(f"{msg}",
                         exc_info=True)
            try:
                self._fail_operation(
                    cluster_id,
                    DefEntityOperation.UPDATE)
            except Exception:
                msg = f"Failed to update defined entity status " \
                      f" for cluster {cluster_id}"
                LOGGER.error(f"{msg}", exc_info=True)
            # NOTE: Since the defined entity is assumed to be
            # resolved during cluster creation, there is no need
            # to resolve the defined entity again
            try:
                self._sync_def_entity(cluster_id)
            except Exception:
                msg = f"Failed to sync defined entity of the cluster {cluster_id}" # noqa: E501
                LOGGER.error(f"{msg}", exc_info=True)
            self._update_task(vcd_client.TaskStatus.ERROR,
                              message=msg,
                              error_message=str(err))
        finally:
            # TODO re-organize updating defined entity and task update as per
            # https://stackoverflow.com/questions/49099637/how-to-determine-if-an-exception-was-raised-once-youre-in-the-finally-block
            # noqa: E501
            self.context.end()

    @utils.run_async
    def _delete_nodes_async(self, cluster_id: str,
                            cluster_spec: def_models.NativeEntity = None,
                            nodes_to_del=None):
        """Delete worker and/or nfs nodes in vCD.

        This method is executed by a thread in an asynchronous manner.
        Do's:
        - Update the defined entity in except blocks.
        - Set the self.task status either to Running or Error
        Dont's:
        - Do not set the self.task status to SUCCESS. This will prevent other
        parallel threads if any to update the status. vCD interprets SUCCESS
        as a terminal state.
        - Do not end the context.client.

        Let the caller monitor thread or method to set SUCCESS task status,
          end the client context
        """
        if nodes_to_del is None:
            nodes_to_del = []
        curr_entity: def_models.DefEntity = self.entity_svc.get_entity(cluster_id)  # noqa: E501
        vapp_href = curr_entity.externalId
        cluster_name = curr_entity.entity.metadata.cluster_name

        if not nodes_to_del:
            if not cluster_spec:
                raise E.CseServerError(f"No nodes specified to delete for "
                                       f"cluster {cluster_name}({cluster_id})")
            desired_worker_count = cluster_spec.spec.workers.count
            nodes_to_del = [node.name for node in
                            curr_entity.entity.status.nodes.workers[desired_worker_count:]]  # noqa: E501

        vapp = vcd_vapp.VApp(self.context.client, href=vapp_href)
        try:
            # if nodes fail to drain, continue with node deletion anyways
            try:
                worker_nodes_to_delete = [
                    node_name for node_name in nodes_to_del
                    if node_name.startswith(NodeType.WORKER)]
                if worker_nodes_to_delete:
                    msg = f"Draining {len(worker_nodes_to_delete)} node(s) " \
                          f"from cluster '{cluster_name}': " \
                          f"{worker_nodes_to_delete}"
                    self._update_task(
                        vcd_client.TaskStatus.RUNNING, message=msg)
                    _drain_nodes(self.context.sysadmin_client,
                                 vapp_href,
                                 worker_nodes_to_delete,
                                 cluster_name=cluster_name)
            except (E.NodeOperationError, E.ScriptExecutionError) as err:
                LOGGER.warning(f"Failed to drain nodes: {nodes_to_del}"
                               f" in cluster '{cluster_name}'."
                               f" Continuing node delete...\nError: {err}")

            msg = f"Deleting {len(nodes_to_del)} node(s) from " \
                  f"cluster '{cluster_name}': {nodes_to_del}"
            self._update_task(vcd_client.TaskStatus.RUNNING, message=msg)

            _delete_nodes(self.context.sysadmin_client,
                          vapp_href,
                          nodes_to_del,
                          cluster_name=cluster_name)

            msg = f"Deleted {len(nodes_to_del)} node(s)" \
                  f" to cluster '{cluster_name}'"
            self._update_task(vcd_client.TaskStatus.RUNNING, message=msg)
        except Exception as err:
            msg = f"Unexpected error while deleting nodes {nodes_to_del}"
            LOGGER.error(f"{msg}",
                         exc_info=True)
            try:
                self._fail_operation(
                    cluster_id,
                    DefEntityOperation.UPDATE)
            except Exception:
                msg = f"Failed to update defined entity status " \
                      f" for cluster {cluster_id}"
                LOGGER.error(f"{msg}", exc_info=True)
            # NOTE: Since the defined entity is assumed to be
            # resolved during cluster creation, there is no need
            # to resolve the defined entity again
            try:
                self._sync_def_entity(cluster_id, vapp=vapp)
            except Exception:
                msg = f"Failed to sync defined entity of the cluster {cluster_id}" # noqa: E501
                LOGGER.error(f"{msg}", exc_info=True)
            self._update_task(vcd_client.TaskStatus.ERROR,
                              message=msg,
                              error_message=str(err))

    def _sync_def_entity(self, cluster_id, curr_entity=None, vapp=None):
        """Sync the defined entity with the latest vApp status."""
        # NOTE: Do not use this function to update defined entities unless
        # it is sure that the underlying VApp for the cluster exists.
        if not curr_entity:
            curr_entity: def_models.DefEntity = self.entity_svc.get_entity(
                cluster_id)
        if not vapp:
            vapp = vcd_vapp.VApp(self.context.client, href=curr_entity.externalId)  # noqa: E501
        curr_nodes_status = _get_nodes_details(
            self.context.sysadmin_client, vapp)
        if curr_nodes_status:
            # Retrieve external ip for exposed NSX-T cluster
            if curr_entity.entity.status.exposed and \
                    curr_entity.entity.status.nodes and \
                    curr_entity.entity.status.nodes.control_plane:
                curr_nodes_status.control_plane.ip = curr_entity.entity.status.nodes.control_plane.ip  # noqa: E501

            curr_entity.entity.spec.workers.count = len(
                curr_nodes_status.workers)
            curr_entity.entity.spec.nfs.count = len(curr_nodes_status.nfs)
            curr_entity.entity.status.nodes = curr_nodes_status
        return self.entity_svc.update_entity(cluster_id, curr_entity)

    def _fail_operation(self, cluster_id: str, op: DefEntityOperation):
        def_entity: def_models.DefEntity = self.entity_svc.get_entity(cluster_id)  # noqa: E501
        def_entity.entity.status.phase = \
            str(DefEntityPhase(op, DefEntityOperationStatus.FAILED))
        self.entity_svc.update_entity(cluster_id, def_entity)

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
        if not self.context.client.is_sysadmin():
            stack_trace = ''

        if self.task is None:
            self.task = vcd_task.Task(self.context.sysadmin_client)

        org = vcd_utils.get_org(self.context.client)
        user_href = org.get_user(self.context.user.name).get('href')

        # Wait for the thread-1 to finish updating the task, before thread-2 in
        # the line can read the current status of the task.
        # It is safe for thread-2 to check the current task status before
        # updating it. A task with a terminal state of SUCCESS or ERROR cannot
        # be further updated; vCD will throw an error.
        with self.task_update_lock:
            task_href = None
            if self.task_resource is not None:
                task_href = self.task_resource.get('href')
                curr_task_status = self.task_resource.get('status')
                if curr_task_status == vcd_client.TaskStatus.SUCCESS.value or \
                        curr_task_status == vcd_client.TaskStatus.ERROR.value:
                    # TODO Log the message here.
                    return
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

    def _replace_kubeconfig_expose_ip(self, internal_ip: str, cluster_id: str,
                                      vapp: vcd_vapp.VApp):
        # Form kubeconfig with internal ip
        expose_kubeconfig = self.get_cluster_config(cluster_id)
        internal_ip_kubeconfig = re.sub(
            pattern=IP_PORT_REGEX,
            repl=f'{internal_ip}:6443',
            string=str(expose_kubeconfig))

        # Output new kubeconfig
        script = f"#!/usr/bin/env bash\n" \
                 f"echo \'{internal_ip_kubeconfig}\' > " \
                 f"{CSE_CLUSTER_KUBECONFIG_PATH}\n"
        node_names = _get_node_names(vapp, NodeType.CONTROL_PLANE)
        result = _execute_script_in_nodes(self.context.sysadmin_client,
                                          vapp=vapp,
                                          node_names=node_names,
                                          script=script,
                                          check_tools=True)

        errors = _get_script_execution_errors(result)
        if errors:
            raise E.ScriptExecutionError(
                f"Failed to overwrite kubeconfig with internal ip: "
                f"{internal_ip}: {errors}")


def _get_nodes_details(sysadmin_client, vapp):
    """Get the details of the nodes given a vapp.

    This method should not raise an exception. It is being used in the
    exception blocks to sync the defined entity status of any given cluster
    It returns None in the case of any unexpected errors.

    :param pyvcloud.client.Client sysadmin_client:
    :param pyvcloud.vapp.VApp vapp: vApp

    :return: Node details
    :rtype: container_service_extension.def_.models.Nodes
    """
    try:
        vms = vapp.get_all_vms()
        workers = []
        nfs_nodes = []
        control_plane = None
        for vm in vms:
            # skip processing vms in 'unresolved' state.
            if int(vm.get('status')) == 0:
                continue
            vm_name = vm.get('name')
            ip = None
            try:
                ip = vapp.get_primary_ip(vm_name)
            except Exception:
                LOGGER.error(f"Failed to retrieve the IP of the node "
                             f"{vm_name} in cluster {vapp.name}",
                             exc_info=True)
            sizing_class = None
            if hasattr(vm, 'ComputePolicy') and hasattr(vm.ComputePolicy,
                                                        'VmSizingPolicy'):
                policy_name = vm.ComputePolicy.VmSizingPolicy.get('name')
                sizing_class = compute_policy_manager.\
                    get_cse_policy_display_name(policy_name)
            if vm_name.startswith(NodeType.CONTROL_PLANE):
                control_plane = def_models.Node(name=vm_name, ip=ip,
                                                sizing_class=sizing_class)
            elif vm_name.startswith(NodeType.WORKER):
                workers.append(
                    def_models.Node(name=vm_name, ip=ip,
                                    sizing_class=sizing_class))
            elif vm_name.startswith(NodeType.NFS):
                exports = None
                try:
                    exports = _get_nfs_exports(sysadmin_client,
                                               ip,
                                               vapp,
                                               vm_name)
                except Exception:
                    LOGGER.error(f"Failed to retrieve the NFS exports of "
                                 f"node {vm_name} of cluster {vapp.name} ",
                                 exc_info=True)
                nfs_nodes.append(def_models.NfsNode(name=vm_name, ip=ip,
                                                    sizing_class=sizing_class,
                                                    exports=str(exports)))
        return def_models.Nodes(control_plane=control_plane, workers=workers,
                                nfs=nfs_nodes)
    except Exception as err:
        LOGGER.error("Failed to retrieve the status of the nodes of the "
                     f"cluster {vapp.name}: {err}", exc_info=True)


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
        LOGGER.error(f"Failed to drain nodes {node_names} in cluster "
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
        LOGGER.error(f"Failed to uncordon nodes {node_names} in cluster "
                     f"'{cluster_name}' (vapp: {vapp_href}) "
                     f"with error: {err}")
        raise

    LOGGER.debug(f"Successfully uncordoned nodes {node_names} in cluster "
                 f"'{cluster_name}' (vapp: {vapp_href})")


def _delete_vapp(client, org_name, ovdc_name, vapp_name):
    LOGGER.debug(
        f"Deleting vapp {vapp_name} in (org: {org_name}, vdc: {ovdc_name})")

    vdc_href = ""
    try:
        org = vcd_org.Org(client=client,
                          resource=client.get_org_by_name(org_name))
        vdc_resource = org.get_vdc(name=ovdc_name)
        vdc_href = vdc_resource.get('href')
        vdc = VDC(client, href=vdc_href)
        task = vdc.delete_vapp(vapp_name, force=True)
        client.get_task_monitor().wait_for_status(task)
    except Exception as err:
        LOGGER.error(f"Failed to delete vapp {vapp_name} "
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
        LOGGER.error(f"Failed to delete node(s) {node_names} from cluster "
                     f"'{cluster_name}' using kubectl "
                     f"(vapp: {vapp_href}): {err}", exc_info=True)

    vapp = vcd_vapp.VApp(sysadmin_client, href=vapp_href)
    for vm_name in node_names:
        vm = vcd_vm.VM(sysadmin_client, resource=vapp.get_vm(vm_name))
        try:
            task = vm.undeploy()
            sysadmin_client.get_task_monitor().wait_for_status(task)
        except Exception:
            LOGGER.error(f"Failed to undeploy VM {vm_name} "
                         f"(vapp: {vapp_href})", exc_info=True)

    task = vapp.delete_vms(node_names)
    sysadmin_client.get_task_monitor().wait_for_status(task)
    LOGGER.debug(f"Successfully deleted node(s) {node_names} from "
                 f"cluster '{cluster_name}' (vapp: {vapp_href})")


def _is_valid_cluster_name(name):
    """Validate that the cluster name against the pattern."""
    if name and len(name) > 25:
        return False
    return re.match("^[a-zA-Z][A-Za-z0-9-]*$", name) is not None


def _cluster_exists(client, cluster_name, org_name=None, ovdc_name=None):
    query_filter = f'name=={urllib.parse.quote(cluster_name)}'
    if ovdc_name is not None:
        query_filter += f";vdcName=={urllib.parse.quote(ovdc_name)}"
    resource_type = vcd_client.ResourceType.VAPP.value
    if client.is_sysadmin():
        resource_type = vcd_client.ResourceType.ADMIN_VAPP.value
        if org_name is not None and org_name.lower() != SYSTEM_ORG_NAME.lower(): # noqa: E501
            org_resource = client.get_org_by_name(org_name)
            org = vcd_org.Org(client, resource=org_resource)
            query_filter += f";org=={urllib.parse.quote(org.resource.get('id'))}"  # noqa: E501

    q = client.get_typed_query(
        resource_type,
        query_result_format=vcd_client.QueryResultFormat.ID_RECORDS,
        qfilter=query_filter)
    result = q.execute()

    return len(list(result)) != 0


def _get_template(name=None, revision=None):
    if (name is None and revision is not None) or (name is not None and revision is None): # noqa: E501
        raise ValueError("If template revision is specified, then template "
                         "name must also be specified (and vice versa).")
    server_config = utils.get_server_runtime_config()
    name = name or server_config['broker']['default_template_name']
    revision = revision or server_config['broker']['default_template_revision']
    for template in server_config['broker']['templates']:
        if (template[LocalTemplateKey.NAME], str(template[LocalTemplateKey.REVISION])) == (name, str(revision)): # noqa: E501
            return template
    raise Exception(f"Template '{name}' at revision {revision} not found.")


def _add_nodes(sysadmin_client, num_nodes, node_type, org, vdc, vapp,
               catalog_name, template, network_name, storage_profile=None,
               ssh_key=None, sizing_class_name=None):
    vcd_utils.raise_error_if_user_not_from_system_org(sysadmin_client)

    if num_nodes > 0:
        specs = []
        try:
            # DEV NOTE: With api v33.0 and onwards, get_catalog operation will fail  # noqa: E501
            # for non admin users of an an org which is not hosting the catalog,  # noqa: E501
            # even if the catalog is explicitly shared with the org in question.  # noqa: E501
            # This happens because for api v 33.0 and onwards, the Org XML no
            # longer returns the href to catalogs accessible to the org, and typed  # noqa: E501
            # queries hide the catalog link from non admin users.
            # As a workaround, we will use a sys admin client to get the href and  # noqa: E501
            # pass it forward. Do note that the catalog itself can still be
            # accessed by these non admin users, just that they can't find by the  # noqa: E501
            # href on their own.

            org_name = org.get_name()
            org_resource = sysadmin_client.get_org_by_name(org_name)
            org_sa = vcd_org.Org(sysadmin_client, resource=org_resource)
            catalog_item = org_sa.get_catalog_item(
                catalog_name, template[LocalTemplateKey.CATALOG_ITEM_NAME])
            catalog_item_href = catalog_item.Entity.get('href')

            source_vapp = vcd_vapp.VApp(sysadmin_client, href=catalog_item_href)  # noqa: E501
            source_vm = source_vapp.get_all_vms()[0].get('name')
            if storage_profile is not None:
                storage_profile = vdc.get_storage_profile(storage_profile)

            config = utils.get_server_runtime_config()
            cpm = compute_policy_manager.ComputePolicyManager(sysadmin_client,
                                                              log_wire=utils.str_to_bool(config['service']['log_wire']))  # noqa: E501
            sizing_class_href = None
            if sizing_class_name:
                vdc_resource = vdc.get_resource()
                for policy in cpm.list_vdc_sizing_policies_on_vdc(vdc_resource.get('id')):  # noqa: E501
                    if policy['name'] == sizing_class_name:
                        if not sizing_class_href:
                            sizing_class_href = policy['href']
                        else:
                            msg = f"Duplicate sizing policies with the name {sizing_class_name}"  # noqa: E501
                            LOGGER.error(msg)
                            raise Exception(msg)
                if not sizing_class_href:
                    msg = f"No sizing policy with the name {sizing_class_name} exists on the VDC"  # noqa: E501
                    LOGGER.error(msg)
                    raise Exception(msg)
                LOGGER.debug(f"Found sizing policy with name {sizing_class_name} on the VDC {vdc_resource.get('name')}")  # noqa: E501

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
                if sizing_class_href:
                    spec['sizing_policy_href'] = sizing_class_href
                    spec['placement_policy_href'] = config['placement_policy_hrefs'][template[LocalTemplateKey.KIND]]  # noqa: E501
                if cust_script is not None:
                    spec['cust_script'] = cust_script
                if storage_profile:
                    spec['storage_profile'] = storage_profile
                specs.append(spec)

            task = vapp.add_vms(specs, power_on=False)
            sysadmin_client.get_task_monitor().wait_for_status(task)
            vapp.reload()

            for spec in specs:
                vm_name = spec['target_vm_name']
                vm_resource = vapp.get_vm(vm_name)
                vm = vcd_vm.VM(sysadmin_client, resource=vm_resource)

                task = vm.power_on()
                sysadmin_client.get_task_monitor().wait_for_status(task)
                vapp.reload()

                if node_type == NodeType.NFS:
                    LOGGER.debug(f"Enabling NFS server on {vm_name}")
                    script_filepath = ltm.get_script_filepath(
                        template[LocalTemplateKey.NAME],
                        template[LocalTemplateKey.REVISION],
                        ScriptFile.NFSD)
                    script = utils.read_data_file(script_filepath, logger=LOGGER)  # noqa: E501
                    exec_results = _execute_script_in_nodes(
                        sysadmin_client, vapp=vapp, node_names=[vm_name],
                        script=script)
                    errors = _get_script_execution_errors(exec_results)
                    if errors:
                        raise E.ScriptExecutionError(
                            f"VM customization script execution failed "
                            f"on node {vm_name}:{errors}")
        except Exception as err:
            LOGGER.error(err, exc_info=True)
            # TODO: get details of the exception to determine cause of failure,
            # e.g. not enough resources available.
            node_list = [entry.get('target_vm_name') for entry in specs]
            if hasattr(err, 'vcd_error') and err.vcd_error is not None and \
                    "throwPolicyNotAvailableException" in err.vcd_error.get('stackTrace', ''):  # noqa: E501
                raise E.NodeCreationError(node_list,
                                          f"OVDC not enabled for {template[LocalTemplateKey.KIND]}")  # noqa: E501

            raise E.NodeCreationError(node_list, str(err))

        vapp.reload()
        return {'task': task, 'specs': specs}


def _get_node_names(vapp, node_type):
    return [vm.get('name') for vm in vapp.get_all_vms() if vm.get('name').startswith(node_type)] # noqa: E501


def _get_control_plane_ip(sysadmin_client: vcd_client.Client, vapp,
                          check_tools=False, use_ubuntu_20_sleep=False):
    vcd_utils.raise_error_if_user_not_from_system_org(sysadmin_client)

    LOGGER.debug(f"Getting control_plane IP for vapp: "
                 f"{vapp.get_resource().get('name')}")
    script = "#!/usr/bin/env bash\n" \
             "ip route get 1 | awk '{print $NF;exit}'\n" \

    node_names = _get_node_names(vapp, NodeType.CONTROL_PLANE)
    result = _execute_script_in_nodes(sysadmin_client, vapp=vapp,
                                      node_names=node_names, script=script,
                                      check_tools=check_tools,
                                      use_ubuntu_20_sleep=use_ubuntu_20_sleep)
    errors = _get_script_execution_errors(result)
    if errors:
        raise E.ScriptExecutionError(f"Get control plane IP script execution "
                                     f"failed on control plane node "
                                     f"{node_names}:{errors}")
    control_plane_ip = result[0][1].content.decode().split()[0]
    LOGGER.debug(f"Retrieved control plane IP for vapp: "
                 f"{vapp.get_resource().get('name')}, ip: {control_plane_ip}")
    return control_plane_ip


def _init_cluster(sysadmin_client: vcd_client.Client, vapp, template_name,
                  template_revision, expose_ip=None):
    vcd_utils.raise_error_if_user_not_from_system_org(sysadmin_client)

    try:
        script_filepath = ltm.get_script_filepath(template_name,
                                                  template_revision,
                                                  ScriptFile.CONTROL_PLANE)
        script = utils.read_data_file(script_filepath, logger=LOGGER)

        # Expose cluster if given external ip
        if expose_ip:
            script = _form_expose_ip_init_cluster_script(script, expose_ip)
        if TKGM_TEMPLATE_NAME_FRAGMENT in template_name:
            script = script.format(
                pod_network_cidr=TKGM_DEFAULT_POD_NETWORK_CIDR,
                service_cidr=TKGM_DEFAULT_SERVICE_CIDR)

        node_names = _get_node_names(vapp, NodeType.CONTROL_PLANE)
        result = _execute_script_in_nodes(sysadmin_client, vapp=vapp,
                                          node_names=node_names, script=script)
        errors = _get_script_execution_errors(result)
        if errors:
            raise E.ScriptExecutionError(
                f"Initialize cluster script execution failed on node "
                f"{node_names}:{errors}")
        if result[0][0] != 0:
            raise E.ClusterInitializationError(f"Couldn't initialize cluster:\n{result[0][2].content.decode()}") # noqa: E501
    except Exception as err:
        LOGGER.error(err, exc_info=True)
        raise E.ClusterInitializationError(
            f"Couldn't initialize cluster: {str(err)}")


def _form_expose_ip_init_cluster_script(script: str, expose_ip: str):
    """Form init cluster script with expose ip control plane endpoint option.

    If the '--control-plane-endpoint' option is already present, this option
    will be replaced with this option specifying the exposed ip. If this option
    is not specified, the '--control-plane-endpoint' option will be added.

    :param str script: the init cluster script
    :param str expose_ip: the ip to expose the cluster

    :return: the updated init cluster script
    :rtype: str
    """
    # Get line with 'kubeadm init'
    kubeadm_init_match: re.Match = re.search('kubeadm init .+\n', script)
    if not kubeadm_init_match:
        return script
    kubeadm_init_line: str = kubeadm_init_match.group(0)

    # Either add or replace the control plane endpoint option
    expose_control_plane_endpoint_option = f'--control-plane-endpoint=\"{expose_ip}:6443\"'  # noqa: E501
    expose_kubeadm_init_line = re.sub(
        f'--control-plane-endpoint={IP_PORT_REGEX}',
        expose_control_plane_endpoint_option,
        kubeadm_init_line)
    if kubeadm_init_line == expose_kubeadm_init_line:  # no option was replaced
        expose_kubeadm_init_line = kubeadm_init_line.replace(
            'kubeadm init',
            f'kubeadm init --control-plane-endpoint=\"{expose_ip}:6443\"')

    # Replace current kubeadm init line with line containing expose_ip
    return script.replace(kubeadm_init_line, expose_kubeadm_init_line)


def _join_cluster(sysadmin_client: vcd_client.Client, vapp, template_name,
                  template_revision, target_nodes=None):
    vcd_utils.raise_error_if_user_not_from_system_org(sysadmin_client)
    is_tkgm = TKGM_TEMPLATE_NAME_FRAGMENT in template_name
    time.sleep(40)  # hack for waiting for joining cluster
    try:
        if is_tkgm:
            script = "#!/usr/bin/env bash\n" \
                     "kubeadm token create --print-join-command\n" \
                     "ip route get 1 | awk '{print $NF;exit}'\n"
        else:
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
            raise E.ClusterJoiningError(
                "Join cluster script execution failed on "
                f"control plane node {node_names}:{errors}")
        join_info = control_plane_result[0][1].content.decode().split()

        node_names = _get_node_names(vapp, NodeType.WORKER)
        if target_nodes is not None:
            node_names = [name for name in node_names if name in target_nodes]
        tmp_script_filepath = ltm.get_script_filepath(template_name,
                                                      template_revision,
                                                      ScriptFile.NODE)
        tmp_script = utils.read_data_file(tmp_script_filepath, logger=LOGGER)
        if is_tkgm:
            script = tmp_script.format(
                ip_port=join_info[2],
                token=join_info[4],
                discovery_token_ca_cert_hash=join_info[6])
        else:
            script = tmp_script.format(token=join_info[0], ip=join_info[1])
        worker_results = _execute_script_in_nodes(sysadmin_client, vapp=vapp,
                                                  node_names=node_names,
                                                  script=script)
        errors = _get_script_execution_errors(worker_results)
        if errors:
            raise E.ClusterJoiningError(
                "Join cluster script execution failed "
                f"on worker node  {node_names}:{errors}")
        for result in worker_results:
            if result[0] != 0:
                raise E.ClusterJoiningError(f"Couldn't join cluster:"
                                            f"\n{result[2].content.decode()}")
    except Exception as err:
        LOGGER.error(err, exc_info=True)
        raise E.ClusterJoiningError(f"Couldn't join cluster: {str(err)}")


def _wait_for_tools_ready_callback(message, exception=None):
    LOGGER.debug(f"waiting for guest tools, status: {message}")
    if exception is not None:
        LOGGER.error(f"exception: {str(exception)}")


def _wait_for_guest_execution_callback(message, exception=None):
    LOGGER.debug(message)
    if exception is not None:
        LOGGER.error(f"exception: {str(exception)}")


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
        raise E.CseServerError('VM is not ready to execute scripts')


def _execute_script_in_nodes(sysadmin_client: vcd_client.Client,
                             vapp, node_names, script,
                             check_tools=True, wait=True,
                             use_ubuntu_20_sleep=False):
    vcd_utils.raise_error_if_user_not_from_system_org(sysadmin_client)
    all_results = []
    if use_ubuntu_20_sleep:
        time.sleep(150)  # hack for ubuntu 20 cluster creation
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
        except Exception as err:
            raise E.ScriptExecutionError(f"Error executing script in node {node_name}: {str(err)}")  # noqa: E501

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
        raise E.ScriptExecutionError(f"Script execution failed on node "
                                     f"{node_names}\nErrors: {errors}")
    if results[0][0] != 0:
        raise E.NodeOperationError(f"Error during node operation:\n"
                                   f"{results[0][2].content.decode()}")


def _get_script_execution_errors(results):
    return [result[2].content.decode() for result in results if result[0] != 0]


def _create_k8s_software_string(software_name: str, software_version: str) -> str: # noqa: E501
    """Generate string containing the software name and version.

    Example: if software_name is "upstream" and version is "1.17.3",
        "upstream 1.17.3" is returned

    :param str software_name:
    :param str software_version:
    :rtype: str
    """
    return f"{software_name} {software_version}"


def _get_vdc_network_response(cloudapi_client, network_urn_id: str):
    relative_path = f'{cloudapi_constants.CloudApiResource.ORG_VDC_NETWORKS}' \
                    f'?filter=id=={network_urn_id}'
    response = cloudapi_client.do_request(
        method=RequestMethod.GET,
        cloudapi_version=cloudapi_constants.CloudApiVersion.VERSION_1_0_0,
        resource_url_relative_path=relative_path)
    return response


def _get_gateway_href(vdc: VDC, gateway_name):
    edge_gateways = vdc.list_edge_gateways()
    for gateway_dict in edge_gateways:
        if gateway_dict['name'] == gateway_name:
            return gateway_dict['href']
    return None


def _get_gateway(client: vcd_client.Client, org_name: str, ovdc_name: str,
                 network_name: str):
    # Check if routed org vdc network
    cloudapi_client = vcd_utils.get_cloudapi_client_from_vcd_client(client)
    ovdc = vcd_utils.get_vdc(client, org_name=org_name, vdc_name=ovdc_name)
    try:
        routed_network_resource = ovdc.get_routed_orgvdc_network(network_name)
    except EntityNotFoundException:
        raise Exception(f'No routed network found named: {network_name} '
                        f'in ovdc {ovdc_name} and org {org_name}')

    routed_vdc_network = vdc_network.VdcNetwork(
        client=client,
        resource=routed_network_resource)
    network_id = utils.extract_id_from_href(routed_vdc_network.href)
    network_urn_id = f'{NETWORK_URN_PREFIX}:{network_id}'
    try:
        vdc_network_response = _get_vdc_network_response(
            cloudapi_client, network_urn_id)
    except Exception:
        return None
    gateway_name = vdc_network_response[VdcNetworkInfoKey.VALUES][0][
        VdcNetworkInfoKey.CONNECTION][VdcNetworkInfoKey.ROUTER_REF][
        VdcNetworkInfoKey.NAME]
    gateway_href = _get_gateway_href(ovdc, gateway_name)
    gateway = vcd_gateway.Gateway(client, name=gateway_name, href=gateway_href)
    return gateway


def _get_nsxt_backed_gateway_service(client: vcd_client.Client, org_name: str,
                                     ovdc_name: str, network_name: str):
    # Check if NSX-T backed gateway
    gateway: vcd_gateway.Gateway = _get_gateway(
        client=client,
        org_name=org_name,
        ovdc_name=ovdc_name,
        network_name=network_name)
    if not gateway:
        raise Exception(f'No gateway found for network: {network_name}')
    if not gateway.is_nsxt_backed():
        raise Exception('Gateway is not NSX-T backed for exposing cluster.')

    return NsxtBackedGatewayService(gateway, client)


def _form_expose_dnat_rule_name(cluster_name: str, cluster_id: str):
    """Form dnat rule name for expose cluster.

    Dnat rule name includes cluster name to show users the cluster rule
    corresponds to. The cluster id is used to make the name unique
    """
    return f"{cluster_name}_{cluster_id}_{EXPOSE_CLUSTER_NAME_FRAGMENT}"


def _expose_cluster(client: vcd_client.Client, org_name: str, ovdc_name: str,
                    network_name: str, cluster_name: str, cluster_id: str,
                    internal_ip: str):

    # Auto reserve ip and add dnat rule
    nsxt_gateway_svc = _get_nsxt_backed_gateway_service(
        client, org_name, ovdc_name, network_name)
    expose_ip = nsxt_gateway_svc.get_available_ip()
    if not expose_ip:
        raise Exception(f'No available ips found for cluster {cluster_name} ({cluster_id})')  # noqa: E501
    try:
        dnat_rule_name = _form_expose_dnat_rule_name(cluster_name, cluster_id)
        nsxt_gateway_svc.add_dnat_rule(
            name=dnat_rule_name,
            internal_address=internal_ip,
            external_address=expose_ip)
    except Exception as err:
        raise Exception(f'Unable to add dnat rule with error: {str(err)}')
    return expose_ip


def _handle_delete_expose_dnat_rule(client: vcd_client.Client,
                                    org_name: str,
                                    ovdc_name: str,
                                    network_name: str,
                                    cluster_name: str,
                                    cluster_id: str):
    nsxt_gateway_svc = _get_nsxt_backed_gateway_service(
        client, org_name, ovdc_name, network_name)
    expose_dnat_rule_name = _form_expose_dnat_rule_name(cluster_name,
                                                        cluster_id)
    nsxt_gateway_svc.delete_dnat_rule(expose_dnat_rule_name)

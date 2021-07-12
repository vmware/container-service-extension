# container-service-extension
# Copyright (c) 2021 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause
from dataclasses import asdict
import random
import re
import string
import threading
import time
from typing import Dict, List, Optional
import urllib

import pkg_resources
import pyvcloud.vcd.client as vcd_client
import pyvcloud.vcd.org as vcd_org
import pyvcloud.vcd.vapp as vcd_vapp
from pyvcloud.vcd.vdc import VDC
import pyvcloud.vcd.vm as vcd_vm
import semantic_version as semver

from container_service_extension.common.constants.server_constants import CLUSTER_ENTITY  # noqa: E501
from container_service_extension.common.constants.server_constants import ClusterMetadataKey  # noqa: E501
from container_service_extension.common.constants.server_constants import ClusterScriptFile, TemplateScriptFile  # noqa: E501
from container_service_extension.common.constants.server_constants import CSE_CLUSTER_KUBECONFIG_PATH  # noqa: E501
from container_service_extension.common.constants.server_constants import DefEntityOperation  # noqa: E501
from container_service_extension.common.constants.server_constants import DefEntityOperationStatus  # noqa: E501
from container_service_extension.common.constants.server_constants import DefEntityPhase  # noqa: E501
from container_service_extension.common.constants.server_constants import LocalTemplateKey  # noqa: E501
from container_service_extension.common.constants.server_constants import NodeType  # noqa: E501
from container_service_extension.common.constants.server_constants import ThreadLocalData  # noqa: E501
import container_service_extension.common.constants.shared_constants as shared_constants  # noqa: E501
from container_service_extension.common.constants.shared_constants import \
    CSE_PAGINATION_DEFAULT_PAGE_SIZE, SYSTEM_ORG_NAME
from container_service_extension.common.constants.shared_constants import CSE_PAGINATION_FIRST_PAGE_NUMBER  # noqa: E501
import container_service_extension.common.thread_local_data as thread_local_data  # noqa: E501
import container_service_extension.common.utils.core_utils as utils
import container_service_extension.common.utils.pyvcloud_utils as vcd_utils
from container_service_extension.common.utils.script_utils import get_cluster_script_file_contents  # noqa: E501
import container_service_extension.common.utils.server_utils as server_utils
import container_service_extension.common.utils.thread_utils as thread_utils
import container_service_extension.common.utils.vsphere_utils as vs_utils
import container_service_extension.exception.exceptions as exceptions
import container_service_extension.installer.templates.local_template_manager as ltm  # noqa: E501
import container_service_extension.lib.telemetry.constants as telemetry_constants  # noqa: E501
import container_service_extension.lib.telemetry.telemetry_handler as telemetry_handler  # noqa: E501
from container_service_extension.logging.logger import SERVER_LOGGER as LOGGER
from container_service_extension.mqi.consumer.mqtt_publisher import MQTTPublisher  # noqa: E501
import container_service_extension.rde.acl_service as acl_service
import container_service_extension.rde.backend.common.network_expose_helper as nw_exp_helper  # noqa: E501
from container_service_extension.rde.behaviors.behavior_model import BehaviorError, BehaviorTaskStatus  # noqa: E501
import container_service_extension.rde.common.entity_service as def_entity_svc
import container_service_extension.rde.constants as def_constants
import container_service_extension.rde.models.common_models as common_models
import container_service_extension.rde.models.rde_2_0_0 as rde_2_x
import container_service_extension.rde.utils as def_utils
from container_service_extension.security.context.behavior_request_context import RequestContext  # noqa: E501
import container_service_extension.security.context.operation_context as operation_context  # noqa: E501
import container_service_extension.server.abstract_broker as abstract_broker
import container_service_extension.server.compute_policy_manager as compute_policy_manager  # noqa: E501

DEFAULT_API_VERSION = vcd_client.ApiVersion.VERSION_36.value

CLUSTER_CREATE_OPERATION_MESSAGE = 'Cluster create'
CLUSTER_RESIZE_OPERATION_MESSAGE = 'Cluster resize'
CLUSTER_DELETE_OPERATION_MESSAGE = 'Cluster delete'
CLUSTER_UPGRADE_OPERATION_MESSAGE = 'Cluster upgrade'
DOWNLOAD_KUBECONFIG_OPERATION_MESSAGE = 'Download kubeconfig'


class ClusterService(abstract_broker.AbstractBroker):
    """Handles cluster operations for native DEF based clusters."""

    def __init__(self, ctx: RequestContext):
        self.context: Optional[operation_context.OperationContext] = None
        # populates above attributes
        super().__init__(ctx.op_ctx)

        # TODO find an elegant way to dynamically pick the module rde_2_x

        self.task_id = ctx.task_id
        client_v36 = self.context.get_client(api_version=DEFAULT_API_VERSION)
        self.task_href = client_v36.get_api_uri() + f"/task/{self.task_id}"
        self.task_status = None
        self.entity_id = ctx.entity_id
        self.mqtt_publisher: MQTTPublisher = ctx.mqtt_publisher
        cloudapi_client_v36 = self.context.get_cloudapi_client(
            api_version=DEFAULT_API_VERSION)
        self.entity_svc = def_entity_svc.DefEntityService(cloudapi_client_v36)
        sysadmin_cloudapi_client_v36 = \
            self.context.get_sysadmin_cloudapi_client(
                api_version=DEFAULT_API_VERSION)
        self.sysadmin_entity_svc = def_entity_svc.DefEntityService(
            sysadmin_cloudapi_client_v36)

    def get_cluster_info(self, cluster_id: str) -> common_models.DefEntity:
        """Get the corresponding defined entity of the native cluster.

        This method ensures to return the latest state of the cluster vApp.
        It syncs the defined entity with the state of the cluster vApp before
        returning the defined entity.
        """
        telemetry_handler.record_user_action_details(
            cse_operation=telemetry_constants.CseOperation.V36_CLUSTER_INFO,
            cse_params={
                telemetry_constants.PayloadKey.CLUSTER_ID: cluster_id,
                telemetry_constants.PayloadKey.SOURCE_DESCRIPTION: thread_local_data.get_thread_local_data(ThreadLocalData.USER_AGENT)  # noqa: E501
            }
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
            cse_operation=telemetry_constants.CseOperation.V36_CLUSTER_LIST,
            cse_params={
                telemetry_constants.PayloadKey.FILTER_KEYS: ','.join(filters.keys()),  # noqa: E501
                telemetry_constants.PayloadKey.SOURCE_DESCRIPTION: thread_local_data.get_thread_local_data(ThreadLocalData.USER_AGENT)  # noqa: E501
            }
        )
        ent_type: common_models.DefEntityType = server_utils.get_registered_def_entity_type()  # noqa: E501
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
            cse_operation=telemetry_constants.CseOperation.V36_CLUSTER_LIST,
            cse_params={
                telemetry_constants.PayloadKey.FILTER_KEYS: ','.join(filters.keys()),  # noqa: E501
                telemetry_constants.PayloadKey.SOURCE_DESCRIPTION: thread_local_data.get_thread_local_data(ThreadLocalData.USER_AGENT)  # noqa: E501
            }
        )

        ent_type: common_models.DefEntityType = server_utils.get_registered_def_entity_type()  # noqa: E501

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
        curr_rde = self.entity_svc.get_entity(cluster_id)
        curr_native_entity: rde_2_x.NativeEntity = curr_rde.entity
        if curr_rde.state != def_constants.DEF_RESOLVED_STATE:
            msg = f"Cluster {curr_rde.name} with id {cluster_id} is " \
                  "not in a valid state for this operation. " \
                  "Please contact the administrator"
            LOGGER.error(msg)
            raise exceptions.CseServerError(msg)

        msg = f"{DOWNLOAD_KUBECONFIG_OPERATION_MESSAGE} ({cluster_id})"
        self._update_task(BehaviorTaskStatus.RUNNING, message=msg)

        telemetry_handler.record_user_action_details(
            cse_operation=telemetry_constants.CseOperation.V36_CLUSTER_CONFIG,
            cse_params={
                CLUSTER_ENTITY: curr_rde,
                telemetry_constants.PayloadKey.SOURCE_DESCRIPTION: thread_local_data.get_thread_local_data(ThreadLocalData.USER_AGENT)  # noqa: E501
            }
        )

        if curr_rde.externalId is None:
            msg = f"Cannot find VApp href for cluster {curr_rde.name} " \
                  f"with id {cluster_id}"
            LOGGER.error(msg)
            raise exceptions.CseServerError(msg)

        client_v36 = self.context.get_client(api_version=DEFAULT_API_VERSION)
        vapp = vcd_vapp.VApp(client_v36, href=curr_rde.externalId)
        control_plane_node_name = curr_native_entity.status.nodes.control_plane.name  # noqa: E501

        LOGGER.debug(f"getting file from node {control_plane_node_name}")
        password = vapp.get_admin_password(control_plane_node_name)
        sysadmin_client_v36 = self.context.get_sysadmin_client(
            api_version=DEFAULT_API_VERSION)
        vs = vs_utils.get_vsphere(sysadmin_client_v36, vapp,
                                  vm_name=control_plane_node_name,
                                  logger=LOGGER)
        vs.connect()
        moid = vapp.get_vm_moid(control_plane_node_name)
        vm = vs.get_vm_by_moid(moid)
        result = vs.download_file_from_guest(vm, 'root', password,
                                             CSE_CLUSTER_KUBECONFIG_PATH)

        if not result:
            msg = "Failed to get cluster kube-config"
            LOGGER.error(msg)
            raise exceptions.ClusterOperationError(msg)

        return self.mqtt_publisher.construct_behavior_payload(
            message=result.content.decode(),
            status=BehaviorTaskStatus.SUCCESS.value)

    def create_cluster(self, entity_id: str, input_native_entity: rde_2_x.NativeEntity):  # noqa: E501
        """Start the cluster creation operation.

        Creates corresponding defined entity in vCD for every native cluster.
        Updates the defined entity with new properties after the cluster
        creation.

        **telemetry: Optional

        :return: dictionary representing mqtt response published
        :rtype: dict
        """
        cluster_name: Optional[str] = None
        org_name: Optional[str] = None
        ovdc_name: Optional[str] = None
        try:
            cluster_name = input_native_entity.metadata.name
            org_name = input_native_entity.metadata.org_name
            ovdc_name = input_native_entity.metadata.virtual_data_center_name

            # Pick default template name and revision if both template name
            # and template revision is not provided in the input native entity
            if not input_native_entity.spec.distribution.template_name and \
                    not input_native_entity.spec.distribution.template_revision:  # noqa: E501
                server_config: dict = server_utils.get_server_runtime_config()
                input_native_entity.spec.distribution = rde_2_x.Distribution(
                    template_name=server_config['broker']['default_template_name'],  # noqa: E501
                    template_revision=int(server_config['broker']['default_template_revision']))  # noqa: E501
            template_name = input_native_entity.spec.distribution.template_name
            template_revision = input_native_entity.spec.distribution.template_revision  # noqa: E501

            # check that cluster name is syntactically valid
            if not _is_valid_cluster_name(cluster_name):
                raise exceptions.CseServerError(
                    f"Invalid cluster name '{cluster_name}'")

            # Check that cluster name doesn't already exist.
            # Do not replace the below with the check to verify if defined
            # entity already exists. It will not give accurate result as even
            # sys-admin cannot view all the defined entities unless
            # native entity type admin view right is assigned.
            client_v36 = \
                self.context.get_client(api_version=DEFAULT_API_VERSION)
            if _cluster_exists(client_v36, cluster_name,
                               org_name=org_name,
                               ovdc_name=ovdc_name):
                raise exceptions.ClusterAlreadyExistsError(
                    f"Cluster '{cluster_name}' already exists.")

            # check that requested/default template is valid
            template = _get_template(
                name=template_name, revision=template_revision)

            # TODO(DEF) design and implement telemetry VCDA-1564 defined entity
            #  based clusters
            k8_distribution = rde_2_x.Distribution(
                template_name=template_name,
                template_revision=template_revision
            )
            cloud_properties = rde_2_x.CloudProperties(
                distribution=k8_distribution,
                org_name=org_name,
                virtual_data_center_name=ovdc_name,
                ovdc_network_name=input_native_entity.spec.settings.ovdc_network,  # noqa: E501
                rollback_on_failure=input_native_entity.spec.settings.rollback_on_failure,  # noqa: E501
                ssh_key=input_native_entity.spec.settings.ssh_key
            )
            new_status: rde_2_x.Status = rde_2_x.Status(
                phase=str(DefEntityPhase(DefEntityOperation.CREATE,
                                         DefEntityOperationStatus.IN_PROGRESS)),  # noqa: E501
                kubernetes=_create_k8s_software_string(
                    template[LocalTemplateKey.KUBERNETES],
                    template[LocalTemplateKey.KUBERNETES_VERSION]),
                cni=_create_k8s_software_string(
                    template[LocalTemplateKey.CNI],
                    template[LocalTemplateKey.CNI_VERSION]),
                docker_version=template[LocalTemplateKey.DOCKER_VERSION],
                os=template[LocalTemplateKey.OS],
                cloud_properties=cloud_properties,
                uid=entity_id
            )

            msg = f"Creating cluster '{cluster_name}' " \
                  f"from template '{template_name}' " \
                  f"(revision {template_revision})"
            self._update_task(BehaviorTaskStatus.RUNNING, message=msg)
            new_status.task_href = self.task_href

            try:
                curr_rde = self._update_cluster_entity(entity_id, new_status)  # noqa: E501
            except Exception:
                msg = f"Error updating the cluster '{cluster_name}' with the status"  # noqa: E501
                LOGGER.error(msg, exc_info=True)
                raise
            telemetry_handler.record_user_action_details(
                cse_operation=telemetry_constants.CseOperation.V36_CLUSTER_APPLY,  # noqa: E501
                cse_params={
                    CLUSTER_ENTITY: curr_rde,
                    telemetry_constants.PayloadKey.SOURCE_DESCRIPTION: thread_local_data.get_thread_local_data(ThreadLocalData.USER_AGENT)  # noqa: E501
                }
            )
            # trigger async operation
            self.context.is_async = True
            self._create_cluster_async(entity_id, input_native_entity)
            return self.mqtt_publisher.construct_behavior_payload(
                message=f"{CLUSTER_CREATE_OPERATION_MESSAGE} ({entity_id})",
                status=BehaviorTaskStatus.RUNNING.value,
                progress=5)
        except Exception as err:
            create_failed_msg = f"Failed to create cluster {cluster_name} in org {org_name} and VDC {ovdc_name}"  # noqa: E501
            LOGGER.error(create_failed_msg, exc_info=True)
            # Since defined entity is already created by defined entity
            # framework, we need to delete the defined entity if rollback
            # is set to true
            # NOTE: As per schema definition, default value for rollback is
            #   True
            if input_native_entity.spec.settings.rollback_on_failure:
                try:
                    # TODO can reduce try - catch by raising more specific
                    # exceptions
                    # Resolve entity state manually (PRE_CREATED --> RESOLVED/RESOLUTION_ERROR)  # noqa: E501
                    # to allow delete operation
                    self.sysadmin_entity_svc.resolve_entity(entity_id=entity_id)  # noqa: E501
                    # delete defined entity
                    self.sysadmin_entity_svc.delete_entity(
                        entity_id,
                        invoke_hooks=False)
                except Exception:
                    msg = f"Failed to delete defined entity for cluster " \
                          f"{cluster_name} ({entity_id})"
                    LOGGER.error(msg, exc_info=True)
            else:
                # update status to CREATE:FAILED
                try:
                    self._fail_operation(entity_id, DefEntityOperation.CREATE)
                except Exception:
                    msg = f"Failed to update defined entity status for" \
                          f" cluster {cluster_name}({entity_id})"
                    LOGGER.error(f"{msg}", exc_info=True)

            self._update_task(BehaviorTaskStatus.ERROR,
                              message=create_failed_msg,
                              error_message=str(err))
            raise

    def resize_cluster(self, cluster_id: str,
                       input_native_entity: rde_2_x.NativeEntity):
        """Start the resize cluster operation.

        :param str cluster_id: Defined entity Id of the cluster
        :param DefEntity input_native_entity: Input cluster spec
        :return: DefEntity of the cluster with the updated operation status
        and task_href.

        :rtype: dict
        """
        # TODO: Make use of current entity in the behavior payload
        # NOTE: It is always better to do a get on the entity to make use of
        # existing entity status. This guarantees that operations performed
        # are relevant.
        curr_rde: common_models.DefEntity = self.entity_svc.get_entity(cluster_id)  # noqa: E501
        curr_native_entity: rde_2_x.NativeEntity = curr_rde.entity
        state: str = curr_rde.state

        cluster_name: str = curr_rde.name
        current_spec: rde_2_x.ClusterSpec = \
            def_utils.construct_cluster_spec_from_entity_status(
                curr_native_entity.status,
                server_utils.get_rde_version_in_use())
        curr_worker_count: int = current_spec.topology.workers.count
        curr_nfs_count: int = current_spec.topology.nfs.count
        phase: DefEntityPhase = DefEntityPhase.from_phase(
            curr_native_entity.status.phase)

        # compute the values of workers and nfs to be added or removed by
        # comparing the desired and the current state. "num_workers_to_add"
        # can hold either +ve or -ve value.
        desired_worker_count: int = input_native_entity.spec.topology.workers.count  # noqa: E501
        desired_nfs_count: int = input_native_entity.spec.topology.nfs.count
        num_workers_to_add: int = desired_worker_count - curr_worker_count
        num_nfs_to_add: int = desired_nfs_count - curr_nfs_count

        if desired_worker_count < 0:
            raise exceptions.CseServerError(
                f"Worker count must be >= 0 (received {desired_worker_count})")
        if num_nfs_to_add < 0:
            raise exceptions.CseServerError(
                "Scaling down nfs nodes is not supported")

        # Check for unexposing the cluster
        desired_expose_state: bool = \
            input_native_entity.spec.settings.network.expose
        is_exposed: bool = current_spec.settings.network.expose
        unexpose: bool = is_exposed and not desired_expose_state

        # Check if the desired worker and nfs count is valid and raise
        # an exception if the cluster does not need to be unexposed
        if not unexpose and num_workers_to_add == 0 and num_nfs_to_add == 0:
            raise exceptions.CseServerError(
                f"Cluster '{cluster_name}' already has {desired_worker_count} "
                f"workers and {desired_nfs_count} nfs nodes and is "
                f"already not exposed.")

        # check if cluster is in a valid state
        if state != def_constants.DEF_RESOLVED_STATE or phase.is_entity_busy():
            # TODO fix the exception type raised
            raise exceptions.CseServerError(
                f"Cluster {cluster_name} with id {cluster_id} is not in a "
                f"valid state to be resized. Please contact the administrator")

        # Record telemetry details
        telemetry_data: common_models.DefEntity = common_models.DefEntity(
            entityType=server_utils.get_registered_def_entity_type().id,
            id=cluster_id,
            entity=input_native_entity)
        telemetry_handler.record_user_action_details(
            cse_operation=telemetry_constants.CseOperation.V36_CLUSTER_APPLY,
            cse_params={
                CLUSTER_ENTITY: telemetry_data,
                telemetry_constants.PayloadKey.SOURCE_DESCRIPTION: thread_local_data.get_thread_local_data(ThreadLocalData.USER_AGENT)  # noqa: E501
            }
        )

        # update the task and defined entity.
        msg = f"Resizing the cluster '{cluster_name}' ({cluster_id}) to the " \
              f"desired worker count {desired_worker_count} and " \
              f"nfs count {desired_nfs_count}"
        if unexpose:
            msg += " and unexposing the cluster"
        self._update_task(BehaviorTaskStatus.RUNNING, message=msg)
        # set entity status to busy
        new_status: rde_2_x.Status = curr_native_entity.status
        new_status.task_href = self.task_href
        new_status.phase = str(
            DefEntityPhase(DefEntityOperation.UPDATE,
                           DefEntityOperationStatus.IN_PROGRESS))
        try:
            self._update_cluster_entity(cluster_id, new_status)
        except Exception as err:
            self._update_task(BehaviorTaskStatus.ERROR,
                              message=msg,
                              error_message=str(err))
            LOGGER.error(str(err), exc_info=True)
            raise
        # trigger async operation
        self.context.is_async = True
        self._monitor_resize(
            cluster_id=cluster_id,
            input_native_entity=input_native_entity
        )
        # TODO(test-resize): verify if multiple messages are not published
        #   in update_cluster()
        return self.mqtt_publisher.construct_behavior_payload(
            message=f"{CLUSTER_RESIZE_OPERATION_MESSAGE} ({cluster_id})",
            status=BehaviorTaskStatus.RUNNING.value, progress=5)

    def delete_cluster(self, cluster_id):
        """Start the delete cluster operation."""
        # TODO: Make use of current entity in the behavior payload
        # Get entity required here to get the org and vdc in which the cluster
        # is present
        curr_rde: common_models.DefEntity = self.entity_svc.get_entity(
            cluster_id)
        curr_native_entity: rde_2_x.NativeEntity = curr_rde.entity
        cluster_name: str = curr_rde.name
        org_name: str = curr_native_entity.metadata.org_name
        ovdc_name: str = curr_native_entity.metadata.virtual_data_center_name
        phase: DefEntityPhase = DefEntityPhase.from_phase(
            curr_native_entity.status.phase)

        # Check if cluster is busy
        if phase.is_entity_busy():
            raise exceptions.CseServerError(
                f"Cluster {cluster_name} with id {cluster_id} is not in a "
                f"valid state to be deleted. Please contact administrator.")

        telemetry_handler.record_user_action_details(
            cse_operation=telemetry_constants.CseOperation.V36_CLUSTER_DELETE,
            cse_params={
                CLUSTER_ENTITY: curr_rde,
                telemetry_constants.PayloadKey.SOURCE_DESCRIPTION: thread_local_data.get_thread_local_data(ThreadLocalData.USER_AGENT)  # noqa: E501
            }
        )

        # must _update_task here or else self.task_resource is None
        # do not logout of sys admin, or else in pyvcloud's session.request()
        # call, session becomes None
        msg = f"Deleting cluster '{cluster_name}' ({cluster_id})"
        self._update_task(BehaviorTaskStatus.RUNNING, message=msg)

        new_status: rde_2_x.Status = curr_native_entity.status
        new_status.task_href = self.task_href
        curr_native_entity.phase = str(
            DefEntityPhase(DefEntityOperation.DELETE,
                           DefEntityOperationStatus.IN_PROGRESS))
        # Update defined entity of the cluster to delete in-progress state
        try:
            self._update_cluster_entity(cluster_id, new_status)
        except Exception:
            msg = f"Error updating the cluster '{cluster_name}' with the status"  # noqa: E501
            LOGGER.error(msg, exc_info=True)
            raise

        self.context.is_async = True
        # NOTE: The async method will mark the task as succeeded which will
        # allow the RDE framework to delete the cluster defined entity
        self._delete_cluster_async(cluster_name=cluster_name,
                                   org_name=org_name,
                                   ovdc_name=ovdc_name,
                                   curr_rde=curr_rde)
        return self.mqtt_publisher.construct_behavior_payload(
            message=f"{CLUSTER_DELETE_OPERATION_MESSAGE} ({cluster_id})",
            status=BehaviorTaskStatus.RUNNING.value, progress=5)

    def get_cluster_upgrade_plan(self, cluster_id: str):
        """Get the template names/revisions that the cluster can upgrade to.

        :param str cluster_id:
        :return: A list of dictionaries with keys defined in LocalTemplateKey

        :rtype: List[Dict]
        """
        # TODO: Make use of current entity in the behavior payload
        # Get entity required here to retrieve the cluster upgrade plan
        curr_rde = self.entity_svc.get_entity(cluster_id)
        curr_native_entity: rde_2_x.NativeEntity = curr_rde.entity
        telemetry_handler.record_user_action_details(
            cse_operation=telemetry_constants.CseOperation.V36_CLUSTER_UPGRADE_PLAN,  # noqa: E501
            cse_params={
                CLUSTER_ENTITY: curr_rde,
                telemetry_constants.PayloadKey.SOURCE_DESCRIPTION: thread_local_data.get_thread_local_data(ThreadLocalData.USER_AGENT)  # noqa: E501
            }
        )
        return _get_cluster_upgrade_target_templates(
            curr_native_entity.status.cloud_properties.distribution.template_name,  # noqa: E501
            str(curr_native_entity.status.cloud_properties.distribution.template_revision))  # noqa: E501

    def upgrade_cluster(self, cluster_id: str,
                        input_native_entity: rde_2_x.NativeEntity):
        """Start the upgrade cluster operation.

        Upgrading cluster is an asynchronous task, so the returned
        `result['task_href']` can be polled to get updates on task progress.

        :param str cluster_id: id of the cluster to be upgraded
        :param rde_2_x.NativeEntity input_native_entity: cluster spec with new
            kubernetes distribution and revision

        :return: dictionary representing mqtt response published
        :rtype: dict
        """
        # TODO: Make use of current entity in the behavior payload
        curr_rde = self.entity_svc.get_entity(cluster_id)
        curr_native_entity: rde_2_x.NativeEntity = curr_rde.entity
        cluster_name = curr_native_entity.metadata.name
        new_template_name = input_native_entity.spec.distribution.template_name
        new_template_revision = input_native_entity.spec.distribution.template_revision  # noqa: E501

        # check if cluster is in a valid state
        phase: DefEntityPhase = DefEntityPhase.from_phase(
            curr_native_entity.status.phase)

        state = curr_rde.state
        if state != def_constants.DEF_RESOLVED_STATE or phase.is_entity_busy():
            raise exceptions.CseServerError(
                f"Cluster {cluster_name} with id {cluster_id} is not in a "
                f"valid state to be upgraded. Please contact administrator.")

        # check that the specified template is a valid upgrade target
        template = {}
        valid_templates = _get_cluster_upgrade_target_templates(
            curr_native_entity.status.cloud_properties.distribution.template_name,  # noqa: E501
            str(curr_native_entity.status.cloud_properties.distribution.template_revision))  # noqa: E501

        for t in valid_templates:
            if (t[LocalTemplateKey.NAME], str(t[LocalTemplateKey.REVISION])) == (new_template_name, str(new_template_revision)):  # noqa: E501
                template = t
                break
        if not template:
            try:
                self._fail_operation(cluster_id, DefEntityOperation.UPGRADE)
            except Exception:
                msg = f"Failed to update defined entity status for cluster {cluster_id}"  # noqa: E501
                LOGGER.error(msg, exc_info=True)
            # TODO all of these e.CseServerError instances related to request
            # should be changed to BadRequestError (400)
            raise exceptions.CseServerError(
                f"Specified template/revision ({new_template_name} revision "
                f"{new_template_revision}) is not a valid upgrade target for "
                f"cluster '{cluster_name}'.")

        telemetry_handler.record_user_action_details(
            telemetry_constants.CseOperation.V36_CLUSTER_UPGRADE,
            cse_params={
                CLUSTER_ENTITY: curr_rde,
                telemetry_constants.PayloadKey.SOURCE_DESCRIPTION: thread_local_data.get_thread_local_data(ThreadLocalData.USER_AGENT)  # noqa: E501
            }
        )

        msg = f"Upgrading cluster '{cluster_name}' " \
              f"software to match template {new_template_name} (revision " \
              f"{new_template_revision}): Kubernetes: " \
              f"{input_native_entity.status.kubernetes} -> " \
              f"{template[LocalTemplateKey.KUBERNETES_VERSION]}, Docker-CE: " \
              f"{input_native_entity.status.docker_version} -> " \
              f"{template[LocalTemplateKey.DOCKER_VERSION]}, CNI: " \
              f"{input_native_entity.status.cni} -> " \
              f"{template[LocalTemplateKey.CNI_VERSION]}"
        self._update_task(BehaviorTaskStatus.RUNNING, message=msg)
        LOGGER.info(f"{msg} ({curr_rde.externalId})")

        new_status: rde_2_x.Status = input_native_entity.status
        new_status.phase = str(
            DefEntityPhase(DefEntityOperation.UPGRADE, DefEntityOperationStatus.IN_PROGRESS))  # noqa: E501
        new_status.task_href = self.task_href
        try:
            self._update_cluster_entity(cluster_id,
                                        new_status)
        except Exception as err:
            self._update_task(BehaviorTaskStatus.ERROR,
                              message=msg,
                              error_message=str(err))
            LOGGER.error(str(err), exc_info=True)
            raise

        self.context.is_async = True
        self._upgrade_cluster_async(cluster_id=cluster_id,
                                    template=template)
        # TODO(test-upgrade): Verify if multiple messages are not published
        #   in update_cluster()
        return self.mqtt_publisher.construct_behavior_payload(
            message=f"{CLUSTER_UPGRADE_OPERATION_MESSAGE} ({cluster_id})",
            status=BehaviorTaskStatus.RUNNING.value, progress=5)

    def update_cluster(self, cluster_id: str, input_native_entity: rde_2_x.NativeEntity):  # noqa: E501
        """Start the update cluster operation (resize or upgrade).

        Updating cluster is an asynchronous task, so the returned
        `result['task_href']` can be polled to get updates on task progress.

        :param str cluster_id: id of the cluster to be updated
        :param rde_2_x.NativeEntity input_native_entity: cluster spec with new
        worker/nfs node count or new kubernetes distribution and revision

        :return: dictionary representing mqtt response published
        :rtype: dict
        """
        # TODO: Make use of current entity in the behavior payload
        curr_rde = self.entity_svc.get_entity(cluster_id)
        curr_native_entity: rde_2_x.NativeEntity = curr_rde.entity
        current_spec: rde_2_x.ClusterSpec = \
            def_utils.construct_cluster_spec_from_entity_status(
                curr_native_entity.status,
                server_utils.get_rde_version_in_use())
        current_workers_count = current_spec.topology.workers.count
        current_nfs_count = current_spec.topology.nfs.count
        desired_workers_count = input_native_entity.spec.topology.workers.count
        desired_nfs_count = input_native_entity.spec.topology.nfs.count

        if current_workers_count != desired_workers_count or current_nfs_count != desired_nfs_count:  # noqa: E501
            return self.resize_cluster(cluster_id, input_native_entity)

        current_template_name = current_spec.distribution.template_name
        current_template_revision = current_spec.distribution.template_revision
        desired_template_name = input_native_entity.spec.distribution.template_name  # noqa: E501
        desired_template_revision = input_native_entity.spec.distribution.template_revision  # noqa: E501
        if current_template_name != desired_template_name or current_template_revision != desired_template_revision:  # noqa: E501
            return self.upgrade_cluster(cluster_id, input_native_entity)
        raise exceptions.CseServerError("update not supported for the specified input specification")  # noqa: E501

    def get_cluster_acl_info(self, cluster_id, page: int, page_size: int):
        """Get cluster ACL info based on the defined entity ACL."""
        telemetry_params = {
            shared_constants.RequestKey.CLUSTER_ID: cluster_id,
            shared_constants.PaginationKey.PAGE_NUMBER: page,
            shared_constants.PaginationKey.PAGE_SIZE: page_size,
            telemetry_constants.PayloadKey.SOURCE_DESCRIPTION: thread_local_data.get_thread_local_data(ThreadLocalData.USER_AGENT)  # noqa: E501
        }
        telemetry_handler.record_user_action_details(
            telemetry_constants.CseOperation.V36_CLUSTER_ACL_LIST,
            cse_params=telemetry_params)

        client_v36 = self.context.get_client(api_version=DEFAULT_API_VERSION)
        acl_svc = acl_service.ClusterACLService(cluster_id, client_v36)
        curr_rde: common_models.DefEntity = acl_svc.get_cluster_entity()
        user_id_names_dict = vcd_utils.create_org_user_id_to_name_dict(
            client=client_v36,
            org_name=curr_rde.org.name)
        # If the user is from the system org, need to consider system users
        if client_v36.is_sysadmin():
            system_user_id_names_dict = vcd_utils.create_org_user_id_to_name_dict(  # noqa: E501
                client=client_v36,
                org_name=SYSTEM_ORG_NAME)
            user_id_names_dict.update(system_user_id_names_dict)

        # Iterate all acl entries because not all results correspond to a user
        acl_values = []
        result_total = 0
        for acl_entry in acl_svc.list_def_entity_acl_entries():
            if acl_entry.memberId.startswith(shared_constants.USER_URN_PREFIX):
                curr_page = result_total // page_size + 1
                page_entry = result_total % page_size
                # Check if entry is on desired page
                if curr_page == page and page_entry < page_size:
                    # Add acl entry
                    # If there is no username found, the user must be a system
                    # user, so a generic name is shown
                    acl_entry.username = user_id_names_dict.get(
                        acl_entry.memberId, shared_constants.SYSTEM_USER_GENERIC_NAME)  # noqa: E501
                    filter_acl_value: dict = acl_entry.construct_filtered_dict(
                        include=def_constants.CLUSTER_ACL_LIST_FIELDS)
                    acl_values.append(filter_acl_value)
                result_total += 1

        return {
            shared_constants.PaginationKey.RESULT_TOTAL: result_total,
            shared_constants.PaginationKey.VALUES: acl_values
        }

    def update_cluster_acl(self, cluster_id, update_acl_entry_dicts: list):
        """Update the cluster ACL by updating the defined entity and vApp ACL."""  # noqa: E501
        update_acl_entries = [common_models.ClusterAclEntry(**entry_dict)
                              for entry_dict in update_acl_entry_dicts]
        telemetry_params = {
            shared_constants.RequestKey.CLUSTER_ID: cluster_id,
            shared_constants.ClusterAclKey.UPDATE_ACL_ENTRIES:
                update_acl_entries,
            telemetry_constants.PayloadKey.SOURCE_DESCRIPTION: thread_local_data.get_thread_local_data(ThreadLocalData.USER_AGENT)  # noqa: E501
        }
        telemetry_handler.record_user_action_details(
            telemetry_constants.CseOperation.V36_CLUSTER_ACL_UPDATE,
            cse_params=telemetry_params)

        client_v36 = self.context.get_client(api_version=DEFAULT_API_VERSION)
        # Get previous def entity acl
        acl_svc = acl_service.ClusterACLService(cluster_id, client_v36)
        prev_user_id_to_acl_entry_dict: \
            Dict[str, common_models.ClusterAclEntry] = \
            acl_svc.create_user_id_to_acl_entry_dict()

        try:
            acl_svc.update_native_def_entity_acl(
                update_acl_entries=update_acl_entries,
                prev_user_id_to_acl_entry=prev_user_id_to_acl_entry_dict)
            acl_svc.native_update_vapp_access_settings(
                prev_user_id_to_acl_entry_dict, update_acl_entries)
        except Exception as err:
            LOGGER.error(str(err), exc_info=True)
            # Rollback defined entity
            prev_acl_entries = [acl_entry for _, acl_entry in prev_user_id_to_acl_entry_dict.items()]  # noqa: E501
            curr_user_acl_info = acl_svc.create_user_id_to_acl_entry_dict()
            acl_svc.update_native_def_entity_acl(
                update_acl_entries=prev_acl_entries,
                prev_user_id_to_acl_entry=curr_user_acl_info)
            raise err

    def delete_nodes(self, cluster_id: str, nodes_to_del=None):
        """Start the delete nodes operation."""
        if nodes_to_del is None:
            nodes_to_del = []
        # TODO: Make use of current entity in the behavior payload
        # get_entity() call needed here to get the cluster details
        curr_rde: common_models.DefEntity = self.entity_svc.get_entity(
            cluster_id)
        curr_native_entity: rde_2_x.NativeEntity = curr_rde.entity

        if len(nodes_to_del) == 0:
            LOGGER.debug("No nodes specified to delete")
            return curr_rde

        # must _update_task here or else self.task_resource is None
        # do not logout of sys admin, or else in pyvcloud's session.request()
        # call, session becomes None

        msg = f"Deleting {', '.join(nodes_to_del)} node(s) from cluster " \
              f"'{curr_native_entity.metadata.name}' ({cluster_id})"
        self._update_task(BehaviorTaskStatus.RUNNING, message=msg)

        # TODO(DEF) design and implement telemetry VCDA-1564 defined entity
        #  based clusters

        new_status: rde_2_x.Status = curr_native_entity.status
        new_status.task_href = self.task_href
        new_status.phase = str(
            DefEntityPhase(DefEntityOperation.UPDATE,
                           DefEntityOperationStatus.IN_PROGRESS))
        try:
            curr_rde = self._update_cluster_entity(cluster_id, new_status)
        except Exception as err:
            self._update_task(BehaviorTaskStatus.ERROR,
                              message=msg,
                              error_message=str(err))
            LOGGER.error(str(err), exc_info=True)
            raise

        self.context.is_async = True
        self._monitor_delete_nodes(cluster_id=cluster_id,
                                   nodes_to_del=nodes_to_del)
        msg = f"Deleting NFS nodes: {nodes_to_del} for cluster {curr_rde.name} ({cluster_id})"  # noqa: E501
        return self.mqtt_publisher.construct_behavior_payload(
            message=msg,
            status=BehaviorTaskStatus.RUNNING.value, progress=5)

    @thread_utils.run_async
    def _create_cluster_async(self, cluster_id: str,
                              input_native_entity: rde_2_x.NativeEntity):
        cluster_name = ''
        rollback = False
        org_name = ''
        ovdc_name = ''
        vapp = None
        expose_ip: str = ''
        network_name = ''
        client_v36 = self.context.get_client(api_version=DEFAULT_API_VERSION)
        try:
            cluster_name = input_native_entity.metadata.name
            org_name = input_native_entity.metadata.org_name
            ovdc_name = input_native_entity.metadata.virtual_data_center_name
            num_workers = input_native_entity.spec.topology.workers.count
            control_plane_sizing_class = input_native_entity.spec.topology.control_plane.sizing_class  # noqa: E501
            worker_sizing_class = input_native_entity.spec.topology.workers.sizing_class  # noqa: E501
            control_plane_storage_profile = input_native_entity.spec.topology.control_plane.storage_profile  # noqa: E501
            worker_storage_profile = input_native_entity.spec.topology.workers.storage_profile  # noqa: E501
            nfs_count = input_native_entity.spec.topology.nfs.count
            nfs_sizing_class = input_native_entity.spec.topology.nfs.sizing_class  # noqa: E501
            nfs_storage_profile = input_native_entity.spec.topology.nfs.storage_profile  # noqa: E501
            network_name = input_native_entity.spec.settings.ovdc_network
            template_name = input_native_entity.spec.distribution.template_name  # noqa: E501
            template_revision = input_native_entity.spec.distribution.template_revision  # noqa: E501
            ssh_key = input_native_entity.spec.settings.ssh_key
            rollback = input_native_entity.spec.settings.rollback_on_failure
            expose = input_native_entity.spec.settings.network.expose

            org = vcd_utils.get_org(client_v36, org_name=org_name)
            vdc = vcd_utils.get_vdc(client_v36, vdc_name=ovdc_name, org=org)

            LOGGER.debug(f"About to create cluster '{cluster_name}' on "
                         f"{ovdc_name} with {num_workers} worker nodes, "
                         f"storage profile={worker_storage_profile}")
            msg = f"Creating cluster vApp {cluster_name} ({cluster_id})"
            self._update_task(BehaviorTaskStatus.RUNNING, message=msg)
            try:
                vapp_resource = vdc.create_vapp(
                    cluster_name,
                    description=f"cluster '{cluster_name}'",
                    network=network_name,
                    fence_mode='bridged')
            except Exception as err:
                LOGGER.error(str(err), exc_info=True)
                raise exceptions.ClusterOperationError(
                    f"Error while creating vApp: {err}")
            client_v36.get_task_monitor().wait_for_status(vapp_resource.Tasks.Task[0])  # noqa: E501

            template = _get_template(template_name, template_revision)

            LOGGER.debug(f"Setting metadata on cluster vApp '{cluster_name}'")
            tags = {
                ClusterMetadataKey.CLUSTER_ID: cluster_id,
                ClusterMetadataKey.CSE_VERSION: pkg_resources.require('container-service-extension')[0].version,  # noqa: E501
                ClusterMetadataKey.TEMPLATE_NAME: template[LocalTemplateKey.NAME],  # noqa: E501
                ClusterMetadataKey.TEMPLATE_REVISION: template[LocalTemplateKey.REVISION],  # noqa: E501
                ClusterMetadataKey.OS: template[LocalTemplateKey.OS],
                ClusterMetadataKey.DOCKER_VERSION: template[LocalTemplateKey.DOCKER_VERSION],  # noqa: E501
                ClusterMetadataKey.KUBERNETES: template[LocalTemplateKey.KUBERNETES],  # noqa: E501
                ClusterMetadataKey.KUBERNETES_VERSION: template[LocalTemplateKey.KUBERNETES_VERSION],  # noqa: E501
                ClusterMetadataKey.CNI: template[LocalTemplateKey.CNI],
                ClusterMetadataKey.CNI_VERSION: template[LocalTemplateKey.CNI_VERSION]  # noqa: E501
            }
            vapp = vcd_vapp.VApp(client_v36,
                                 href=vapp_resource.get('href'))
            task = vapp.set_multiple_metadata(tags)
            client_v36.get_task_monitor().wait_for_status(task)

            msg = f"Creating control plane node for cluster '{cluster_name}'" \
                  f" ({cluster_id})"
            LOGGER.debug(msg)
            self._update_task(BehaviorTaskStatus.RUNNING, message=msg)
            vapp.reload()
            server_config = server_utils.get_server_runtime_config()
            catalog_name = server_config['broker']['catalog']
            sysadmin_client_v36 = self.context.get_sysadmin_client(
                api_version=DEFAULT_API_VERSION)
            try:
                _add_nodes(sysadmin_client_v36,
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
                raise exceptions.ControlPlaneNodeCreationError(
                    f"Error adding control plane node: {err}")

            msg = f"Initializing cluster '{cluster_name}' ({cluster_id})"
            LOGGER.debug(msg)
            self._update_task(BehaviorTaskStatus.RUNNING, message=msg)
            vapp.reload()

            control_plane_ip = _get_control_plane_ip(
                sysadmin_client_v36, vapp, check_tools=True)

            # Handle exposing cluster
            if expose:
                try:
                    expose_ip = nw_exp_helper.expose_cluster(
                        client=self.context.client,
                        org_name=org_name,
                        ovdc_name=ovdc_name,
                        network_name=network_name,
                        cluster_name=cluster_name,
                        cluster_id=cluster_id,
                        internal_ip=control_plane_ip)
                    if expose_ip:
                        control_plane_ip = expose_ip
                except Exception as err:
                    LOGGER.error(
                        f"Exposing cluster failed: {str(err)}", exc_info=True
                    )
                    expose_ip = ''

            _init_cluster(sysadmin_client_v36,
                          vapp,
                          template[LocalTemplateKey.KIND],
                          template[LocalTemplateKey.KUBERNETES_VERSION],
                          template[LocalTemplateKey.CNI_VERSION],
                          expose_ip=expose_ip)
            task = vapp.set_metadata('GENERAL', 'READWRITE', 'cse.master.ip',
                                     control_plane_ip)
            client_v36.get_task_monitor().wait_for_status(task)

            msg = f"Creating {num_workers} node(s) for cluster " \
                  f"'{cluster_name}' ({cluster_id})"
            LOGGER.debug(msg)
            self._update_task(BehaviorTaskStatus.RUNNING, message=msg)
            try:
                _add_nodes(sysadmin_client_v36,
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
                raise exceptions.WorkerNodeCreationError(
                    f"Error creating worker node: {err}")

            msg = f"Adding {num_workers} node(s) to cluster " \
                  f"'{cluster_name}' ({cluster_id})"
            LOGGER.debug(msg)
            self._update_task(BehaviorTaskStatus.RUNNING, message=msg)
            vapp.reload()
            _join_cluster(sysadmin_client_v36, vapp)

            if nfs_count > 0:
                msg = f"Creating {nfs_count} NFS nodes for cluster " \
                      f"'{cluster_name}' ({cluster_id})"
                LOGGER.debug(msg)
                # TODO should this task be commented out?
                self._update_task(BehaviorTaskStatus.RUNNING, message=msg)
                try:
                    _add_nodes(sysadmin_client_v36,
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
                    raise exceptions.NFSNodeCreationError(
                        f"Error creating NFS node: {err}")

            # Update defined entity instance with new properties like vapp_id,
            # control plane_ip and nodes.
            msg = f"Updating cluster `{cluster_name}` ({cluster_id}) defined entity"  # noqa: E501
            LOGGER.debug(msg)
            self._update_task(BehaviorTaskStatus.RUNNING, message=msg)
            curr_rde: common_models.DefEntity = self.entity_svc.get_entity(cluster_id)  # noqa: E501
            curr_native_entity: rde_2_x.NativeEntity = curr_rde.entity
            new_status: rde_2_x.Status = curr_native_entity.status
            new_status.uid = cluster_id
            new_status.phase = str(
                DefEntityPhase(
                    DefEntityOperation.CREATE,
                    DefEntityOperationStatus.SUCCEEDED
                )
            )
            new_status.nodes = _get_nodes_details(
                sysadmin_client_v36, vapp)

            # Update status with exposed ip
            if expose_ip:
                new_status.cloud_properties.exposed = True
                new_status.external_ip = expose_ip

            self._update_cluster_entity(
                cluster_id,
                new_status,
                external_id=vapp_resource.get('href')
            )

            # cluster creation succeeded. Mark the task as success
            msg = f"Created cluster '{cluster_name}' ({cluster_id})"
            LOGGER.debug(msg)
            self._update_task(BehaviorTaskStatus.SUCCESS, message=msg)
            return msg
        except (exceptions.ControlPlaneNodeCreationError,
                exceptions.WorkerNodeCreationError,
                exceptions.NFSNodeCreationError,
                exceptions.ClusterJoiningError,
                exceptions.ClusterInitializationError,
                exceptions.ClusterOperationError) as err:
            msg = f"Error creating cluster '{cluster_name}'"
            LOGGER.error(msg, exc_info=True)
            try:
                self._fail_operation(
                    cluster_id, DefEntityOperation.CREATE)
            except Exception:
                msg = f"Failed to update defined entity status for cluster {cluster_id}"  # noqa: E501
                LOGGER.error(f"{msg}", exc_info=True)
            if rollback:
                msg = f"Error creating cluster '{cluster_name}'. " \
                      f"Deleting cluster (rollback=True)"
                self._update_task(BehaviorTaskStatus.RUNNING, message=msg)
                LOGGER.info(msg)
                try:
                    _delete_vapp(client_v36,
                                 org_name,
                                 ovdc_name,
                                 cluster_name)
                except Exception:
                    LOGGER.error(f"Failed to delete cluster '{cluster_name}'",
                                 exc_info=True)

                if expose_ip:
                    try:
                        nw_exp_helper.handle_delete_expose_dnat_rule(
                            client=self.context.client,
                            org_name=org_name,
                            ovdc_name=ovdc_name,
                            network_name=network_name,
                            cluster_name=cluster_name,
                            cluster_id=cluster_id)
                        LOGGER.info(f'Deleted dnat rule for cluster '
                                    f'{cluster_name} ({cluster_id})')
                    except Exception as err1:
                        LOGGER.error(f'Failed to delete dnat rule for '
                                     f'{cluster_name} ({cluster_id}) with '
                                     f'error: {str(err1)}', exc_info=True)

            else:
                # TODO: Avoid many try-except block. Check if it is a good practice  # noqa: E501
                # NOTE: sync of the defined entity should happen before call to
                # resolving the defined entity to prevent possible missing
                # values in the defined entity
                try:
                    self._sync_def_entity(cluster_id, vapp=vapp)
                except Exception:
                    msg = f"Failed to sync defined entity for cluster {cluster_id}"  # noqa: E501
                    LOGGER.error(f"{msg}", exc_info=True)

            # Should attempt deleting the defined entity before updating the
            # task to ERROR
            if rollback:
                try:
                    # Resolve entity state manually (PRE_CREATED --> RESOLVED/RESOLUTION_ERROR)  # noqa: E501
                    # to allow delete operation
                    self.sysadmin_entity_svc.resolve_entity(entity_id=cluster_id)  # noqa: E501
                    self.sysadmin_entity_svc.delete_entity(cluster_id,
                                                           invoke_hooks=False)
                except Exception:
                    LOGGER.error("Failed to delete the defined entity for "
                                 f"cluster '{cluster_name}'", exc_info=True)

            self._update_task(BehaviorTaskStatus.ERROR,
                              message=msg,
                              error_message=str(err))
        except Exception as err:
            msg = f"Unknown error creating cluster '{cluster_name}: {str(err)}'"   # noqa: E501
            LOGGER.error(msg, exc_info=True)
            # TODO: Avoid many try-except block. Check if it is a good practice
            try:
                self._fail_operation(
                    cluster_id,
                    DefEntityOperation.CREATE)
            except Exception:
                msg = f"Failed to update defined entity status for cluster {cluster_id}"  # noqa: E501
                LOGGER.error(f"{msg}", exc_info=True)

            # NOTE: sync of the defined entity should happen before call to
            # resolving the defined entity to prevent possible missing
            # values in the defined entity
            try:
                self._sync_def_entity(cluster_id, vapp=vapp)
            except Exception:
                msg = f"Failed to sync defined entity for cluster {cluster_id}"  # noqa: E501
                LOGGER.error(f"{msg}", exc_info=True)

            self._update_task(BehaviorTaskStatus.ERROR,
                              message=msg,
                              error_message=str(err))
        finally:
            # TODO re-organize updating defined entity and task update as per
            # https://stackoverflow.com/questions/49099637/how-to-determine-if-an-exception-was-raised-once-youre-in-the-finally-block
            # noqa: E501
            self.context.end()

    @thread_utils.run_async
    def _monitor_resize(self, cluster_id: str, input_native_entity: rde_2_x.NativeEntity):  # noqa: E501
        """Triggers and monitors one or more async threads of resize.

        This method (or) thread triggers two async threads (for node
        addition and deletion) in parallel. It waits for both the threads to
        join before calling the resize operation complete.

        Performs below once child threads join back.
        - updates the defined entity
        - updates the task status to SUCCESS
        - ends the client context
        """
        cluster_name = None
        try:
            curr_rde: common_models.DefEntity = \
                self.entity_svc.get_entity(cluster_id)
            curr_native_entity: rde_2_x.NativeEntity = curr_rde.entity
            cluster_name = curr_rde.name
            current_spec: rde_2_x.ClusterSpec = \
                def_utils.construct_cluster_spec_from_entity_status(
                    curr_native_entity.status,
                    server_utils.get_rde_version_in_use())
            curr_worker_count: int = current_spec.topology.workers.count
            curr_nfs_count: int = current_spec.topology.nfs.count
            template_name = current_spec.distribution.template_name
            template_revision = current_spec.distribution.template_revision

            desired_worker_count: int = \
                input_native_entity.spec.topology.workers.count
            desired_nfs_count: int = \
                input_native_entity.spec.topology.nfs.count
            num_workers_to_add: int = desired_worker_count - curr_worker_count
            num_nfs_to_add: int = desired_nfs_count - curr_nfs_count

            if num_workers_to_add > 0 or num_nfs_to_add > 0:
                _get_template(name=template_name, revision=template_revision)
                self._create_nodes_async(input_native_entity)

                # TODO Below is the temporary fix to avoid parallel Recompose
                #  error between node creation and deletion threads. Below
                #  serializes the sequence of node creation and deletion.
                #  Remove the below block once the issue is fixed in pyvcloud.
                create_nodes_async_thread_name = \
                    thread_utils.generate_thread_name(self._create_nodes_async.__name__)  # noqa: E501
                for t in threading.enumerate():
                    if t.getName() == create_nodes_async_thread_name:
                        t.join()
            if num_workers_to_add < 0:
                self._delete_nodes_async(
                    cluster_id,
                    input_native_entity=input_native_entity)

            # Wait for the children threads of the current thread to join
            curr_thread_id = str(threading.current_thread().ident)
            for t in threading.enumerate():
                if t.getName().endswith(curr_thread_id):
                    t.join()

            # Handle deleting the dnat rule if the cluster was exposed and
            # the user's current desire is to un-expose the cluster
            desired_expose_state: bool = \
                input_native_entity.spec.settings.network.expose
            is_exposed: bool = current_spec.settings.network.expose
            unexpose: bool = is_exposed and not desired_expose_state
            unexpose_success: bool = False
            if unexpose:
                org_name: str = curr_native_entity.metadata.org_name
                ovdc_name: str = curr_native_entity.metadata.ovdc_name
                network_name: str = current_spec.settings.ovdc_network
                try:
                    # We need to get the internal IP via script and not rely
                    # on the value in status.nodes.control_plane.ip because
                    # the exposed cluster might have been converted from
                    # RDE 1.0 to RDE 2.0, and those clusters would have their
                    # control plane ip overwritten to the external ip.
                    vapp_href = curr_rde.externalId
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
                    nw_exp_helper.handle_delete_expose_dnat_rule(
                        client=self.context.client,
                        org_name=org_name,
                        ovdc_name=ovdc_name,
                        network_name=network_name,
                        cluster_name=cluster_name,
                        cluster_id=cluster_id)

                    # For pure RDE2.0 based clusters this step won't be
                    # necessary, but we might have exposed clusters that were
                    # converted from RDE 1.0 to RDE 2.0, since those clusters
                    # would have their control plane ip overwritten to the
                    # external ip, we need to set it back to the true
                    # internal ip.
                    curr_native_entity.status.nodes.control_plane.ip = control_plane_internal_ip  # noqa: E501

                    curr_native_entity.status.cloud_properties.exposed = False
                    curr_native_entity.status.external_ip = None
                    unexpose_success = True
                except Exception as err:
                    LOGGER.error(
                        f"Failed to unexpose cluster with error: {str(err)}",
                        exc_info=True
                    )

            # update the defined entity and the task status. Check if one of
            # the child threads had set the status to ERROR.
            curr_task_status = self.task_status
            msg = ''
            if curr_task_status == BehaviorTaskStatus.ERROR.value:
                # NOTE: Possible repetition of operation.
                # _create_node_async() and _delete_node_async() also
                # sets status to failed
                curr_native_entity.status.phase = str(
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
                curr_native_entity.status.phase = str(
                    DefEntityPhase(DefEntityOperation.UPDATE,
                                   DefEntityOperationStatus.SUCCEEDED))

            self._sync_def_entity(cluster_id, curr_rde)
            if curr_task_status != BehaviorTaskStatus.ERROR.value:
                self._update_task(BehaviorTaskStatus.SUCCESS, message=msg)
        except Exception as err:
            msg = f"Unexpected error while resizing nodes for {cluster_name}" \
                  f" ({cluster_id})"
            LOGGER.error(f"{msg}", exc_info=True)
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
                msg = f"Failed to sync defined entity of the cluster {cluster_id}"  # noqa: E501
                LOGGER.error(f"{msg}", exc_info=True)

            self._update_task(BehaviorTaskStatus.ERROR,
                              message=msg,
                              error_message=str(err))
        finally:
            # TODO re-organize updating defined entity and task update as per
            # https://stackoverflow.com/questions/49099637/how-to-determine-if-an-exception-was-raised-once-youre-in-the-finally-block
            # noqa: E501
            self.context.end()

    @thread_utils.run_async
    def _create_nodes_async(self, input_native_entity: rde_2_x.NativeEntity):
        """Create worker and/or nfs nodes in vCD.

        This method is executed by a thread in an asynchronous manner.
        Do's:
        - Update the defined entity in except blocks.
        - Can update the task status either to Running or Error
        Dont's:
        - Do not update the task status to SUCCESS. This will prevent other
        parallel threads if any to update the status. vCD interprets SUCCESS
        as a terminal state.
        - Do not end the context.client.

        Let the caller monitor thread or method to set SUCCESS task status,
         end the client context
        """
        vapp: Optional[vcd_vapp.VApp] = None
        cluster_name = None
        # Default value from rde_2_x model class
        rollback = True
        vapp_href = None
        sysadmin_client_v36 = self.context.get_sysadmin_client(
            api_version=DEFAULT_API_VERSION)
        cluster_id = input_native_entity.status.uid
        try:
            curr_rde: common_models.DefEntity = self.entity_svc.get_entity(cluster_id)  # noqa: E501
            curr_native_entity: rde_2_x.NativeEntity = curr_rde.entity
            vapp_href = curr_rde.externalId
            cluster_name = curr_native_entity.metadata.name
            current_spec: rde_2_x.ClusterSpec = \
                def_utils.construct_cluster_spec_from_entity_status(
                    curr_native_entity.status,
                    server_utils.get_rde_version_in_use())
            org_name = curr_native_entity.metadata.org_name
            ovdc_name = curr_native_entity.metadata.virtual_data_center_name
            curr_worker_count: int = current_spec.topology.workers.count
            curr_nfs_count: int = current_spec.topology.nfs.count

            # use the same settings with which cluster was originally created
            # viz., template, storage_profile, and network among others.
            worker_storage_profile = input_native_entity.spec.topology.workers.storage_profile  # noqa: E501
            worker_sizing_class = input_native_entity.spec.topology.workers.sizing_class  # noqa: E501
            nfs_storage_profile = input_native_entity.spec.topology.nfs.storage_profile  # noqa: E501
            nfs_sizing_class = input_native_entity.spec.topology.nfs.sizing_class  # noqa: E501
            network_name = input_native_entity.spec.settings.ovdc_network
            ssh_key = input_native_entity.spec.settings.ssh_key
            rollback = input_native_entity.spec.settings.rollback_on_failure
            template_name = input_native_entity.spec.distribution.template_name
            template_revision = input_native_entity.spec.distribution.template_revision  # noqa: E501
            template = _get_template(template_name, template_revision)

            # compute the values of workers and nfs to be added or removed
            desired_worker_count: int = input_native_entity.spec.topology.workers.count  # noqa: E501
            num_workers_to_add = desired_worker_count - curr_worker_count
            desired_nfs_count = input_native_entity.spec.topology.nfs.count
            num_nfs_to_add = desired_nfs_count - curr_nfs_count

            server_config = server_utils.get_server_runtime_config()
            catalog_name = server_config['broker']['catalog']
            client_v36 = self.context.get_client(
                api_version=DEFAULT_API_VERSION)
            org = vcd_utils.get_org(client_v36, org_name=org_name)
            ovdc = vcd_utils.get_vdc(client_v36, vdc_name=ovdc_name, org=org)
            vapp = vcd_vapp.VApp(client_v36, href=vapp_href)

            if num_workers_to_add > 0:
                msg = f"Creating {num_workers_to_add} workers from template" \
                      f"' {template_name}' (revision {template_revision}); " \
                      f"adding to cluster '{cluster_name}' ({cluster_id})"
                LOGGER.debug(msg)
                self._update_task(BehaviorTaskStatus.RUNNING, message=msg)
                worker_nodes = _add_nodes(
                    sysadmin_client_v36,
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
                self._update_task(BehaviorTaskStatus.RUNNING, message=msg)
                target_nodes = []
                for spec in worker_nodes['specs']:
                    target_nodes.append(spec['target_vm_name'])
                vapp.reload()
                _join_cluster(sysadmin_client_v36,
                              vapp,
                              target_nodes=target_nodes)
                msg = f"Added {num_workers_to_add} node(s) to cluster " \
                      f"{cluster_name}({cluster_id})"
                self._update_task(BehaviorTaskStatus.RUNNING, message=msg)
            if num_nfs_to_add > 0:
                msg = f"Creating {num_nfs_to_add} nfs node(s) from template " \
                      f"'{template_name}' (revision {template_revision}) " \
                      f"for cluster '{cluster_name}' ({cluster_id})"
                LOGGER.debug(msg)
                self._update_task(BehaviorTaskStatus.RUNNING, message=msg)
                _add_nodes(sysadmin_client_v36,
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
                self._update_task(BehaviorTaskStatus.RUNNING, message=msg)
            msg = f"Created {num_workers_to_add} workers & {num_nfs_to_add}" \
                  f" nfs nodes for '{cluster_name}' ({cluster_id}) "
            self._update_task(BehaviorTaskStatus.RUNNING, message=msg)
        except (exceptions.NodeCreationError, exceptions.ClusterJoiningError) as err:  # noqa: E501
            msg = f"Error adding nodes to cluster '{cluster_name}'"
            LOGGER.error(msg, exc_info=True)
            if rollback:
                msg = f"Error adding nodes to cluster '{cluster_name}' " \
                      f"({cluster_id}). Deleting nodes: {err.node_names} " \
                      f"(rollback=True)"
                self._update_task(BehaviorTaskStatus.RUNNING, message=msg)
                LOGGER.info(msg)
                try:
                    _delete_nodes(sysadmin_client_v36,
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
                LOGGER.error(f"{msg}", exc_info=True)

            # NOTE: Since the defined entity is assumed to be
            # resolved during cluster creation, there is no need
            # to resolve the defined entity again
            try:
                self._sync_def_entity(cluster_id, vapp=vapp)
            except Exception:
                msg = f"Failed to sync defined entity of the cluster {cluster_id}"  # noqa: E501
                LOGGER.error(f"{msg}", exc_info=True)

            self._update_task(BehaviorTaskStatus.ERROR,
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
                LOGGER.error(f"{msg}", exc_info=True)
            # NOTE: Since the defined entity is assumed to be
            # resolved during cluster creation, there is no need
            # to resolve the defined entity again
            try:
                self._sync_def_entity(cluster_id, vapp=vapp)
            except Exception:
                msg = f"Failed to sync defined entity of the cluster {cluster_id}"  # noqa: E501
                LOGGER.error(f"{msg}", exc_info=True)
            self._update_task(BehaviorTaskStatus.ERROR,
                              message=msg,
                              error_message=str(err))

    @thread_utils.run_async
    def _delete_cluster_async(self,
                              cluster_name: str,
                              org_name: str,
                              ovdc_name: str,
                              curr_rde: common_models.DefEntity):
        """Delete the cluster asynchronously.

        :param cluster_name: Name of the cluster to be deleted.
        :param org_name: Name of the org where the cluster resides.
        :param ovdc_name: Name of the ovdc where the cluster resides.
        """
        cluster_id = curr_rde.id
        try:
            msg = f"Deleting cluster '{cluster_name}'"
            self._update_task(BehaviorTaskStatus.RUNNING, message=msg)
            client_v36 = self.context.get_client(
                api_version=DEFAULT_API_VERSION
            )

            if curr_rde.externalId:
                # Delete Vapp if RDE is linked with a VApp
                _delete_vapp(client_v36, org_name, ovdc_name, cluster_name)

                curr_native_entity: rde_2_x.NativeEntity = curr_rde.entity
                cluster_name = curr_rde.name
                current_spec: rde_2_x.ClusterSpec = \
                    def_utils.construct_cluster_spec_from_entity_status(
                        curr_native_entity.status,
                        server_utils.get_rde_version_in_use())

                # Handle deleting dnat rule if cluster is exposed
                exposed: bool = current_spec.settings.network.expose
                dnat_delete_success: bool = False
                if exposed:
                    network_name: str = current_spec.settings.ovdc_network
                    try:
                        nw_exp_helper.handle_delete_expose_dnat_rule(
                            client=self.context.client,
                            org_name=org_name,
                            ovdc_name=ovdc_name,
                            network_name=network_name,
                            cluster_name=cluster_name,
                            cluster_id=cluster_id)
                        dnat_delete_success = True
                    except Exception as err:
                        LOGGER.error("Failed to delete dnat rule for "
                                     f"{cluster_name} ({cluster_id}) "
                                     f"with error: {str(err)}")

                msg = f"Deleted cluster '{cluster_name}'"
                if exposed and not dnat_delete_success:
                    msg += ' with failed dnat rule deletion'
            else:
                msg = f"VApp for cluster {cluster_name} ({cluster_id}) not present"  # noqa: E501

            LOGGER.info(msg)
            self._update_task(BehaviorTaskStatus.SUCCESS, message=msg)
        except Exception as err:
            msg = f"Unexpected error while deleting cluster {cluster_name}"
            LOGGER.error(f"{msg}", exc_info=True)
            try:
                self._fail_operation(cluster_id, DefEntityOperation.DELETE)
            except Exception:
                msg = f"Failed to update defined entity status for cluster {cluster_id}"  # noqa: E501
                LOGGER.error(msg, exc_info=True)
            self._update_task(BehaviorTaskStatus.ERROR,
                              message=msg,
                              error_message=str(err))
        finally:
            # TODO re-organize updating defined entity and task update as per
            # https://stackoverflow.com/questions/49099637/how-to-determine-if-an-exception-was-raised-once-youre-in-the-finally-block
            # noqa: E501
            self.context.end()

    @thread_utils.run_async
    def _upgrade_cluster_async(self, cluster_id: str, template: Dict):
        cluster_name = None
        vapp = None
        try:
            curr_rde: common_models.DefEntity = self.entity_svc.get_entity(cluster_id)  # noqa: E501
            curr_native_entity: rde_2_x.NativeEntity = curr_rde.entity
            cluster_name = curr_native_entity.metadata.name
            vapp_href = curr_rde.externalId

            # TODO use cluster status field to get the control plane and worker nodes  # noqa: E501
            client_v36 = self.context.get_client(
                api_version=DEFAULT_API_VERSION)
            vapp = vcd_vapp.VApp(client_v36, href=vapp_href)
            all_node_names = [vm.get('name') for vm in vapp.get_all_vms() if not vm.get('name').startswith(NodeType.NFS)]  # noqa: E501
            control_plane_node_names = [curr_native_entity.status.nodes.control_plane.name]  # noqa: E501
            worker_node_names = [worker.name for worker in curr_native_entity.status.nodes.workers]  # noqa: E501

            template_name = template[LocalTemplateKey.NAME]
            template_revision = template[LocalTemplateKey.REVISION]
            template_cookbook_version = semver.Version(template[LocalTemplateKey.COOKBOOK_VERSION])  # noqa: E501

            # semantic version doesn't allow leading zeros
            # docker's version format YY.MM.patch allows us to directly use
            # lexicographical string comparison
            c_docker = curr_native_entity.status.docker_version
            t_docker = template[LocalTemplateKey.DOCKER_VERSION]
            k8s_details = curr_native_entity.status.kubernetes.split(' ')
            c_k8s = semver.Version(k8s_details[-1])
            t_k8s = semver.Version(template[LocalTemplateKey.KUBERNETES_VERSION])  # noqa: E501
            cni_details = curr_native_entity.status.cni.split(' ')
            c_cni = semver.Version(cni_details[-1])
            t_cni = semver.Version(template[LocalTemplateKey.CNI_VERSION])

            upgrade_docker = t_docker > c_docker
            upgrade_k8s = t_k8s >= c_k8s
            upgrade_cni = t_cni > c_cni or t_k8s.major > c_k8s.major or t_k8s.minor > c_k8s.minor  # noqa: E501

            sysadmin_client_v36 = self.context.get_sysadmin_client(
                api_version=DEFAULT_API_VERSION)

            if upgrade_k8s:
                msg = f"Draining control plane node {control_plane_node_names}"
                self._update_task(BehaviorTaskStatus.RUNNING, message=msg)
                _drain_nodes(sysadmin_client_v36, vapp_href,
                             control_plane_node_names, cluster_name=cluster_name)  # noqa: E501

                msg = f"Upgrading Kubernetes ({c_k8s} -> {t_k8s}) " \
                      f"in control plane node {control_plane_node_names}"
                self._update_task(BehaviorTaskStatus.RUNNING, message=msg)
                filepath = ltm.get_script_filepath(template_cookbook_version,
                                                   template_name,
                                                   template_revision,
                                                   TemplateScriptFile.CONTROL_PLANE_K8S_UPGRADE)  # noqa: E501
                script = utils.read_data_file(filepath, logger=LOGGER)
                _run_script_in_nodes(sysadmin_client_v36, vapp_href,
                                     control_plane_node_names, script)

                msg = f"Uncordoning control plane node {control_plane_node_names}"  # noqa: E501
                self._update_task(BehaviorTaskStatus.RUNNING, message=msg)
                _uncordon_nodes(sysadmin_client_v36,
                                vapp_href,
                                control_plane_node_names,
                                cluster_name=cluster_name)

                filepath = ltm.get_script_filepath(template_cookbook_version,
                                                   template_name,
                                                   template_revision,
                                                   TemplateScriptFile.WORKER_K8S_UPGRADE)  # noqa: E501
                script = utils.read_data_file(filepath, logger=LOGGER)
                for node in worker_node_names:
                    msg = f"Draining node {node}"
                    self._update_task(BehaviorTaskStatus.RUNNING,
                                      message=msg)
                    _drain_nodes(sysadmin_client_v36,
                                 vapp_href,
                                 [node],
                                 cluster_name=cluster_name)

                    msg = f"Upgrading Kubernetes ({c_k8s} " \
                          f"-> {t_k8s}) in node {node}"
                    self._update_task(BehaviorTaskStatus.RUNNING,
                                      message=msg)
                    _run_script_in_nodes(sysadmin_client_v36,
                                         vapp_href, [node], script)

                    msg = f"Uncordoning node {node}"
                    self._update_task(BehaviorTaskStatus.RUNNING,
                                      message=msg)
                    _uncordon_nodes(sysadmin_client_v36,
                                    vapp_href, [node],
                                    cluster_name=cluster_name)

            if upgrade_docker or upgrade_cni:
                msg = f"Draining all nodes {all_node_names}"
                self._update_task(BehaviorTaskStatus.RUNNING, message=msg)
                _drain_nodes(sysadmin_client_v36,
                             vapp_href, all_node_names,
                             cluster_name=cluster_name)

            if upgrade_docker:
                msg = f"Upgrading Docker-CE ({c_docker} -> {t_docker}) " \
                      f"in nodes {all_node_names}"
                self._update_task(BehaviorTaskStatus.RUNNING, message=msg)
                filepath = ltm.get_script_filepath(
                    template_cookbook_version,
                    template_name,
                    template_revision,
                    TemplateScriptFile.DOCKER_UPGRADE)
                script = utils.read_data_file(filepath, logger=LOGGER)
                _run_script_in_nodes(sysadmin_client_v36, vapp_href,
                                     all_node_names, script)

            if upgrade_cni:
                msg = "Applying CNI " \
                      f"({curr_native_entity.status.cni} " \
                      f"-> {t_cni}) in control plane node {control_plane_node_names}"  # noqa: E501
                self._update_task(BehaviorTaskStatus.RUNNING, message=msg)
                filepath = ltm.get_script_filepath(template_cookbook_version,
                                                   template_name,
                                                   template_revision,
                                                   TemplateScriptFile.CONTROL_PLANE_CNI_APPLY)  # noqa: E501
                script = utils.read_data_file(filepath, logger=LOGGER)
                _run_script_in_nodes(sysadmin_client_v36, vapp_href,
                                     control_plane_node_names, script)

            # uncordon all nodes (sometimes redundant)
            msg = f"Uncordoning all nodes {all_node_names}"
            self._update_task(BehaviorTaskStatus.RUNNING, message=msg)
            _uncordon_nodes(sysadmin_client_v36, vapp_href,
                            all_node_names, cluster_name=cluster_name)

            # update cluster metadata
            msg = f"Updating metadata for cluster '{cluster_name}'"
            self._update_task(BehaviorTaskStatus.RUNNING, message=msg)
            metadata = {
                ClusterMetadataKey.TEMPLATE_NAME: template[LocalTemplateKey.NAME],  # noqa: E501
                ClusterMetadataKey.TEMPLATE_REVISION: template[LocalTemplateKey.REVISION],  # noqa: E501
                ClusterMetadataKey.DOCKER_VERSION: template[LocalTemplateKey.DOCKER_VERSION],  # noqa: E501
                ClusterMetadataKey.KUBERNETES_VERSION: template[LocalTemplateKey.KUBERNETES_VERSION],  # noqa: E501
                ClusterMetadataKey.CNI: template[LocalTemplateKey.CNI],
                ClusterMetadataKey.CNI_VERSION: template[LocalTemplateKey.CNI_VERSION]  # noqa: E501
            }

            task = vapp.set_multiple_metadata(metadata)
            client_v36 = self.context.get_client(
                api_version=DEFAULT_API_VERSION)
            client_v36.get_task_monitor().wait_for_status(task)

            curr_rde_status: rde_2_x.Status = curr_native_entity.status
            # update defined entity of the cluster
            curr_rde_status.cloud_properties.distribution = \
                rde_2_x.Distribution(template_name=template[LocalTemplateKey.NAME],  # noqa: E501
                                     template_revision=int(template[LocalTemplateKey.REVISION]))  # noqa: E501
            curr_rde_status.cni = \
                _create_k8s_software_string(template[LocalTemplateKey.CNI],
                                            template[LocalTemplateKey.CNI_VERSION])  # noqa: E501
            curr_rde_status.kubernetes = \
                _create_k8s_software_string(template[LocalTemplateKey.KUBERNETES],  # noqa: E501
                                            template[LocalTemplateKey.KUBERNETES_VERSION])  # noqa: E501
            curr_rde_status.docker_version = template[LocalTemplateKey.DOCKER_VERSION]  # noqa: E501
            curr_rde_status.os = template[LocalTemplateKey.OS]
            curr_rde_status.phase = str(
                DefEntityPhase(DefEntityOperation.UPGRADE,
                               DefEntityOperationStatus.SUCCEEDED))
            self._update_cluster_entity(cluster_id, curr_rde_status)

            msg = f"Successfully upgraded cluster '{cluster_name}' software " \
                  f"to match template {template_name} (revision " \
                  f"{template_revision}): Kubernetes: {c_k8s} -> {t_k8s}, " \
                  f"Docker-CE: {c_docker} -> {t_docker}, " \
                  f"CNI: {c_cni} -> {t_cni}"
            self._update_task(BehaviorTaskStatus.SUCCESS, message=msg)
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
                msg = f"Failed to sync defined entity of the cluster {cluster_id}"  # noqa: E501
                LOGGER.error(f"{msg}", exc_info=True)
            self._update_task(BehaviorTaskStatus.ERROR,
                              message=msg, error_message=str(err))

        finally:
            # TODO re-organize updating defined entity and task update as per
            # https://stackoverflow.com/questions/49099637/how-to-determine-if-an-exception-was-raised-once-youre-in-the-finally-block
            # noqa: E501
            self.context.end()

    @thread_utils.run_async
    def _monitor_delete_nodes(self, cluster_id, nodes_to_del):
        """Triggers and monitors delete thread.

        This method (or) thread waits for the thread(s) to join before
        - updating the defined entity
        - updating the task status to SUCCESS
        - ending the client context
        """
        cluster_name = None
        try:
            curr_rde: common_models.DefEntity = self.entity_svc.get_entity(
                cluster_id)
            curr_native_entity: rde_2_x.NativeEntity = curr_rde.entity
            self._delete_nodes_async(cluster_id=cluster_id,
                                     nodes_to_del=nodes_to_del)

            # wait for the children threads of the current thread to join
            curr_thread_id = str(threading.current_thread().ident)
            for t in threading.enumerate():
                if t.getName().endswith(curr_thread_id):
                    t.join()

            # update the defined entity and task status.
            curr_task_status = self.task_status
            msg = ''
            if curr_task_status == BehaviorTaskStatus.ERROR.value:
                curr_native_entity.status.phase = str(
                    DefEntityPhase(DefEntityOperation.UPDATE,
                                   DefEntityOperationStatus.FAILED))
            else:
                msg = f"Deleted the {nodes_to_del} nodes  from cluster " \
                      f"'{cluster_name}' ({cluster_id}) "
                curr_native_entity.status.phase = str(
                    DefEntityPhase(DefEntityOperation.UPDATE,
                                   DefEntityOperationStatus.SUCCEEDED))
            self._sync_def_entity(cluster_id, curr_rde)
            if curr_task_status != BehaviorTaskStatus.ERROR.value:
                self._update_task(BehaviorTaskStatus.SUCCESS, message=msg)

        except Exception as err:
            msg = f"Unexpected error while deleting nodes for " \
                  f"{cluster_name} ({cluster_id})"
            LOGGER.error(f"{msg}", exc_info=True)
            try:
                self._fail_operation(
                    cluster_id,
                    DefEntityOperation.UPDATE)
            except Exception:
                msg = f"Failed to update defined entity status " \
                      f" for cluster {cluster_id}"
                LOGGER.error(f"{msg}", exc_info=True)

            try:
                self._sync_def_entity(cluster_id)
            except Exception:
                msg = f"Failed to sync defined entity of the cluster {cluster_id}"  # noqa: E501
                LOGGER.error(f"{msg}", exc_info=True)
            self._update_task(BehaviorTaskStatus.ERROR,
                              message=msg,
                              error_message=str(err))
        finally:
            # TODO re-organize updating defined entity and task update as per
            # https://stackoverflow.com/questions/49099637/how-to-determine-if-an-exception-was-raised-once-youre-in-the-finally-block
            # noqa: E501
            self.context.end()

    @thread_utils.run_async
    def _delete_nodes_async(self, cluster_id: str,
                            input_native_entity: rde_2_x.NativeEntity = None,
                            nodes_to_del=None):
        """Delete worker and/or nfs nodes in vCD.

        This method is executed by a thread in an asynchronous manner.
        Do's:
        - Update the defined entity in except blocks.
        - Update the task status either to Running or Error
        Dont's:
        - Do not update the task status to SUCCESS. This will prevent other
        parallel threads if any to update the status. vCD interprets SUCCESS
        as a terminal state.
        - Do not end the context.client.

        Let the caller monitor thread or method to set SUCCESS task status,
          end the client context
        """
        # cluster_id = input_native_entity.status.uid
        if nodes_to_del is None:
            nodes_to_del = []
        curr_rde: common_models.DefEntity = self.entity_svc.get_entity(cluster_id)  # noqa: E501
        curr_native_entity: rde_2_x.NativeEntity = curr_rde.entity
        vapp_href = curr_rde.externalId
        cluster_name = curr_native_entity.metadata.name

        if not nodes_to_del:
            if not input_native_entity:
                raise exceptions.CseServerError(
                    f"No nodes specified to delete from "
                    f"cluster {cluster_name}({cluster_id})")
            desired_worker_count = input_native_entity.spec.topology.workers.count  # noqa: E501
            nodes_to_del = [node.name for node in
                            curr_native_entity.status.nodes.workers[desired_worker_count:]]  # noqa: E501

        client_v36 = self.context.get_client(api_version=DEFAULT_API_VERSION)
        vapp = vcd_vapp.VApp(client_v36, href=vapp_href)
        try:
            # if nodes fail to drain, continue with node deletion anyways
            sysadmin_client_v36 = self.context.get_sysadmin_client(
                api_version=DEFAULT_API_VERSION)
            try:
                worker_nodes_to_delete = [
                    node_name for node_name in nodes_to_del
                    if node_name.startswith(NodeType.WORKER)]
                if worker_nodes_to_delete:
                    msg = f"Draining {len(worker_nodes_to_delete)} node(s) " \
                          f"from cluster '{cluster_name}': " \
                          f"{worker_nodes_to_delete}"
                    self._update_task(
                        BehaviorTaskStatus.RUNNING, message=msg)
                    _drain_nodes(sysadmin_client_v36,
                                 vapp_href,
                                 worker_nodes_to_delete,
                                 cluster_name=cluster_name)
            except (exceptions.NodeOperationError, exceptions.ScriptExecutionError) as err:  # noqa: E501
                LOGGER.warning(f"Failed to drain nodes: {nodes_to_del}"
                               f" in cluster '{cluster_name}'."
                               f" Continuing node delete...\nError: {err}")

            msg = f"Deleting {len(nodes_to_del)} node(s) from " \
                  f"cluster '{cluster_name}': {nodes_to_del}"
            self._update_task(BehaviorTaskStatus.RUNNING, message=msg)

            _delete_nodes(sysadmin_client_v36,
                          vapp_href,
                          nodes_to_del,
                          cluster_name=cluster_name)

            msg = f"Deleted {len(nodes_to_del)} node(s)" \
                  f" to cluster '{cluster_name}'"
            self._update_task(BehaviorTaskStatus.RUNNING, message=msg)
        except Exception as err:
            msg = f"Unexpected error while deleting nodes {nodes_to_del}"
            LOGGER.error(f"{msg}", exc_info=True)
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
                msg = f"Failed to sync defined entity of the cluster {cluster_id}"  # noqa: E501
                LOGGER.error(f"{msg}", exc_info=True)
            self._update_task(BehaviorTaskStatus.ERROR,
                              message=msg,
                              error_message=str(err))

    def _sync_def_entity(self, cluster_id: str,
                         curr_rde: common_models.DefEntity = None,
                         vapp=None):
        """Sync the defined entity with the latest vApp status."""
        # NOTE: This function should not be used to update the defined entity
        # unless it is sure that the Vapp with the cluster-id exists
        if not curr_rde:
            curr_rde: common_models.DefEntity = \
                self.entity_svc.get_entity(cluster_id)
        if not curr_rde.externalId and not vapp:
            return curr_rde
        if not vapp:
            client_v36 = self.context.get_client(
                api_version=DEFAULT_API_VERSION)
            vapp = vcd_vapp.VApp(client_v36, href=curr_rde.externalId)

        sysadmin_client_v36 = self.context.get_sysadmin_client(
            api_version=DEFAULT_API_VERSION)
        curr_nodes_status = _get_nodes_details(sysadmin_client_v36, vapp)

        new_status: rde_2_x.Status = curr_rde.entity.status
        if curr_nodes_status:
            new_status.nodes = curr_nodes_status
        return self._update_cluster_entity(cluster_id, new_status)

    def _update_cluster_entity(self, cluster_id: str,
                               native_entity_status: rde_2_x.Status,
                               external_id: Optional[str] = None):
        """Update status part of the cluster rde.

        This method serves as a placeholder where we make changes for
        optimistic locking.

        :param str cluster_id: ID of the defined entity.
        :param rde_2_x.Status native_entity_status: Defined entity status to be
            updated.
        :param str external_id: Vapp ID to update the defined entity of the
            cluster with.
        :returns: Updated defined entity
        :rtype: common_models.DefEntity
        """
        # TODO update function to use optimistic locking feature by VCD

        cluster_rde: common_models.DefEntity = \
            self.entity_svc.get_entity(cluster_id)

        # update the cluster_rde with external_id if provided by the caller
        if external_id is not None:
            cluster_rde.externalId = external_id
        # Update entity status with new values
        cluster_rde.entity.status = native_entity_status

        # Update cluster rde
        return self.sysadmin_entity_svc.update_entity(
            cluster_id, cluster_rde, invoke_hooks=False
        )

    def _fail_operation(self, cluster_id: str, op: DefEntityOperation):
        curr_rde: common_models.DefEntity = self.entity_svc.get_entity(cluster_id)  # noqa: E501
        new_status: rde_2_x.Status = curr_rde.entity.status
        new_status.phase = \
            str(DefEntityPhase(op, DefEntityOperationStatus.FAILED))
        self._update_cluster_entity(curr_rde.id, new_status)

    def _update_task(self, status, message='', error_message='', progress=None):  # noqa: E501
        if status == BehaviorTaskStatus.ERROR:
            error_details = asdict(BehaviorError(majorErrorCode='500',
                                                 minorErrorCode=message,
                                                 message=error_message))
            payload = self.mqtt_publisher.construct_behavior_payload(
                status=status.value, error_details=error_details)
        else:
            payload = self.mqtt_publisher.construct_behavior_payload(
                status=status.value, message=message, progress=progress)
        response_json = self.mqtt_publisher.construct_behavior_response_json(
            task_id=self.task_id, entity_id=self.entity_id, payload=payload)
        LOGGER.debug(f"Sending behavior response:{response_json}")
        self.mqtt_publisher.send_response(response_json)
        self.task_status = status.value

    def _replace_kubeconfig_expose_ip(self, internal_ip: str, cluster_id: str,
                                      vapp: vcd_vapp.VApp):
        # Form kubeconfig with internal ip
        kubeconfig_with_exposed_ip = self.get_cluster_config(cluster_id)
        script = \
            nw_exp_helper.construct_script_to_update_kubeconfig_with_internal_ip(  # noqa: E501
                kubeconfig_with_exposed_ip=kubeconfig_with_exposed_ip,
                internal_ip=internal_ip
            )

        node_names = _get_node_names(vapp, NodeType.CONTROL_PLANE)
        result = _execute_script_in_nodes(
            self.context.sysadmin_client,
            vapp=vapp,
            node_names=node_names,
            script=script,
            check_tools=True
        )

        errors = _get_script_execution_errors(result)
        if errors:
            raise exceptions.ScriptExecutionError(
                f"Failed to overwrite kubeconfig with internal ip: "
                f"{internal_ip}: {errors}"
            )


def _get_cluster_upgrade_target_templates(
        source_template_name, source_template_revision) -> List[dict]:
    """Get list of templates that a given cluster can upgrade to.

    :param str source_template_name:
    :param str source_template_revision:
    :return: List of dictionary containing templates
    :rtype: List[dict]
    """
    upgrades = []
    config = server_utils.get_server_runtime_config()
    for t in config['broker']['templates']:
        if source_template_name in t[LocalTemplateKey.UPGRADE_FROM]:
            if t[LocalTemplateKey.NAME] == source_template_name and \
                    int(t[LocalTemplateKey.REVISION]) <= int(source_template_revision):  # noqa: E501
                continue
            upgrades.append(t)

    return upgrades


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
            vcd_utils.to_dict(vm)
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
            storage_profile: Optional[str] = None
            if hasattr(vm, 'StorageProfile'):
                storage_profile = vm.StorageProfile.get('name')
            if vm_name.startswith(NodeType.CONTROL_PLANE):
                control_plane = rde_2_x.Node(name=vm_name, ip=ip,
                                             sizing_class=sizing_class,
                                             storage_profile=storage_profile)
            elif vm_name.startswith(NodeType.WORKER):
                workers.append(
                    rde_2_x.Node(name=vm_name, ip=ip,
                                 sizing_class=sizing_class,
                                 storage_profile=storage_profile))
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
                nfs_nodes.append(rde_2_x.NfsNode(name=vm_name, ip=ip,
                                                 sizing_class=sizing_class,
                                                 storage_profile=storage_profile,  # noqa: E501
                                                 exports=exports))
        return rde_2_x.Nodes(control_plane=control_plane, workers=workers,
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
                     f"error: {err}", exc_info=True)
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
                     f"with error: {err}", exc_info=True)
        raise

    LOGGER.debug(f"Successfully uncordoned nodes {node_names} in cluster "
                 f"'{cluster_name}' (vapp: {vapp_href})")


def _delete_vapp(client, org_name, ovdc_name, vapp_name):
    LOGGER.debug(
        f"Deleting vapp {vapp_name} in (org: {org_name}, vdc: {ovdc_name})")

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
                     f"(vdc: {ovdc_name}) with error: {err}", exc_info=True)
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
        if org_name is not None and org_name.lower() != SYSTEM_ORG_NAME.lower():  # noqa: E501
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

            config = server_utils.get_server_runtime_config()
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
                if sizing_class_href:
                    spec['sizing_policy_href'] = sizing_class_href
                    spec['placement_policy_href'] = config['placement_policy_hrefs'][template[LocalTemplateKey.KIND]]  # noqa: E501
                if cust_script is not None:
                    spec['cust_script'] = cust_script
                if storage_profile is not None:
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
                        semver.Version(template[LocalTemplateKey.COOKBOOK_VERSION]),  # noqa: E501
                        template[LocalTemplateKey.NAME],
                        template[LocalTemplateKey.REVISION],
                        TemplateScriptFile.NFSD)
                    script = utils.read_data_file(script_filepath, logger=LOGGER)  # noqa: E501
                    exec_results = _execute_script_in_nodes(
                        sysadmin_client, vapp=vapp, node_names=[vm_name],
                        script=script)
                    errors = _get_script_execution_errors(exec_results)
                    if errors:
                        raise exceptions.ScriptExecutionError(
                            f"VM customization script execution failed "
                            f"on node {vm_name}:{errors}")
        except Exception as err:
            LOGGER.error(err, exc_info=True)
            # TODO: get details of the exception to determine cause of failure,
            # e.g. not enough resources available.
            node_list = [entry.get('target_vm_name') for entry in specs]
            if hasattr(err, 'vcd_error') and err.vcd_error is not None and \
                    "throwPolicyNotAvailableException" in err.vcd_error.get('stackTrace', ''):  # noqa: E501
                raise exceptions.NodeCreationError(
                    node_list,
                    f"OVDC not enabled for {template[LocalTemplateKey.KIND]}")  # noqa: E501

            raise exceptions.NodeCreationError(node_list, str(err))

        vapp.reload()
        return {'task': task, 'specs': specs}


def _get_node_names(vapp, node_type):
    return [vm.get('name') for vm in vapp.get_all_vms() if vm.get('name').startswith(node_type)]  # noqa: E501


def _get_control_plane_ip(sysadmin_client: vcd_client.Client, vapp,
                          check_tools=False):
    vcd_utils.raise_error_if_user_not_from_system_org(sysadmin_client)

    LOGGER.debug(f"Getting control_plane IP for vapp: "
                 f"{vapp.get_resource().get('name')}")
    script = "#!/usr/bin/env bash\n" \
             "ip route get 1 | awk '{print $NF;exit}'\n" \

    node_names = _get_node_names(vapp, NodeType.CONTROL_PLANE)
    result = _execute_script_in_nodes(sysadmin_client, vapp=vapp,
                                      node_names=node_names, script=script,
                                      check_tools=check_tools)
    errors = _get_script_execution_errors(result)
    if errors:
        raise exceptions.ScriptExecutionError(
            "Get control plane IP script execution "
            "failed on control plane node "
            f"{node_names}:{errors}")
    control_plane_ip = result[0][1].content.decode().split()[0]
    LOGGER.debug(f"Retrieved control plane IP for vapp: "
                 f"{vapp.get_resource().get('name')}, ip: {control_plane_ip}")
    return control_plane_ip


def _init_cluster(sysadmin_client: vcd_client.Client, vapp, cluster_kind,
                  k8s_version, cni_version, expose_ip=None):
    vcd_utils.raise_error_if_user_not_from_system_org(sysadmin_client)

    try:
        templated_script = get_cluster_script_file_contents(
            ClusterScriptFile.CONTROL_PLANE, ClusterScriptFile.VERSION_2_X)
        script = templated_script.format(
            cluster_kind=cluster_kind,
            k8s_version=k8s_version,
            cni_version=cni_version)

        # Expose cluster if given external ip
        if expose_ip:
            script = \
                nw_exp_helper.construct_init_cluster_script_with_exposed_ip(
                    script, expose_ip
                )

        node_names = _get_node_names(vapp, NodeType.CONTROL_PLANE)
        result = _execute_script_in_nodes(sysadmin_client, vapp=vapp,
                                          node_names=node_names, script=script)
        errors = _get_script_execution_errors(result)
        if errors:
            raise exceptions.ScriptExecutionError(
                f"Initialize cluster script execution failed on node "
                f"{node_names}:{errors}")
        if result[0][0] != 0:
            raise exceptions.ClusterInitializationError(f"Couldn't initialize cluster:\n{result[0][2].content.decode()}")  # noqa: E501
    except Exception as err:
        LOGGER.error(err, exc_info=True)
        raise exceptions.ClusterInitializationError(
            f"Couldn't initialize cluster: {str(err)}")


def _join_cluster(sysadmin_client: vcd_client.Client, vapp, target_nodes=None):
    vcd_utils.raise_error_if_user_not_from_system_org(sysadmin_client)
    try:

        script = """
                 #!/usr/bin/env bash
                 kubeadm token create --print-join-command
            """

        node_names = _get_node_names(vapp, NodeType.CONTROL_PLANE)
        control_plane_result = _execute_script_in_nodes(sysadmin_client,
                                                        vapp=vapp,
                                                        node_names=node_names,
                                                        script=script)
        errors = _get_script_execution_errors(control_plane_result)
        if errors:
            raise exceptions.ClusterJoiningError(
                "Join cluster script execution failed on "
                f"control plane node {node_names}:{errors}")
        # kubeadm join <ip:port> --token <token> --discovery-token-ca-cert-hash <discovery_token> # noqa: E501
        join_info = control_plane_result[0][1].content.decode().split()

        templated_script = get_cluster_script_file_contents(
            ClusterScriptFile.NODE, ClusterScriptFile.VERSION_2_X)
        script = templated_script.format(
            ip_port=join_info[2],
            token=join_info[4],
            discovery_token_ca_cert_hash=join_info[6])

        node_names = _get_node_names(vapp, NodeType.WORKER)
        if target_nodes is not None:
            node_names = [name for name in node_names if name in target_nodes]

        worker_results = _execute_script_in_nodes(sysadmin_client, vapp=vapp,
                                                  node_names=node_names,
                                                  script=script)
        errors = _get_script_execution_errors(worker_results)
        if errors:
            raise exceptions.ClusterJoiningError(
                "Join cluster script execution failed "
                f"on worker node  {node_names}:{errors}")
        for result in worker_results:
            if result[0] != 0:
                raise exceptions.ClusterJoiningError(
                    "Couldn't join cluster:\n"
                    f"{result[2].content.decode()}")
    except Exception as err:
        LOGGER.error(err, exc_info=True)
        raise exceptions.ClusterJoiningError(
            f"Couldn't join cluster: {str(err)}")


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
        raise exceptions.CseServerError('VM is not ready to execute scripts')


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
        except Exception as err:
            msg = f"Error executing script in node {node_name}: {str(err)}"
            LOGGER.error(msg, exc_info=True)
            raise exceptions.ScriptExecutionError(msg)  # noqa: E501

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
        raise exceptions.ScriptExecutionError(
            "Script execution failed on node "
            f"{node_names}\nErrors: {errors}")
    if results[0][0] != 0:
        raise exceptions.NodeOperationError(
            "Error during node operation:\n"
            f"{results[0][2].content.decode()}")


def _get_script_execution_errors(results):
    return [result[2].content.decode() for result in results if result[0] != 0]


def _create_k8s_software_string(software_name: str, software_version: str) -> str:  # noqa: E501
    """Generate string containing the software name and version.

    Example: if software_name is "upstream" and version is "1.17.3",
        "upstream 1.17.3" is returned

    :param str software_name:
    :param str software_version:
    :rtype: str
    """
    return f"{software_name} {software_version}"

# container-service-extension
# Copyright (c) 2021 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

from pyvcloud.vcd.client import Client
from pyvcloud.vcd.vdc import VDC

from container_service_extension.common.constants.server_constants import FlattenedClusterSpecKey2X  # noqa: E501
from container_service_extension.common.constants.server_constants import VALID_UPDATE_FIELDS_2X  # noqa: E501
from container_service_extension.common.utils.pyvcloud_utils import get_vdc  # noqa: E501
from container_service_extension.exception.exceptions import BadRequestError
from container_service_extension.lib.cloudapi.cloudapi_client import CloudApiClient  # noqa: E501
from container_service_extension.rde.behaviors.behavior_model import BehaviorOperation  # noqa: E501
from container_service_extension.rde.common.entity_service import DefEntityService  # noqa: E501
import container_service_extension.rde.constants as rde_constants
from container_service_extension.rde.models import rde_factory
from container_service_extension.rde.models.abstractNativeEntity import AbstractNativeEntity  # noqa: E501
import container_service_extension.rde.models.rde_2_1_0 as rde_2_1_0
import container_service_extension.rde.utils as rde_utils
from container_service_extension.rde.validators.abstract_validator import AbstractValidator  # noqa: E501


class Validator_2_1_0(AbstractValidator):
    def __init__(self):
        pass

    def validate(
            self,
            cloudapi_client: CloudApiClient,
            sysadmin_client: Client,
            entity_id: str = None,
            entity: dict = None,
            operation: BehaviorOperation = BehaviorOperation.CREATE_CLUSTER,
            **kwargs
    ) -> bool:
        """Validate the input request.

        This method performs
        1. Basic validation of the entity by simply casting the input entity
        dict to the model class dictated by the api_version specified in the
        request. This is usually performed for the "create" operation.
        2. Operation (create, update, delete) specific validation.
        - create: "entity" is the only required parameter.
        - update: both "entity" and "entity_id" are required parameters.
        - delete: "entity_id" is the only required parameter.
        - kubeconfig: "entity_id" is the only required parameter.

        :param cloudapi_client: cloud api client
        :param sysadmin_client:
        :param dict entity: dict form of the native entity to be validated
        :param entity_id: entity id to be validated
        :param BehaviorOperation operation: CSE operation key
        :return: is validation successful or failure
        :rtype: bool
        """
        is_tkgm_cluster = kwargs.get('is_tkgm_cluster', False)
        if not entity_id and not entity:
            raise ValueError('Either entity_id or entity is required to validate.')  # noqa: E501
        entity_svc = DefEntityService(cloudapi_client=cloudapi_client)

        api_version: str = cloudapi_client.get_api_version()
        rde_version_introduced_at_api_version: str = rde_utils.get_rde_version_introduced_at_api_version(api_version)  # noqa: E501

        # TODO Reject the request if payload_version does not match with
        #  either rde_in_use (or) rde_version_introduced_at_api_version

        # Cast the entity to the model class based on the user-specified
        # api_version. This can be considered as a basic request validation.
        # Any operation specific validation is handled further down
        native_entity_class: AbstractNativeEntity = rde_factory. \
            get_rde_model(rde_version_introduced_at_api_version)
        input_entity = None
        if entity:
            try:
                input_entity: AbstractNativeEntity = native_entity_class.from_dict(entity)  # noqa: E501
            except Exception as err:
                msg = f"Failed to parse request body: {err}"
                raise BadRequestError(msg)

        # Need to ensure that sizing class along with cpu/memory is not
        # present in the request
        if isinstance(input_entity, rde_2_1_0.NativeEntity):
            # cpu and mem are properties of only rde 2.0.0
            bad_request_msg = ""
            if input_entity.spec.topology.workers.sizing_class and \
                    (input_entity.spec.topology.workers.cpu or input_entity.spec.topology.workers.memory):  # noqa: E501
                bad_request_msg = "Cannot specify both sizing class and cpu/memory for Workers nodes."  # noqa: E501
            if input_entity.spec.topology.control_plane.sizing_class and (input_entity.spec.topology.control_plane.cpu or input_entity.spec.topology.control_plane.memory):  # noqa: E501
                bad_request_msg = "Cannot specify both sizing class and cpu/memory for Control Plane nodes."  # noqa: E501
            if bad_request_msg:
                raise BadRequestError(bad_request_msg)
        # Return True if the operation is not specified.
        if operation == BehaviorOperation.CREATE_CLUSTER:
            return True

        # TODO: validators for rest of the CSE operations in V36 will be
        #  implemented as and when v36/def_cluster_handler.py get other handler
        #  functions
        if operation == BehaviorOperation.UPDATE_CLUSTER:
            if not entity_id or not entity:
                raise ValueError('Both entity_id and entity are required to validate the Update operation.')  # noqa: E501
            current_entity: AbstractNativeEntity = entity_svc.get_entity(entity_id).entity  # noqa: E501
            input_entity_spec: rde_2_1_0.ClusterSpec = input_entity.spec
            current_entity_status: rde_2_1_0.Status = current_entity.status
            is_tkgm_with_default_sizing_in_control_plane = False
            is_tkgm_with_default_sizing_in_workers = False
            if is_tkgm_cluster:
                # NOTE: Since for TKGm cluster, if cluster is created without
                # a sizing class, default sizing class is assigned by VCD,
                # If we find the default sizing policy in the status section,
                # validate cpu/memory and sizing policy.
                # Also note that at this point in code, we are sure that only
                # one of sizing class or cpu/mem will be associated with
                # control plane and workers.
                vdc: VDC = get_vdc(
                    sysadmin_client,
                    vdc_name=current_entity_status.cloud_properties.virtual_data_center_name,  # noqa: E501
                    org_name=current_entity_status.cloud_properties.org_name)
                vdc_resource = vdc.get_resource_admin()
                default_cp_name = vdc_resource.DefaultComputePolicy.get('name')
                control_plane_sizing_class = current_entity_status.nodes.control_plane.sizing_class  # noqa: E501
                is_tkgm_with_default_sizing_in_control_plane = \
                    (control_plane_sizing_class == default_cp_name)
                is_tkgm_with_default_sizing_in_workers = \
                    (len(current_entity_status.nodes.workers) > 0
                     and current_entity_status.nodes.workers[0].sizing_class == default_cp_name)  # noqa: E501
            current_entity_spec = \
                rde_utils.construct_cluster_spec_from_entity_status(
                    current_entity_status,
                    rde_constants.RDEVersion.RDE_2_1_0.value,
                    is_tkgm_with_default_sizing_in_control_plane=is_tkgm_with_default_sizing_in_control_plane,  # noqa: E501
                    is_tkgm_with_default_sizing_in_workers=is_tkgm_with_default_sizing_in_workers)  # noqa: E501
            return validate_cluster_update_request_and_check_cluster_upgrade(
                input_entity_spec,
                current_entity_spec,
                is_tkgm_cluster
            )

        # TODO check the reason why there was an unreachable raise statement
        raise NotImplementedError(f"Validator for {operation.name} not found")


def validate_cluster_update_request_and_check_cluster_upgrade(
        input_spec: rde_2_1_0.ClusterSpec,
        reference_spec: rde_2_1_0.ClusterSpec,
        is_tkgm_cluster: bool,
) -> bool:
    """
    Validate the desired spec with curr spec and check if upgrade operation.

    :param dict input_spec: input spec
    :param dict reference_spec: reference spec to validate the desired spec
    :param bool is_tkgm_cluster: True implies that this is a TKGm cluster
    :return: true if cluster operation is upgrade and false if operation is
        resize
    :rtype: bool
    :raises: BadRequestError for invalid payload.
    """
    # Since these fields are only in the spec section, and since we create
    # the reference_spec section from a status section, we will always have
    # null for the POD and SVC CIDRs. Hence we cannot validate it until there
    # is a better way to get the spec details.
    exclude_fields = [
        FlattenedClusterSpecKey2X.POD_CIDR.value,
        FlattenedClusterSpecKey2X.SVC_CIDR.value,
    ]

    if reference_spec.topology.workers.count == 0:
        # Exclude worker nodes' sizing class and storage profile from
        # validation if worker count is 0
        exclude_fields.append(FlattenedClusterSpecKey2X.WORKERS_SIZING_CLASS.value)  # noqa: E501
        exclude_fields.append(FlattenedClusterSpecKey2X.WORKERS_STORAGE_PROFILE.value)  # noqa: E501
        exclude_fields.append(FlattenedClusterSpecKey2X.WORKERS_CPU_COUNT.value)  # noqa: E501
        exclude_fields.append(FlattenedClusterSpecKey2X.WORKERS_MEMORY_MB.value)  # noqa: E501
    if reference_spec.topology.nfs.count == 0:
        # Exclude nfs nodes' sizing class and storage profile from validation
        # if nfs count is 0
        exclude_fields.append(FlattenedClusterSpecKey2X.NFS_SIZING_CLASS.value)
        exclude_fields.append(FlattenedClusterSpecKey2X.NFS_STORAGE_PROFILE.value)  # noqa: E501

    # Allow empty template revisions (== 0) if the value is the default
    # for TKGm clusters only
    if is_tkgm_cluster:
        if (
            reference_spec.distribution.template_revision == 1
            and input_spec.distribution.template_revision == 0  # default value
        ):
            exclude_fields.append(
                FlattenedClusterSpecKey2X.TEMPLATE_REVISION.value
            )

    input_spec_dict = input_spec.to_dict()
    reference_spec_dict = reference_spec.to_dict()
    diff_fields = rde_utils.find_diff_fields(
        input_spec_dict,
        reference_spec_dict,
        exclude_fields=exclude_fields)

    is_upgrade_operation = False
    if not diff_fields:
        return is_upgrade_operation

    keys_with_invalid_value = {}
    for k, v in diff_fields.items():
        if k not in VALID_UPDATE_FIELDS_2X:
            keys_with_invalid_value[k] = v

    # Raise exception if fields which cannot be changed are updated
    if len(keys_with_invalid_value) > 0:
        err_msg = "Change detected in immutable field(s) ["
        for k in sorted(keys_with_invalid_value):
            err_msg += \
                f"{k} found : {keys_with_invalid_value[k]['actual']} " \
                f"expected : {keys_with_invalid_value[k]['expected']}, "
        err_msg += "]."
        raise BadRequestError(err_msg)

    is_resize_operation = False
    if FlattenedClusterSpecKey2X.WORKERS_COUNT.value in diff_fields or \
            FlattenedClusterSpecKey2X.NFS_COUNT.value in diff_fields:
        is_resize_operation = True

    if FlattenedClusterSpecKey2X.TEMPLATE_NAME.value in diff_fields or \
            FlattenedClusterSpecKey2X.TEMPLATE_REVISION.value in diff_fields:
        is_upgrade_operation = True

    # Raise exception if resize and upgrade are performed at the same time
    if is_resize_operation and is_upgrade_operation:
        err_msg = "Cannot resize and upgrade the cluster at the same time"
        raise BadRequestError(err_msg)

    return is_upgrade_operation

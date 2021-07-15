# container-service-extension
# Copyright (c) 2021 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

from container_service_extension.common.constants.server_constants import FlattenedClusterSpecKey2X  # noqa: E501
from container_service_extension.common.constants.server_constants import VALID_UPDATE_FIELDS_2X  # noqa: E501
from container_service_extension.exception.exceptions import BadRequestError
from container_service_extension.lib.cloudapi.cloudapi_client import CloudApiClient  # noqa: E501
from container_service_extension.rde.behaviors.behavior_model import BehaviorOperation  # noqa: E501
from container_service_extension.rde.common.entity_service import DefEntityService  # noqa: E501
import container_service_extension.rde.constants as rde_constants
from container_service_extension.rde.models import rde_factory
from container_service_extension.rde.models.abstractNativeEntity import AbstractNativeEntity  # noqa: E501
import container_service_extension.rde.models.rde_2_0_0 as rde_2_0_0
import container_service_extension.rde.utils as rde_utils
from container_service_extension.rde.validators.abstract_validator import AbstractValidator  # noqa: E501


class Validator_2_0_0(AbstractValidator):
    def __init__(self):
        pass

    def validate(self, cloudapi_client: CloudApiClient, entity_id: str = None,
                 entity: dict = None, operation: BehaviorOperation = None) -> bool:  # noqa: E501
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
        :param dict entity: dict form of the native entity to be validated
        :param entity_id: entity id to be validated
        :param BehaviorOperation operation: CSE operation key
        :return: is validation successful or failure
        :rtype: bool
        """
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
        NativeEntityClass: AbstractNativeEntity = rde_factory. \
            get_rde_model(rde_version_introduced_at_api_version)
        input_entity = None
        if entity:
            try:
                input_entity: AbstractNativeEntity = NativeEntityClass.from_dict(entity)  # noqa: E501
            except Exception as err:
                msg = f"Failed to parse request body: {err}"
                raise BadRequestError(msg)

        # Return True if the operation is not specified.
        if not operation:
            return True

        # TODO: validators for rest of the CSE operations in V36 will be
        #  implemented as and when v36/def_cluster_handler.py get other handler
        #  functions
        if operation == BehaviorOperation.UPDATE_CLUSTER:
            if not entity_id or not entity:
                raise ValueError('Both entity_id and entity are required to validate the Update operation.')  # noqa: E501
            current_entity: AbstractNativeEntity = entity_svc.get_entity(entity_id).entity  # noqa: E501
            input_entity_spec: rde_2_0_0.ClusterSpec = input_entity.spec
            current_entity_status: rde_2_0_0.Status = current_entity.status
            current_entity_spec = \
                rde_utils.construct_cluster_spec_from_entity_status(
                    current_entity_status, rde_constants.RDEVersion.RDE_2_0_0.value)  # noqa: E501
            return validate_cluster_update_request_and_check_cluster_upgrade(
                input_entity_spec,
                current_entity_spec)

        # TODO check the reason why there was an unreachable raise statement
        raise NotImplementedError(f"Validator for {operation.name} not found")


def validate_cluster_update_request_and_check_cluster_upgrade(input_spec: rde_2_0_0.ClusterSpec,  # noqa: E501
                                                              reference_spec: rde_2_0_0.ClusterSpec) -> bool:  # noqa: E501
    """Validate the desired spec with curr spec and check if upgrade operation.

    :param dict input_spec: input spec
    :param dict reference_spec: reference spec to validate the desired spec
    :return: true if cluster operation is upgrade and false if operation is
        resize
    :rtype: bool
    :raises: BadRequestError for invalid payload.
    """
    exclude_fields = []
    if reference_spec.topology.workers.count == 0:
        # Exclude worker nodes' sizing class and storage profile from
        # validation if worker count is 0
        exclude_fields.append(FlattenedClusterSpecKey2X.WORKERS_SIZING_CLASS.value)  # noqa: E501
        exclude_fields.append(FlattenedClusterSpecKey2X.WORKERS_STORAGE_PROFILE.value)  # noqa: E501
    if reference_spec.topology.nfs.count == 0:
        # Exclude nfs nodes' sizing class and storage profile from validation
        # if nfs count is 0
        exclude_fields.append(FlattenedClusterSpecKey2X.NFS_SIZING_CLASS.value)
        exclude_fields.append(FlattenedClusterSpecKey2X.NFS_STORAGE_PROFILE.value)  # noqa: E501

    input_spec_dict = input_spec.to_dict()
    reference_spec_dict = reference_spec.to_dict()
    diff_fields = rde_utils.find_diff_fields(
        input_spec_dict,
        reference_spec_dict,
        exclude_fields=exclude_fields)

    # Raise exception if empty diff
    if not diff_fields:
        raise BadRequestError("No change in cluster specification")  # noqa: E501

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
    is_upgrade_operation = False

    if FlattenedClusterSpecKey2X.TEMPLATE_NAME.value in diff_fields or \
            FlattenedClusterSpecKey2X.TEMPLATE_REVISION.value in diff_fields:
        is_upgrade_operation = True

    # Raise exception if resize and upgrade are performed at the same time
    if is_resize_operation and is_upgrade_operation:
        err_msg = "Cannot resize and upgrade the cluster at the same time"
        raise BadRequestError(err_msg)

    return is_upgrade_operation

# container-service-extension
# Copyright (c) 2021 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

from dataclasses import asdict

import semantic_version

from container_service_extension.common.constants.server_constants import FlattenedClusterSpecKey  # noqa: E501
from container_service_extension.common.constants.server_constants import VALID_UPDATE_FIELDS  # noqa: E501
from container_service_extension.common.utils import server_utils
from container_service_extension.exception.exceptions import BadRequestError
from container_service_extension.lib.cloudapi.cloudapi_client import CloudApiClient  # noqa: E501
from container_service_extension.rde.behaviors.behavior_model import BehaviorOperation  # noqa: E501
from container_service_extension.rde.common.entity_service import DefEntityService  # noqa: E501
import container_service_extension.rde.constants as rde_constants
from container_service_extension.rde.models import rde_factory
from container_service_extension.rde.models.abstractNativeEntity import AbstractNativeEntity  # noqa: E501
import container_service_extension.rde.utils as rde_utils
from container_service_extension.rde.validators.abstract_validator import AbstractValidator  # noqa: E501


class Validator_2_0_0(AbstractValidator):
    def __init__(self):
        pass

    def validate(self, cloudapi_client: CloudApiClient, entity_id: str = None,
                 entity: dict = None, operation: BehaviorOperation = None) -> bool:  # noqa: E501
        """Validate the input entity based on the user specified api_version.

        The validation logic can differ based on the specified operation.

        :param cloudapi_client: cloud api client
        :param dict entity: entity to be validated
        :param entity_id: entity id to be validated
        :param BehaviorOperation operation: CSE operation key
        :return: is validation successful or failure
        :rtype: bool
        """
        if not entity_id and not entity:
            raise ValueError('Either entity_id or entity is required to validate.')  # noqa: E501
        entity_svc = DefEntityService(cloudapi_client=cloudapi_client)

        # Reject the request if rde_in_use is less than rde version introduced
        # at the specified api version.
        api_version: float = float(cloudapi_client.get_api_version())
        rde_version_introduced_at_api_version: str = rde_utils.get_rde_version_introduced_at_api_version(api_version)  # noqa: E501
        rde_in_use: str = server_utils.get_rde_version_in_use()
        if semantic_version.Version(rde_in_use) < \
                semantic_version.Version(rde_version_introduced_at_api_version):  # noqa: E501
            raise BadRequestError(
                error_message=f"Server cannot handle requests of RDE version "
                              f"{rde_version_introduced_at_api_version}at the "
                              f"specified api-version")

        # TODO Reject the request if payload_version does not match with
        #  either rde_in_use (or) rde_version_introduced_at_api_version

        # Cast the entity to the model class based on the user-specified
        # api_version. This can be considered as a basic request validation.
        # Any operation specific validation is handled further down
        NativeEntityClass: AbstractNativeEntity = rde_factory. \
            get_rde_model(rde_version_introduced_at_api_version)
        if entity:
            input_entity: AbstractNativeEntity = NativeEntityClass(**entity)
        elif entity_id:
            input_entity: AbstractNativeEntity = entity_svc.get_entity(entity_id).entity  # noqa: E501

        # Return True if the operation is not specified.
        if not operation:
            return True

        # TODO: validators for rest of the CSE operations in V36 will be
        #  implemented as and when v36/def_cluster_handler.py get other handler
        #  functions
        if operation == BehaviorOperation.UPDATE_CLUSTER:
            current_entity: AbstractNativeEntity = entity_svc.get_entity(entity_id).entity  # noqa: E501
            input_entity_spec = input_entity.spec
            current_entity_status = current_entity.status
            current_entity_spec = \
                rde_utils.construct_cluster_spec_from_entity_status(
                    current_entity_status, rde_constants.RDEVersion.RDE_2_0_0.value)  # noqa: E501
        return validate_cluster_update_request_and_check_cluster_upgrade(
            asdict(input_entity_spec),
            asdict(current_entity_spec))
        raise NotImplementedError(f"Validator for {operation.name} not found")


def validate_cluster_update_request_and_check_cluster_upgrade(input_spec: dict, reference_spec: dict) -> bool:  # noqa: E501
    """Validate the desired spec with curr spec and check if upgrade operation.

    :param dict input_spec: input spec
    :param dict reference_spec: reference spec to validate the desired spec
    :return: true if cluster operation is upgrade and false if operation is
        resize
    :rtype: bool
    :raises: BadRequestError for invalid payload.
    """
    diff_fields = \
        rde_utils.find_diff_fields(input_spec, reference_spec, exclude_fields=[])  # noqa: E501

    # Raise exception if empty diff
    if not diff_fields:
        raise BadRequestError("No change in cluster specification")  # noqa: E501

    # Raise exception if fields which cannot be changed are updated
    keys_with_invalid_value = [k for k in diff_fields if k not in VALID_UPDATE_FIELDS]  # noqa: E501
    if len(keys_with_invalid_value) > 0:
        err_msg = f"Invalid input values found in {sorted(keys_with_invalid_value)}"  # noqa: E501
        raise BadRequestError(err_msg)

    is_resize_operation = False
    if FlattenedClusterSpecKey.WORKERS_COUNT.value in diff_fields or \
            FlattenedClusterSpecKey.NFS_COUNT.value in diff_fields:
        is_resize_operation = True
    is_upgrade_operation = False
    if FlattenedClusterSpecKey.TEMPLATE_NAME.value in diff_fields or \
            FlattenedClusterSpecKey.TEMPLATE_REVISION.value in diff_fields:
        is_upgrade_operation = True

    # Raise exception if resize and upgrade are performed at the same time
    if is_resize_operation and is_upgrade_operation:
        err_msg = "Cannot resize and upgrade the cluster at the same time"
        raise BadRequestError(err_msg)

    return is_upgrade_operation

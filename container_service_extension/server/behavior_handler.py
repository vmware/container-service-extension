# container-service-extension
# Copyright (c) 2021 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

import functools

from container_service_extension.common.constants.shared_constants import RequestKey  # noqa: E501
import container_service_extension.exception.exceptions as cse_exception
from container_service_extension.lib.cloudapi.cloudapi_client import \
    CloudApiClient
from container_service_extension.logging.logger import SERVER_LOGGER as LOGGER
from container_service_extension.rde.backend import cluster_service_factory
import container_service_extension.rde.constants as rde_constants
import container_service_extension.rde.utils as rde_utils
import container_service_extension.rde.validators.validator_factory as rde_validator_factory  # noqa: E501
from container_service_extension.security.context.behavior_request_context import RequestContext  # noqa: E501


# Responsibility of the functions in this file:
# 1. Validate the Input payload based on the (BehaviorOperation, payload_version).  # noqa: E501
# Get the validator based on the payload_version.
# 2. Based on the rde_in_use, convert the entity if necessary
# 3. Based on the rde_in_use, call the appropriate backend method.
# 4. Return the success_payload_string.

def exception_handler(func):
    """Decorate to trap exceptions and process them.

    Raise errors of type KeyError, TypeError, ValueError as
    BadRequestError.

    Also raises BadRequest and Internal Server Errors from backend.

    :param method func: decorated function

    :return: reference to the function that executes the decorated function
        and traps exceptions raised by it.
    """
    @functools.wraps(func)
    def exception_handler_wrapper(*args, **kwargs):
        try:
            result = func(*args, **kwargs)
        except (KeyError, TypeError, ValueError) as error:
            LOGGER.error(error, exc_info=True)
            raise cse_exception.BadRequestError(error_message=str(error))
        except Exception as error:
            LOGGER.error(error, exc_info=True)
            if not isinstance(error, cse_exception.CseRequestError):
                raise cse_exception.InternalServerRequestError(error_message=str(error))  # noqa: E501
            raise error
        return result
    return exception_handler_wrapper


@exception_handler
def create_cluster(behavior_ctx: RequestContext):
    entity_id: str = behavior_ctx.entity_id
    input_entity: dict = behavior_ctx.entity
    cloudapi_client: CloudApiClient = behavior_ctx.op_ctx.cloudapi_client

    payload_version: str = input_entity.get(rde_constants.PayloadKey.PAYLOAD_VERSION)  # noqa: E501
    rde_utils.raise_error_if_unsupported_payload_version(payload_version)

    # Validate the Input payload based on the (Operation, payload_version).
    # Get the validator based on the payload_version
    input_rde_version = rde_constants.MAP_INPUT_PAYLOAD_VERSION_TO_RDE_VERSION[payload_version]  # noqa: E501
    rde_validator_factory.get_validator(
        rde_version=input_rde_version). \
        validate(cloudapi_client=cloudapi_client, entity=input_entity)

    # Convert the input entity to runtime rde format.
    # Based on the runtime rde, call the appropriate backend method.
    converted_input_entity = rde_utils.convert_input_rde_to_runtime_rde_format(input_entity)  # noqa: E501
    svc = cluster_service_factory.ClusterServiceFactory(behavior_ctx).get_cluster_service()  # noqa: E501
    return svc.create_cluster(entity_id=entity_id, input_native_entity=converted_input_entity)  # noqa: E501


@exception_handler
def update_cluster(behavior_ctx: RequestContext):
    entity_id: str = behavior_ctx.entity_id
    input_entity: dict = behavior_ctx.entity
    cloudapi_client: CloudApiClient = behavior_ctx.op_ctx.cloudapi_client

    payload_version: str = input_entity.get(rde_constants.PayloadKey.PAYLOAD_VERSION)  # noqa: E501
    rde_utils.raise_error_if_unsupported_payload_version(
        payload_version=payload_version)

    # Validate the Input payload based on the (Operation, payload_version).
    # Get the validator based on the payload_version
    input_rde_version = rde_constants.MAP_INPUT_PAYLOAD_VERSION_TO_RDE_VERSION[payload_version]  # noqa: E501
    rde_validator_factory.get_validator(
        rde_version=input_rde_version). \
        validate(cloudapi_client=cloudapi_client, entity=input_entity)

    # Convert the input entity to runtime rde format.
    # Based on the runtime rde, call the appropriate backend method.
    converted_input_entity = rde_utils.convert_input_rde_to_runtime_rde_format(input_entity)  # noqa: E501
    svc = cluster_service_factory.ClusterServiceFactory(behavior_ctx).get_cluster_service()  # noqa: E501
    return svc.update_cluster(entity_id, input_native_entity=converted_input_entity)  # noqa: E501


@exception_handler
def delete_cluster(behavior_ctx: RequestContext):
    entity_id: str = behavior_ctx.entity_id

    svc = cluster_service_factory.ClusterServiceFactory(behavior_ctx).get_cluster_service()  # noqa: E501

    return svc.delete_cluster(entity_id)


@exception_handler
def get_kubeconfig(behavior_ctx: RequestContext):
    cluster_id: str = behavior_ctx.entity_id
    svc = cluster_service_factory.ClusterServiceFactory(behavior_ctx).get_cluster_service()  # noqa: E501
    return svc.get_cluster_config(cluster_id)


@exception_handler
def nfs_node_delete(behavior_ctx: RequestContext):
    entity_id: str = behavior_ctx.entity_id
    node_to_delete: str = behavior_ctx.arguments.get(RequestKey.NODE_NAME)
    svc = cluster_service_factory.ClusterServiceFactory(behavior_ctx).get_cluster_service()  # noqa: E501
    return svc.delete_nodes(entity_id, nodes_to_del=[node_to_delete])

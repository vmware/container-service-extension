# container-service-extension
# Copyright (c) 2021 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

# from container_service_extension.rde.behaviors.behavior_model import BehaviorErrorPayload  # noqa: E501
import functools

from container_service_extension.common.utils import server_utils
from container_service_extension.lib.cloudapi.cloudapi_client import \
    CloudApiClient
from container_service_extension.rde.backend import cluster_service_factory
import container_service_extension.rde.constants as rde_constants
import container_service_extension.rde.validators.validator_factory as rde_validator_factory  # noqa: E501
from container_service_extension.rde.models import rde_factory
from container_service_extension.rde.models.abstractNativeEntity import \
    AbstractNativeEntity
import container_service_extension.rde.utils as rde_utils
from container_service_extension.security.context.behavior_operation_context import BehaviorOperationContext  # noqa: E501
import container_service_extension.exception.exceptions as cse_exception
from container_service_extension.logging.logger import SERVER_LOGGER as LOGGER


# Responsibility of the functions in this file:
# 1. Validate the Input payload based on the (api_version, BehaviorOperation, payload_version).  # noqa: E501
# Get the validator based on the api_version and payload_version.
# 2. Based on the rde_in_use, convert the entity if necessary
# 3. Based on the rde_in_use, call the appropriate backend method.
# 4. Return either success_payload_string (or) instance of BehaviorErrorPayload

# As of today (Mar 8, 2021), we do not anticipate the need to maintain
# multiple handlers based on api_version. This can be evaluated on the need basis.  # noqa: E501

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
            LOGGER.error(error)
            raise cse_exception.BadRequestError(error_message=str(error))
        except Exception as error:
            LOGGER.error(error)
            if not isinstance(error, cse_exception.CseRequestError):
                raise cse_exception.InternalServerRequestError(error_message=str(error))  # noqa: E501
            raise error
        return result
    return exception_handler_wrapper


@exception_handler
def create_cluster(behavior_ctx: BehaviorOperationContext):
    entity_id: str = behavior_ctx.entity_id
    entity: dict = behavior_ctx.entity
    cloudapi_client: CloudApiClient = behavior_ctx.op_ctx.cloudapi_client
    api_version: float = behavior_ctx.api_version

    # Validate the input
    rde_version_introduced_at_api_version = rde_utils.get_rde_version_introduced_at_api_version(api_version)  # noqa: E501
    rde_validator_factory.get_validator(
        rde_version=rde_version_introduced_at_api_version). \
        validate(cloudapi_client=cloudapi_client, entity=entity)

    # TODO Based on the rde_in_use, convert the entity if necessary.

    # Call the backend to initiate the cluster creation.
    rde_in_use = server_utils.get_rde_version_in_use()
    svc = cluster_service_factory.ClusterServiceFactory(behavior_ctx).get_cluster_service(rde_in_use)  # noqa: E501
    NativeEntityClass: AbstractNativeEntity = rde_factory.get_rde_model(rde_in_use)  # noqa: E501
    input_entity: AbstractNativeEntity = NativeEntityClass(**entity)
    return svc.create_cluster(entity_id=entity_id, input_native_entity=input_entity)  # noqa: E501


@exception_handler
def update_cluster(behavior_ctx: BehaviorOperationContext):
    # entity_id = behavior_ctx.entity_id
    # entity = behavior_ctx.entity
    # api_version = behavior_ctx.api_version
    # TODO Get validator based on (api_version, payload_version) and validate the entity.  # noqa: E501
    # TODO Based on the rde_in_use, convert the entity if necessary.
    # TODO Based on the rde_in_use, call the right cluster_service.py file.
    # error: bool = True
    # if error:
    #     return BehaviorErrorPayload(majorErrorCode='500',
    #                                 minorErrorCode='Cluster initialization failed',  # noqa: E501
    #                                 message='Cluster initialization failed')
    return "Cluster update successful."


@exception_handler
def delete_cluster(behavior_ctx: BehaviorOperationContext):
    # entity_id = behavior_ctx.entity_id
    # entity = behavior_ctx.entity
    # api_version = behavior_ctx.api_version
    # TODO Get validator based on (api_version, payload_version) and validate the entity.  # noqa: E501
    # TODO Based on the rde_in_use, convert the entity if necessary.
    # TODO Based on the rde_in_use, call the right cluster_service.py file.
    # error: bool = True
    # if error:
    #     return BehaviorErrorPayload(majorErrorCode='500',
    #                                 minorErrorCode='vApp does not exist',
    #                                 message='vApp does not exist')
    return "Successfully deleted the cluster."


@exception_handler
def get_kubeconfig(behavior_ctx: BehaviorOperationContext):
    # entity_id = behavior_ctx.entity_id
    # entity = behavior_ctx.entity
    # api_version = behavior_ctx.api_version
    # TODO Get validator based on (api_version, payload_version) and validate the entity.  # noqa: E501
    # TODO Based on the rde_in_use, convert the entity if necessary.
    # TODO Based on the rde_in_use, call the right cluster_service.py file.
    # error: bool = True
    # if error:
    #     return BehaviorErrorPayload(majorErrorCode='500',
    #                                 minorErrorCode='Cannot reach the cluster',  # noqa: E501
    #                                 message='Cannot reach the cluster')
    return "Returning the kubeconfig"


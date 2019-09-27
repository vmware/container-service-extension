# container-service-extension
# Copyright (c) 2019 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

import requests

from container_service_extension.minor_error_codes import MinorErrorCode


class AmqpError(Exception):
    """Base class for Amqp related errors."""


class AmqpConnectionError(AmqpError):
    """Raised when amqp connection is not open."""


# To be used only by clients
class CseResponseError(Exception):
    """Base class for all vcd response related Exceptions."""

    def __init__(self, status_code, error_message, minor_error_code):
        self.status_code = status_code
        self.error_message = error_message
        self.minor_error_code = minor_error_code

    def __str__(self):
        return str(self.error_message)


class CseServerError(Exception):
    """Base class for cse server side exceptions."""


class CseRequestError(CseServerError):
    """Base class for all incoming CSE REST request errors."""

    def __init__(self, status_code, error_message=None,
                 minor_error_code=None):
        self.status_code = status_code
        self.error_message = str(error_message)
        if not minor_error_code:
            minor_error_code = MinorErrorCode.DEFAULT_ERROR_CODE
        self.minor_error_code = minor_error_code

    def __str__(self):
        return self.error_message


class ClusterOperationError(CseServerError):
    """Base class for all cluster operation related exceptions."""


class ClusterAlreadyExistsError(CseServerError):
    """Raised when creating a cluster that already exists."""


class ClusterNotFoundError(CseServerError):
    """Raised when cluster is not found in the environment."""


class CseDuplicateClusterError(CseServerError):
    """Raised when multiple vCD clusters of same name detected."""


class NodeNotFoundError(CseServerError):
    """Raised when a node is not found in the environment."""


class PksServerError(CseServerError):
    """Raised when error is received from PKS."""

    def __init__(self, status, body=None):
        self.status = status
        self.body = body

    def __str__(self):
        # TODO() Removing user context should be moved to PksServer response
        #  processing aka filtering layer
        from container_service_extension.pksbroker import PksBroker
        return f"PKS error\n status: {self.status}\n body: " \
            f" {PksBroker.filter_traces_of_user_context(self.body)}\n"


class BadRequestError(CseRequestError):
    """Raised when an invalid action is attempted by an user."""

    def __init__(self, error_message=None, minor_error_code=None):
        super().__init__(requests.codes.bad_request, error_message,
                         minor_error_code)


class InternalServerRequestError(CseRequestError):
    """Raised when an internal server error occurs while processing a REST request.""" # noqa: E501

    def __init__(self, error_message=None, minor_error_code=None):
        super().__init__(requests.codes.internal_server_error, error_message,
                         minor_error_code)


class MethodNotAllowedRequestError(CseRequestError):
    """Raised when an invalid HTTP method is attempted on a CSE REST endpoint.""" # noqa: E501

    def __init__(self, error_message="Method not allowed",
                 minor_error_code=None):
        super().__init__(requests.codes.method_not_allowed, error_message,
                         minor_error_code)


class NotAcceptableRequestError(CseRequestError):
    """Raised when CSE can't serve the provided the response as per the accept header in the request.""" # noqa: E501

    def __init__(self, error_message="Not acceptable",
                 minor_error_code=None):
        super().__init__(requests.codes.not_acceptable, error_message,
                         minor_error_code)


class NotFoundRequestError(CseRequestError):
    """Raised when an invalid CSE REST endpoint is accessed."""

    def __init__(self, error_message="Invalid url - not found",
                 minor_error_code=None):
        super().__init__(requests.codes.not_found, error_message,
                         minor_error_code)


class UnauthorizedRequestError(CseRequestError):
    """Raised when an action is attempted by an unauthorized user."""

    def __init__(self, error_message=None, minor_error_code=None):
        super().__init__(requests.codes.unauthorized, error_message,
                         minor_error_code)


class ClusterJoiningError(ClusterOperationError):
    """Raised when any error happens while cluster join operation."""


class ClusterInitializationError(ClusterOperationError):
    """Raised when any error happens while cluster initialization."""


class ClusterNetworkIsolationError(ClusterOperationError):
    """Raised when any error happens while isolating cluster network."""


class NodeOperationError(ClusterOperationError):
    """Base class for all node operation related exceptions."""


class NodeCreationError(NodeOperationError):
    """Raised when node creation fails for any reason."""

    def __init__(self, node_names, error_message):
        self.node_names = node_names
        self.error_message = error_message

    def __str__(self):
        return f"failure on creating nodes {self.node_names}\nError:" \
            f"{self.error_message}"


class MasterNodeCreationError(NodeOperationError):
    """Raised when any error happens while adding master node."""


class WorkerNodeCreationError(NodeOperationError):
    """Raised when any error happens while adding worker node."""


class NFSNodeCreationError(NodeOperationError):
    """Raised when any error happens while adding NFS node."""


class ScriptExecutionError(NodeOperationError):
    """Raised when any error happens when executing script on nodes."""


class DeleteNodeError(NodeOperationError):
    """Raised when there is any error while deleting node."""


class PksConnectionError(PksServerError):
    """Raised when connection establishment to PKS fails."""


class PksClusterNotFoundError(PksServerError):
    """Raised if PKS cluster search fails because the cluster doesn't exist."""


class PksDuplicateClusterError(PksServerError):
    """Raised when multiple PKS clusters of same name detected."""

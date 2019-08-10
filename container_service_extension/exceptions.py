# container-service-extension
# Copyright (c) 2019 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

from pyvcloud.vcd.exceptions import VcdException


class CseClientError(Exception):
    """Raised for any client side error."""


class CseServerError(VcdException):
    """Base class for cse server side operation related exceptions."""


class CseRequestError(CseServerError):
    """Base class for all REST request errors."""

    def __init__(self, status_code, error_message=None):
        self.status_code = int(status_code)
        self._error_message = str(error_message)

    def __str__(self):
        return self._error_message


class ClusterOperationError(CseServerError):
    """Base class for all cluster operation related exceptions."""


class ClusterAlreadyExistsError(CseServerError):
    """Raised when creating a cluster that already exists."""


class ClusterNotFoundError(CseServerError):
    """Raised when cluster is not found in the environment."""


class ClusterJoiningError(ClusterOperationError):
    """Raised when any error happens while cluster join operation."""


class ClusterInitializationError(ClusterOperationError):
    """Raised when any error happens while cluster initialization."""


class ClusterNetworkIsolationError(ClusterOperationError):
    """Raised when any error happens while isolating cluster network."""


class CseDuplicateClusterError(CseServerError):
    """Raised when multiple vCD clusters of same name detected."""


class NodeNotFoundError(CseServerError):
    """Raised when a node is not found in the environment."""


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


class AmqpError(Exception):
    """Base class for Amqp related errors."""


class AmqpConnectionError(AmqpError):
    """Raised when amqp connection is not open."""


class UnauthorizedActionError(CseServerError):
    """Raised when an action is attempted by an unauthorized user."""


class VcdResponseError(Exception):
    """Base class for all vcd response related Exceptions."""

    def __init__(self, status_code, error_message):
        self.status_code = status_code
        self.error_message = error_message

    def __str__(self):
        return str(self.error_message)


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


class PksConnectionError(PksServerError):
    """Raised when connection establishment to PKS fails."""


class PksClusterNotFoundError(PksServerError):
    """Raised if PKS cluster search fails because the cluster doesn't exist."""


class PksDuplicateClusterError(PksServerError):
    """Raised when multiple PKS clusters of same name detected."""

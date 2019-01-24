# See the License for the specific language governing permissions and
# limitations under the License.

from pyvcloud.vcd.exceptions import VcdException


class CseServerError(VcdException):
    """Base class for cse server side operation related exceptions."""


class CseClientError(Exception):
    """Raised for any client side error."""


class ClusterOperationError(CseServerError):
    """Base class for all cluster operation related exceptions."""


class ClusterAlreadyExistsError(CseServerError):
    """Raised when creating a cluster that already exists."""


class ClusterJoiningError(ClusterOperationError):
    """Raised when any error happens while cluster join operation."""


class ClusterInitializationError(ClusterOperationError):
    """Raised when any error happens while cluster initialization."""


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


class VcdResponseError(Exception):
    """Base class for all vcd response related Exceptions."""

    def __init__(self, status_code, error_message):
        self.status_code = status_code
        self.error_message = error_message

    def __str__(self):
        return self.error_message

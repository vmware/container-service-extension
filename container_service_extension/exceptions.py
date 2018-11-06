# See the License for the specific language governing permissions and
# limitations under the License.

from pyvcloud.vcd.exceptions import VcdException


class CseServerError(VcdException):
    """Base class for cse server side operation related exceptions"""


class ClusterOperationError(CseServerError):
    """Base class for all cluster operation related exceptions"""


class ClusterAlreadyExistsError(ClusterOperationError):
    """Raised when creating a cluster that already exists"""


class ClusterJoiningError(ClusterOperationError):
    """ Raised when any error happens while cluster join operation"""


class ClusterInitializationError(ClusterOperationError):
    """Raised when any error happens while cluster initialization"""


class NodeOperationError(ClusterOperationError):
    """Base class for all node operation related exceptions"""


class MasterNodeCreationError(NodeOperationError):
    """Raised when any error happens while adding master node"""


class WorkerNodeCreationError(NodeOperationError):
    """Raised when any error happens while adding worker node"""


class NFSNodeCreationError(NodeOperationError):
    """Raised when any error happens while adding NFS node"""




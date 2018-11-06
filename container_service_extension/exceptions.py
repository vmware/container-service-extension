# See the License for the specific language governing permissions and
# limitations under the License.

from pyvcloud.vcd.exceptions import VcdException


class CseServerException(VcdException):
    """Base class for cse server side operation related exceptions"""


class ClusterOperationException(CseServerException):
    """Base class for all cluster operation related exceptions"""


class CreateVAppException(ClusterOperationException):
    """Raised when any error happens while creating Vapp"""


class ClusterInitializationException(ClusterOperationException):
    """Raised when any error happens while cluster initialization"""


class NodeOperationException(ClusterOperationException):
    """Base class for all node operation related exceptions"""


class ClusterJoinException(ClusterOperationException):
    """ Raised when any error happens while cluster join operation"""


class CreateMasterNodeException(NodeOperationException):
    """Raised when any error happens while adding master node"""


class CreateWorkerNodeException(NodeOperationException):
    """Raised when any error happens while adding worker node"""


class CreateNFSNodeException(NodeOperationException):
    """Raised when any error happens while adding NFS node"""




from container_service_extension.cloudapi.cloudapi_client import CloudApiClient
from container_service_extension.cloudapi.constants import CloudApiResource
from container_service_extension.cloudapi.constants import CloudApiVersion
from container_service_extension.shared_constants import RequestMethod
import container_service_extension.utils as utils

def get_vdcs(cloudapi_client: CloudApiClient, page=1, page_size=25):
    """
    Returns: total number of vdcs, list of dict of vdcs
    """
    filter_string = f"page={page}&pageSize={page_size}"
    resp = cloudapi_client.do_request(
            method=RequestMethod.GET,
            cloudapi_version=CloudApiVersion.VERSION_1_0_0,
            resource_url_relative_path=f"{CloudApiResource.VDCS}?{filter_string}")  # noqa: E501
    return resp['resultTotal'], resp['values']

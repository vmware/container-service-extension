from container_service_extension.cloudapi.cloudapi_client import CloudApiClient
from container_service_extension.cloudapi.constants import CloudApiResource
from container_service_extension.cloudapi.constants import CloudApiVersion
from container_service_extension.shared_constants import RequestMethod


def get_vdcs(cloudapi_client: CloudApiClient, page=1, page_size=25):
    """Return a single page list vdc response for the page number and size.

    :param CloudApiClient cloudapi_cliet
    :param int page: page number for the response
    :param int page_size: page size of the response
    :return: touple containing total number of vdcs present and the list of
        vdcs for the current request
    """
    filter_string = f"page={page}&pageSize={page_size}"
    resp = cloudapi_client.do_request(method=RequestMethod.GET,
                                      cloudapi_version=CloudApiVersion.VERSION_1_0_0,  # noqa: E501
                                      resource_url_relative_path=f"{CloudApiResource.VDCS}?{filter_string}")  # noqa: E501
    return resp['resultTotal'], resp['values']

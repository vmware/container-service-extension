from container_service_extension.cloudapi.cloudapi_client import CloudApiClient
from container_service_extension.cloudapi.constants import CloudApiResource
from container_service_extension.cloudapi.constants import CloudApiVersion
from container_service_extension.shared_constants import RequestMethod
from container_service_extension.shared_constants import CSE_PAGINATION_DEFAULT_PAGE_SIZE  # noqa: E501
from container_service_extension.shared_constants import CSE_PAGINATION_FIRST_PAGE_NUMBER  # noqa: E501


def get_vdcs_by_page(cloudapi_client: CloudApiClient, \
                     page_number=CSE_PAGINATION_FIRST_PAGE_NUMBER, page_size=CSE_PAGINATION_FIRST_PAGE_NUMBER):  # noqa: E501
    """Return a single page list vdc response for the page number and size.

    :param CloudApiClient cloudapi_cliet
    :param int page: page number for the response
    :param int page_size: page size of the response
    :return: touple containing total number of vdcs present and the list of
        vdcs for the current request
    """
    filter_string = f"page={page_number}&pageSize={page_size}"
    resp = cloudapi_client.do_request(method=RequestMethod.GET,
                                      cloudapi_version=CloudApiVersion.VERSION_1_0_0,  # noqa: E501
                                      resource_url_relative_path=f"{CloudApiResource.VDCS}?{filter_string}")  # noqa: E501
    return resp['resultTotal'], resp['values']

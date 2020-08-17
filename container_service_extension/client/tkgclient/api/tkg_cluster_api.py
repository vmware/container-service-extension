# coding: utf-8

"""
    TKG Kubernetes API

    This API provides to vCD tenants the means to provision (create and update) Tanzu Kubernetes Grid clusters. This is complementary to the defined-entity APIs:    GET /cloudapi/1.0.0/entities/urn:vcloud:entity:vmware.tkgcluster:1.0.0:{id} which allows to retrieve the clusters created by the API presented here. This is why you will not find here a GET operation for the corresponding entity.   # noqa: E501

    OpenAPI spec version: 1.0.0
    
    Generated by: https://github.com/swagger-api/swagger-codegen.git
"""


from __future__ import absolute_import

import re  # noqa: F401

# python 2 and python 3 compatibility library
import six

from container_service_extension.client.tkgclient.api_client import ApiClient


class TkgClusterApi(object):
    """NOTE: This class is auto generated by the swagger code generator program.

    Do not edit the class manually.
    Ref: https://github.com/swagger-api/swagger-codegen
    """

    def __init__(self, api_client=None):
        if api_client is None:
            api_client = ApiClient()
        self.api_client = api_client

    def list_tkg_clusters(self, entity_type, **kwargs):
        all_params = ['id']  # noqa: E501
        all_params.append('async_req')
        all_params.append('_return_http_data_only')
        all_params.append('_preload_content')
        all_params.append('_request_timeout')
        all_params.append('object_filter')

        params = locals()
        for key, val in six.iteritems(params['kwargs']):
            if key not in all_params:
                raise TypeError(
                    "Got an unexpected keyword argument '%s'"
                    " to method list_tkg_clusters" % key
                )
            params[key] = val
        del params['kwargs']
        if ('entity_type' not in params or
                params['entity_type'] is None):
            raise ValueError(
                "Missing the required parameter `entity_type` when calling `list_tkg_clusters`")
        path_params = {}
        query_params = []
        if params.get('object_filter'):
            query_params.append(('filter', params['object_filter']))
        header_params = {}
        # HTTP header `Accept`
        header_params['Accept'] = self.api_client.select_header_accept(
            ['*/*'])  # noqa: E501
        header_params[
            'Content-Type'] = self.api_client.select_header_content_type(
            ['application/json'])
        form_params = []
        local_var_files = {}
        body_params = None
        auth_settings = []
        collection_formats = {}
        return self.api_client.call_api(
            f"entities/{entity_type}", 'GET',
            path_params,
            query_params,
            header_params,
            body=body_params,
            post_params=form_params,
            files=local_var_files,
            response_type='list[TkgCluster]',  # noqa: E501
            auth_settings=auth_settings,
            async_req=params.get('async_req'),
            _return_http_data_only=params.get('_return_http_data_only'),
            _preload_content=params.get('_preload_content', True),
            _request_timeout=params.get('_request_timeout'),
            collection_formats=collection_formats)

    def get_tkg_cluster(self, id, **kwargs):
        all_params = ['id']  # noqa: E501
        all_params.append('async_req')
        all_params.append('_return_http_data_only')
        all_params.append('_preload_content')
        all_params.append('_request_timeout')

        params = locals()
        for key, val in six.iteritems(params['kwargs']):
            if key not in all_params:
                raise TypeError(
                    "Got an unexpected keyword argument '%s'"
                    " to method create_tkg_cluster" % key
                )
            params[key] = val
        del params['kwargs']
        if ('id' not in params or
                params['id'] is None):
            raise ValueError("Missing the required parameter `id` when calling `get_tkg_cluster`")
        path_params = {}
        query_params = []
        header_params = {}
        header_params['Content-Type'] = self.api_client.select_header_content_type(['application/json'])
        form_params = []
        local_var_files = {}
        body_params = None
        auth_settings = []
        collection_formats = {}
        return self.api_client.call_api(
            f"entities/{id}", 'GET',
            path_params,
            query_params,
            header_params,
            body=body_params,
            post_params=form_params,
            files=local_var_files,
            response_type='TkgCluster',  # noqa: E501
            auth_settings=auth_settings,
            async_req=params.get('async_req'),
            _return_http_data_only=params.get('_return_http_data_only'),
            _preload_content=params.get('_preload_content', True),
            _request_timeout=params.get('_request_timeout'),
            collection_formats=collection_formats)

    def create_tkg_cluster_config_task(self, id, **kwargs):
        """Obtain VCD task to get TKG cluster config."""
        all_params = ['id']  # noqa: E501
        all_params.append('async_req')
        # all_params.append('_return_http_data_only')
        all_params.append('_preload_content')
        all_params.append('_request_timeout')

        params = locals()
        for key, val in six.iteritems(params['kwargs']):
            if key not in all_params:
                raise TypeError(
                    "Got an unexpected keyword argument '%s'"
                    " to method create_tkg_cluster" % key
                )
            params[key] = val
        del params['kwargs']
        if ('id' not in params or
                params['id'] is None):
            raise ValueError("Missing the required parameter `id` when calling `get_tkg_cluster`")  # noqa: E501
        path_params = {}
        query_params = []
        header_params = {}
        header_params['Content-Type'] = self.api_client.select_header_content_type(['application/json'])  # noqa: E501
        form_params = []
        local_var_files = {}
        body_params = None
        auth_settings = []
        collection_formats = {}
        return self.api_client.call_api(
            f"entities/{id}/behaviors/urn:vcloud:behavior-interface:createKubeConfig:vmware:k8s:1.0.0/invocations",  # noqa: E501
            'POST',
            path_params,
            query_params,
            header_params,
            body=body_params,
            post_params=form_params,
            files=local_var_files,
            response_type=None,
            auth_settings=auth_settings,
            async_req=params.get('async_req'),
            _return_http_data_only=False,
            _preload_content=params.get('_preload_content', True),
            _request_timeout=params.get('_request_timeout'),
            collection_formats=collection_formats)

    def create_tkg_cluster(self, tkg_cluster, **kwargs):  # noqa: E501
        """Creates a new TKG cluster. This operation is asynchronous and returns a task that you can monitor to track the progress of the request.   # noqa: E501

        This method makes a synchronous HTTP request by default. To make an
        asynchronous HTTP request, please pass async_req=True
        >>> thread = api.create_tkg_cluster(tkg_cluster, async_req=True)
        >>> result = thread.get()

        :param async_req bool
        :param TkgCluster tkg_cluster: (required)
        :return: None
                 If the method is called asynchronously,
                 returns the request thread.
        """
        kwargs['_return_http_data_only'] = True
        if kwargs.get('async_req'):
            return self.create_tkg_cluster_with_http_info(tkg_cluster, **kwargs)  # noqa: E501
        else:
            (data) = self.create_tkg_cluster_with_http_info(tkg_cluster, **kwargs)  # noqa: E501
            return data

    def create_tkg_cluster_with_http_info(self, tkg_cluster, **kwargs):  # noqa: E501
        """Creates a new TKG cluster. This operation is asynchronous and returns a task that you can monitor to track the progress of the request.   # noqa: E501

        This method makes a synchronous HTTP request by default. To make an
        asynchronous HTTP request, please pass async_req=True
        >>> thread = api.create_tkg_cluster_with_http_info(tkg_cluster, async_req=True)
        >>> result = thread.get()

        :param async_req bool
        :param TkgCluster tkg_cluster: (required)
        :return: None
                 If the method is called asynchronously,
                 returns the request thread.
        """

        all_params = ['tkg_cluster']  # noqa: E501
        all_params.append('async_req')
        all_params.append('_return_http_data_only')
        all_params.append('_preload_content')
        all_params.append('_request_timeout')

        params = locals()
        for key, val in six.iteritems(params['kwargs']):
            if key not in all_params:
                raise TypeError(
                    "Got an unexpected keyword argument '%s'"
                    " to method create_tkg_cluster" % key
                )
            params[key] = val
        del params['kwargs']
        # verify the required parameter 'tkg_cluster' is set
        if ('tkg_cluster' not in params or
                params['tkg_cluster'] is None):
            raise ValueError("Missing the required parameter `tkg_cluster` when calling `create_tkg_cluster`")  # noqa: E501

        collection_formats = {}

        path_params = {}

        query_params = []

        header_params = {}

        form_params = []
        local_var_files = {}

        body_params = None
        if 'tkg_cluster' in params:
            body_params = params['tkg_cluster']
        # HTTP header `Content-Type`
        header_params['Content-Type'] = self.api_client.select_header_content_type(  # noqa: E501
            ['application/json'])  # noqa: E501

        # Authentication setting
        auth_settings = []  # noqa: E501

        return self.api_client.call_api(
            'tkgClusters', 'POST',
            path_params,
            query_params,
            header_params,
            body=body_params,
            post_params=form_params,
            files=local_var_files,
            response_type=None,  # noqa: E501
            auth_settings=auth_settings,
            async_req=params.get('async_req'),
            _return_http_data_only=params.get('_return_http_data_only'),
            _preload_content=params.get('_preload_content', True),
            _request_timeout=params.get('_request_timeout'),
            collection_formats=collection_formats)

    def delete_tkg_cluster(self, tkg_cluster_id, **kwargs):  # noqa: E501
        """delete_tkg_cluster  # noqa: E501

        Deletes the TKG defined entity instance with the unique identifier (URN) This operation is asynchronous and returns a task that you can monitor to track the progress of the request.   # noqa: E501
        This method makes a synchronous HTTP request by default. To make an
        asynchronous HTTP request, please pass async_req=True
        >>> thread = api.delete_tkg_cluster(tkg_cluster_id, async_req=True)
        >>> result = thread.get()

        :param async_req bool
        :param str tkg_cluster_id: A URN corresponding to a TKG defined entity instance previously created by a POST to above OpenAPI tkgClusters endpoint.  (required)
        :return: None
                 If the method is called asynchronously,
                 returns the request thread.
        """
        kwargs['_return_http_data_only'] = True
        if kwargs.get('async_req'):
            return self.delete_tkg_cluster_with_http_info(tkg_cluster_id, **kwargs)  # noqa: E501
        else:
            (data) = self.delete_tkg_cluster_with_http_info(tkg_cluster_id, **kwargs)  # noqa: E501
            return data

    def delete_tkg_cluster_with_http_info(self, tkg_cluster_id, **kwargs):  # noqa: E501
        """delete_tkg_cluster  # noqa: E501

        Deletes the TKG defined entity instance with the unique identifier (URN) This operation is asynchronous and returns a task that you can monitor to track the progress of the request.   # noqa: E501
        This method makes a synchronous HTTP request by default. To make an
        asynchronous HTTP request, please pass async_req=True
        >>> thread = api.delete_tkg_cluster_with_http_info(tkg_cluster_id, async_req=True)
        >>> result = thread.get()

        :param async_req bool
        :param str tkg_cluster_id: A URN corresponding to a TKG defined entity instance previously created by a POST to above OpenAPI tkgClusters endpoint.  (required)
        :return: None
                 If the method is called asynchronously,
                 returns the request thread.
        """

        all_params = ['tkg_cluster_id']  # noqa: E501
        all_params.append('async_req')
        all_params.append('_return_http_data_only')
        all_params.append('_preload_content')
        all_params.append('_request_timeout')

        params = locals()
        for key, val in six.iteritems(params['kwargs']):
            if key not in all_params:
                raise TypeError(
                    "Got an unexpected keyword argument '%s'"
                    " to method delete_tkg_cluster" % key
                )
            params[key] = val
        del params['kwargs']
        # verify the required parameter 'tkg_cluster_id' is set
        if ('tkg_cluster_id' not in params or
                params['tkg_cluster_id'] is None):
            raise ValueError("Missing the required parameter `tkg_cluster_id` when calling `delete_tkg_cluster`")  # noqa: E501

        collection_formats = {}

        path_params = {}
        if 'tkg_cluster_id' in params:
            path_params['tkgClusterId'] = params['tkg_cluster_id']  # noqa: E501

        query_params = []

        header_params = {}

        form_params = []
        local_var_files = {}

        body_params = None
        # Authentication setting
        auth_settings = []  # noqa: E501

        return self.api_client.call_api(
            'tkgClusters/{tkgClusterId}', 'DELETE',
            path_params,
            query_params,
            header_params,
            body=body_params,
            post_params=form_params,
            files=local_var_files,
            response_type=None,  # noqa: E501
            auth_settings=auth_settings,
            async_req=params.get('async_req'),
            _return_http_data_only=params.get('_return_http_data_only'),
            _preload_content=params.get('_preload_content', True),
            _request_timeout=params.get('_request_timeout'),
            collection_formats=collection_formats)

    def update_tkg_cluster(self, tkg_cluster_id, tkg_cluster, **kwargs):  # noqa: E501
        """Update the desired state of the TKG cluster. This operation is asynchronous and returns a task that you can monitor to track the progress of the request.   # noqa: E501

        This method makes a synchronous HTTP request by default. To make an
        asynchronous HTTP request, please pass async_req=True
        >>> thread = api.update_tkg_cluster(tkg_cluster_id, tkg_cluster, async_req=True)
        >>> result = thread.get()

        :param async_req bool
        :param str tkg_cluster_id: A URN corresponding to a TKG defined entity instance previously created by a POST to above OpenAPI tkgClusters endpoint.  (required)
        :param TkgCluster tkg_cluster: (required)
        :return: None
                 If the method is called asynchronously,
                 returns the request thread.
        """
        kwargs['_return_http_data_only'] = True
        if kwargs.get('async_req'):
            return self.update_tkg_cluster_with_http_info(tkg_cluster_id, tkg_cluster, **kwargs)  # noqa: E501
        else:
            (data) = self.update_tkg_cluster_with_http_info(tkg_cluster_id, tkg_cluster, **kwargs)  # noqa: E501
            return data

    def update_tkg_cluster_with_http_info(self, tkg_cluster_id, tkg_cluster, **kwargs):  # noqa: E501
        """Update the desired state of the TKG cluster. This operation is asynchronous and returns a task that you can monitor to track the progress of the request.   # noqa: E501

        This method makes a synchronous HTTP request by default. To make an
        asynchronous HTTP request, please pass async_req=True
        >>> thread = api.update_tkg_cluster_with_http_info(tkg_cluster_id, tkg_cluster, async_req=True)
        >>> result = thread.get()

        :param async bool
        :param str tkg_cluster_id: A URN corresponding to a TKG defined entity instance previously created by a POST to above OpenAPI tkgClusters endpoint.  (required)
        :param TkgCluster tkg_cluster: (required)
        :return: None
                 If the method is called asynchronously,
                 returns the request thread.
        """

        all_params = ['tkg_cluster_id', 'tkg_cluster']  # noqa: E501
        all_params.append('async_req')
        all_params.append('_return_http_data_only')
        all_params.append('_preload_content')
        all_params.append('_request_timeout')

        params = locals()
        for key, val in six.iteritems(params['kwargs']):
            if key not in all_params:
                raise TypeError(
                    "Got an unexpected keyword argument '%s'"
                    " to method update_tkg_cluster" % key
                )
            params[key] = val
        del params['kwargs']
        # verify the required parameter 'tkg_cluster_id' is set
        if ('tkg_cluster_id' not in params or
                params['tkg_cluster_id'] is None):
            raise ValueError("Missing the required parameter `tkg_cluster_id` when calling `update_tkg_cluster`")  # noqa: E501
        # verify the required parameter 'tkg_cluster' is set
        if ('tkg_cluster' not in params or
                params['tkg_cluster'] is None):
            raise ValueError("Missing the required parameter `tkg_cluster` when calling `update_tkg_cluster`")  # noqa: E501

        collection_formats = {}

        path_params = {}
        if 'tkg_cluster_id' in params:
            path_params['tkgClusterId'] = params['tkg_cluster_id']  # noqa: E501

        query_params = []

        header_params = {}

        form_params = []
        local_var_files = {}

        body_params = None
        if 'tkg_cluster' in params:
            body_params = params['tkg_cluster']
        # HTTP header `Content-Type`
        header_params['Content-Type'] = self.api_client.select_header_content_type(  # noqa: E501
            ['application/json'])  # noqa: E501

        # Authentication setting
        auth_settings = []  # noqa: E501

        return self.api_client.call_api(
            'tkgClusters/{tkgClusterId}', 'PUT',
            path_params,
            query_params,
            header_params,
            body=body_params,
            post_params=form_params,
            files=local_var_files,
            response_type=None,  # noqa: E501
            auth_settings=auth_settings,
            async_req=params.get('async_req'),
            _return_http_data_only=params.get('_return_http_data_only'),
            _preload_content=params.get('_preload_content', True),
            _request_timeout=params.get('_request_timeout'),
            collection_formats=collection_formats)

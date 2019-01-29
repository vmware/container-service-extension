# container-service-extension
# Copyright (c) 2017 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

from container_service_extension.utils import process_response


class System(object):
    def __init__(self, client):
        self.client = client
        self._uri = self.client.get_api_uri() + '/cse'

    def get_info(self):
        method = 'GET'
        uri = '%s/system' % (self._uri)
        response = self.client._do_request_prim(
            method,
            uri,
            self.client._session,
            contents=None,
            media_type=None,
            accept_type='application/*+json',
            auth=None)
        return process_response(response)

    def stop(self):
        method = 'PUT'
        uri = '%s/system' % (self._uri)
        response = self.client._do_request_prim(
            method,
            uri,
            self.client._session,
            contents={'stopped': True},
            media_type=None,
            accept_type='application/*+json',
            auth=None)
        return process_response(response)

    def enable_service(self, enabled=True):
        method = 'PUT'
        uri = '%s/system' % (self._uri)
        response = self.client._do_request_prim(
            method,
            uri,
            self.client._session,
            contents={'enabled': enabled},
            media_type=None,
            accept_type='application/*+json',
            auth=None)
        return process_response(response)

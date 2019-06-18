# container-service-extension
# Copyright (c) 2019 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

from http import HTTPStatus
import json

import requests
from requests.auth import HTTPBasicAuth
from requests.exceptions import RequestException

from container_service_extension.nsxt.constants import RequestMethodVerb


class NSXTClient(object):
    """Simple REST bassed NSX-T client."""

    def __init__(self,
                 host,
                 username,
                 password,
                 http_proxy=None,
                 https_proxy=None,
                 verify_ssl=True,
                 logger_instance=None,
                 log_requests=False,
                 log_headers=False,
                 log_body=False):
        """Initialize a NSXTClient object.

        :param str host: fully qualified domain name of the NSX-T server.
        :param str username: username of a NSX-T user with Enterprise
            Administrator role.
        :param str password: password of the afore-mentioned user.
        :param str http_proxy: http proxy to use for unsecured REST calls to
            the NSX-T server. e.g. proxy.example.com:80
        :param str https_proxy: https proxy to use for secured REST calls to
            the.NSX_T server. e.g. proxy.example.com:443
        :param bool verify_ssl: if True, verify SSL certificates of remote
            host, else ignore verification.
        :param logging.Logger logger_instance: logger instance that will be
            used to log the REST calls.
        :param bool log_requests: if True, log REST request and responses
            else don't.
        :param bool log_headers: if True, log REST request and response headers
            else don't. Won't override flag 'log_requests'.
        :param bool log_body: if True, log REST request and response bodies
            else don't. Won't overwrite the flag 'log_requests'.
        """
        self._base_url = f"https://{host}/api/v1/"
        self._auth = HTTPBasicAuth(username, password)
        self._proxies = {}
        if http_proxy:
            self._proxies['http'] = "http://" + http_proxy
        if https_proxy:
            self._proxies['https'] = "https://" + https_proxy
        self._verify_ssl = verify_ssl
        if logger_instance:
            self.LOGGER = logger_instance
        else:
            from container_service_extension.logger import SERVER_NSXT_LOGGER
            self.LOGGER = SERVER_NSXT_LOGGER
        self._log_requests = log_requests
        self._log_headers = log_headers
        self._log_body = log_body

    def test_connectivity(self):
        """Test connectivity to the NSX-T server.

        :return: True, if server is alive, else False

        :rtype: bool
        """
        try:
            self.do_request(RequestMethodVerb.GET, "")
        except RequestException as err:
            if err.response is not None and \
                    (err.response.status_code == HTTPStatus.NOT_FOUND):
                return True
            else:
                return False
        except Exception:
            return False

    def do_request(self, method, resource_url_fragment, payload=None):
        """Make a request to NSX-T server.

        :param constants.RequestMethodVerb method: One of the HTTP verb defined
            in the enum.
        :param str resource_url_fragment: part of the url that idenfies just
            the resource (the host and the common /api/v1/ should be omitted).
            E.g .ns-group/{id}, /firewall/section/ etc.
        :param dict payload: JSON payload for the REST call.

        :return: body of the response text (JSON) in form of a dictionary.

        :rtype: dict

        :raises HTTPError: if the underlying REST call fails.
        """
        url = self._base_url + resource_url_fragment

        response = requests.request(
            method.value,
            url,
            auth=self._auth,
            json=payload,
            proxies=self._proxies,
            verify=self._verify_ssl)

        if self._log_requests:
            self.LOGGER.debug(f"Request uri : {(method.value).upper()} {url}")
            if self._log_headers:
                self.LOGGER.debug("Request hedears : "
                                  f"{response.request.headers}")
            if self._log_body and payload:
                self.LOGGER.debug(f"Request body : {response.request.body}")

        if self._log_requests:
            self.LOGGER.debug(f"Response status code: {response.status_code}")
            if self._log_headers:
                self.LOGGER.debug(f"Response hedears : {response.headers}")
            if self._log_body:
                self.LOGGER.debug(f"Response body : {response.text}")

        response.raise_for_status()

        if response.text:
            return json.loads(response.text)

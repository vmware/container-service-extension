# container-service-extension
# Copyright (c) 2019 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

import json

import requests
from requests.exceptions import RequestException

from container_service_extension.common.constants.shared_constants import RequestMethod  # noqa: E501
from container_service_extension.lib.telemetry.constants import PayloadKey

SEND_FAILED_MSG = "Failed to send telemetry payload"


class VacClient(object):
    """REST based client for Vmware Analytics Server.

    Attributes:
      base_url str: Vmware Analytics Cloud Url
      collector_id str: unique id that is supplied by VAC for the source of
      data.
      instance_id str: name of the instance that is using this
      client. This may be for example: which vCD installation.

    """

    def __init__(self,
                 base_url,
                 collector_id,
                 instance_id,
                 vcd_ceip_id,
                 verify_ssl=True,
                 logger_debug=None,
                 log_requests=False,
                 log_headers=False,
                 log_body=False):
        self._base_url = base_url
        self._collector_id = collector_id
        self._instance_id = instance_id
        self._vcd_ceip_id = vcd_ceip_id
        self._verify_ssl = verify_ssl
        self.LOGGER = logger_debug
        self._log_requests = log_requests
        self._log_headers = log_headers
        self._log_body = log_body

    def send_data(self, payload=None):
        """Send the given payload into Vmware Analytics Server.

        Trap all exceptions and log them.

        :param dict payload: JSON payload to ingest.
        """
        if not self._collector_id:
            msg = f"Invalid collector id.{SEND_FAILED_MSG}:{payload}"
            self.LOGGER.error(msg)
            return

        if not self._instance_id:
            msg = f"Invalid instance id.{SEND_FAILED_MSG}:{payload}"
            self.LOGGER.error(msg)
            return

        if self._vcd_ceip_id:
            payload[PayloadKey.VCD_CEIP_ID] = self._vcd_ceip_id

        response = None
        try:
            response = self._do_request(RequestMethod.POST, payload)
        except RequestException as err:
            msg = f"{err}.{SEND_FAILED_MSG}:{payload}"
            self.LOGGER.error(msg)
        except Exception as err:
            msg = f"{err}.{SEND_FAILED_MSG}:{payload}"
            self.LOGGER.error(msg)
        finally:
            if response:
                response.close()

    def _do_request(self, method, payload=None):
        """Make a request to Vmware Analytics Server.

        :param shared_constants.RequestMethod method: One of the HTTP verb
        defined in the enum.
        :param dict payload: JSON payload for the REST call.

        :return: body of the response text (JSON) in form of a dictionary.

        :rtype: dict

        :raises HTTPError: if the underlying REST call fails.
        """
        url = f"{self._base_url}?_c={self._collector_id}"
        if self._instance_id:
            url += f"&_i={self._instance_id}"

        response = requests.request(
            method.value,
            url,
            json=payload,
            verify=self._verify_ssl,
            headers={'Connection': 'close'})

        if self._log_requests:
            self.LOGGER.debug(f"Request uri : {(method.value).upper()} {url}")
            if self._log_headers:
                self.LOGGER.debug("Request headers : "
                                  f"{response.request.headers}")
            if self._log_body and payload:
                self.LOGGER.debug(f"Request body : {response.request.body}")

        if self._log_requests:
            self.LOGGER.debug(f"Response status code: {response.status_code}")
            if self._log_headers:
                self.LOGGER.debug(f"Response headers : {response.headers}")
            if self._log_body:
                self.LOGGER.debug(f"Response body : {response.text}")

        response.raise_for_status()

        if response.text:
            return json.loads(response.text)

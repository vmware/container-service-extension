# container-service-extension
# Copyright (c) 2020 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

from dataclasses import dataclass


@dataclass
class RequestContext:
    """Represents HTTP request context.

    This class is immutable.
    """
    body: dict
    url: str
    verb: str
    query_params: dict
    url_data: dict = None

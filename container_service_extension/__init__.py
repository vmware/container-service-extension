# container-service-extension
# Copyright (c) 2020 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Claus

from container_service_extension.logger import configure_all_file_loggers
from container_service_extension.logger import configure_null_logger

configure_all_file_loggers()
configure_null_logger()

# container-service-extension
# Copyright (c) 2020 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Claus

from container_service_extension.logging.logger import configure_all_file_loggers  # noqa: E501
from container_service_extension.logging.logger import configure_null_logger
from container_service_extension.common.thread_local_data import init_thread_local_data  # noqa: E501

init_thread_local_data()
configure_all_file_loggers()
configure_null_logger()

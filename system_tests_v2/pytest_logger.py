# container-service-extension
# Copyright (c) 2021 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

import logging


PYTEST_LOG_FILE_NAME = "pytest_log"
PYTEST_LOGGER_NAME = "log"
PYTEST_LOGGER: logging.Logger = logging.getLogger(PYTEST_LOGGER_NAME)

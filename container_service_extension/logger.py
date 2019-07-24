# container-service-extension
# Copyright (c) 2018 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

import datetime
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from container_service_extension.security import RedactingFilter

# max size for log files (8MB)
_MAX_BYTES = 2**23
_BACKUP_COUNT = 10

# timestamp for cse installation log files
_TIME = str(datetime.datetime.now()).split('.')[0]
_TIMESTAMP = _TIME.replace(' ', '_').replace(':', '-')

# standard formatters used by handlers
INFO_LOG_FORMATTER = logging.Formatter(fmt='%(asctime)s | '
                                       '%(levelname)s :: '
                                       '%(message)s',
                                       datefmt='%y-%m-%d %H:%M:%S')
DEBUG_LOG_FORMATTER = logging.Formatter(fmt='%(asctime)s | '
                                        '%(module)s:%(lineno)s - %(funcName)s '
                                        '| %(levelname)s :: '
                                        '%(message)s',
                                        datefmt='%y-%m-%d %H:%M:%S')

# create directory for all cse logs
LOGS_DIR_NAME = 'cse-logs'


def run_once(f):
    """Ensure that a function is only run once using this decorator."""
    def wrapper(*args, **kwargs):
        if not wrapper.has_run:
            wrapper.has_run = True
            return f(*args, **kwargs)
    wrapper.has_run = False
    return wrapper


# cse install logger and config
# cse installation logs to: cse-logs/cse-install_year-mo-day_hr-min-sec.log
INSTALL_LOGGER_NAME = 'container_service_extension.install'
INSTALL_LOG_FILEPATH = f"{LOGS_DIR_NAME}/cse-install_{_TIMESTAMP}.log"
INSTALL_LOGGER = logging.getLogger(INSTALL_LOGGER_NAME)

INSTALL_WIRELOG_FILEPATH = f"{LOGS_DIR_NAME}/cse-install-wire_{_TIMESTAMP}.log"

# cse client logger and config
# cse client logs info level and debug level logs to:
# cse-logs/cse-client-info.log
# cse-logs/cse-client-debug.log
# .log files are always the most current, with .log.9 being the oldest
CLIENT_LOGGER_NAME = 'container_service_extension.client'
CLIENT_INFO_LOG_FILEPATH = f"{LOGS_DIR_NAME}/cse-client-info.log"
CLIENT_DEBUG_LOG_FILEPATH = f"{LOGS_DIR_NAME}/cse-client-debug.log"
CLIENT_LOGGER = logging.getLogger(CLIENT_LOGGER_NAME)

# cse server logger and config
# cse server logs info level and debug level logs to:
# cse-logs/cse-server-info.log
# cse-logs/cse-server-debug.log
# cse - vCD wire logs are logged to:
# cse-logs/cse-server-wire-debug.log
# cse - nsxt logs are logged to:
# cse-logs/cse-nsxt-debug.log
# .log files are always the most current, with .log.9 being the oldest
SERVER_LOGGER_NAME = 'container_service_extension.server'
SERVER_INFO_LOG_FILEPATH = f"{LOGS_DIR_NAME}/cse-server-info.log"
SERVER_DEBUG_LOG_FILEPATH = f"{LOGS_DIR_NAME}/cse-server-debug.log"
SERVER_LOGGER = logging.getLogger(SERVER_LOGGER_NAME)

SERVER_DEBUG_WIRELOG_FILEPATH = f"{LOGS_DIR_NAME}/cse-server-wire-debug.log"

SERVER_NSXT_LOGGER_NAME = 'container_service_extension.server-nsxt'
SERVER_NSXT_LOG_FILEPATH = f"{LOGS_DIR_NAME}/cse-nsxt-debug.log"
SERVER_NSXT_LOGGER = logging.getLogger(SERVER_NSXT_LOGGER_NAME)


@run_once
def setup_log_file_directory():
    """Create directory for log files."""
    Path(LOGS_DIR_NAME).mkdir(parents=True, exist_ok=True)


@run_once
def configure_install_logger():
    """Configure cse install logger if it is not configured."""
    setup_log_file_directory()
    INSTALL_LOGGER.addFilter(RedactingFilter())
    INSTALL_LOGGER.setLevel(logging.DEBUG)
    file_handler = logging.FileHandler(INSTALL_LOG_FILEPATH)
    file_handler.setFormatter(DEBUG_LOG_FORMATTER)
    INSTALL_LOGGER.addHandler(file_handler)


@run_once
def configure_client_logger():
    """Configure cse client logger if it is not configured."""
    setup_log_file_directory()
    info_file_handler = RotatingFileHandler(CLIENT_INFO_LOG_FILEPATH,
                                            maxBytes=_MAX_BYTES,
                                            backupCount=_BACKUP_COUNT)
    info_file_handler.setLevel(logging.INFO)
    info_file_handler.setFormatter(INFO_LOG_FORMATTER)
    debug_file_handler = RotatingFileHandler(CLIENT_DEBUG_LOG_FILEPATH,
                                             maxBytes=_MAX_BYTES,
                                             backupCount=_BACKUP_COUNT)
    debug_file_handler.setFormatter(DEBUG_LOG_FORMATTER)

    CLIENT_LOGGER.addFilter(RedactingFilter())
    CLIENT_LOGGER.setLevel(logging.DEBUG)
    CLIENT_LOGGER.addHandler(info_file_handler)
    CLIENT_LOGGER.addHandler(debug_file_handler)


@run_once
def configure_server_logger():
    """Configure cse server & pika loggers if they are not configured."""
    setup_log_file_directory()

    nsxt_file_handler = RotatingFileHandler(SERVER_NSXT_LOG_FILEPATH,
                                            maxBytes=_MAX_BYTES,
                                            backupCount=_BACKUP_COUNT)
    nsxt_file_handler.setLevel(logging.DEBUG)
    nsxt_file_handler.setFormatter(DEBUG_LOG_FORMATTER)

    SERVER_NSXT_LOGGER.setLevel(logging.DEBUG)
    SERVER_NSXT_LOGGER.addFilter(RedactingFilter())
    SERVER_NSXT_LOGGER.addHandler(nsxt_file_handler)

    info_file_handler = RotatingFileHandler(SERVER_INFO_LOG_FILEPATH,
                                            maxBytes=_MAX_BYTES,
                                            backupCount=_BACKUP_COUNT)
    info_file_handler.setLevel(logging.INFO)
    info_file_handler.setFormatter(INFO_LOG_FORMATTER)

    debug_file_handler = RotatingFileHandler(SERVER_DEBUG_LOG_FILEPATH,
                                             maxBytes=_MAX_BYTES,
                                             backupCount=_BACKUP_COUNT)
    debug_file_handler.setLevel(logging.DEBUG)
    debug_file_handler.setFormatter(DEBUG_LOG_FORMATTER)

    SERVER_LOGGER.addFilter(RedactingFilter())
    SERVER_LOGGER.setLevel(logging.DEBUG)
    SERVER_LOGGER.addHandler(info_file_handler)
    SERVER_LOGGER.addHandler(debug_file_handler)

    pika_logger = logging.getLogger('pika')
    pika_logger.addFilter(RedactingFilter())
    pika_logger.setLevel(logging.WARNING)
    pika_logger.addHandler(info_file_handler)
    pika_logger.addHandler(debug_file_handler)

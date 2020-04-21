# container-service-extension
# Copyright (c) 2018 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

from collections import namedtuple
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
LOGS_DIR_NAME = Path.home() / '.cse-logs'


def run_once(f):
    """Ensure that a function is only run once using this decorator."""
    def wrapper(*args, **kwargs):
        if not wrapper.has_run:
            wrapper.has_run = True
            return f(*args, **kwargs)
    wrapper.has_run = False
    return wrapper


# cse install logger and config
# cse installation logs to: ~/.cse-logs/cse-install_year-mo-day_hr-min-sec.log
INSTALL_LOGGER_NAME = 'container_service_extension.install'
INSTALL_LOG_FILEPATH = f"{LOGS_DIR_NAME}/cse-install_{_TIMESTAMP}.log"
INSTALL_LOGGER = logging.getLogger(INSTALL_LOGGER_NAME)

# logfile for pyvcloud
INSTALL_WIRELOG_FILEPATH = f"{LOGS_DIR_NAME}/cse-install-wire_{_TIMESTAMP}.log"

# cse client logger and config
# cse client logs info level and debug level logs to:
# ~/.cse-logs/cse-client-info.log
# ~/.cse-logs/cse-client-debug.log
# .log files are always the most current, with .log.9 being the oldest
CLIENT_LOGGER_NAME = 'container_service_extension.client'
CLIENT_INFO_LOG_FILEPATH = f"{LOGS_DIR_NAME}/cse-client-info.log"
CLIENT_DEBUG_LOG_FILEPATH = f"{LOGS_DIR_NAME}/cse-client-debug.log"
CLIENT_LOGGER = logging.getLogger(CLIENT_LOGGER_NAME)

CLIENT_WIRE_LOGGER_NAME = 'container_service_extension.client.wire'
CLIENT_WIRE_LOGGER_FILEPATH = f"{LOGS_DIR_NAME}/cse-client-wire_{_TIMESTAMP}.log" # noqa: E501
CLIENT_WIRE_LOGGER = logging.getLogger(CLIENT_WIRE_LOGGER_NAME)

# cse server logger and config
# cse server logs info level and debug level logs to:
# ~/.cse-logs/cse-server-info.log
# ~/.cse-logs/cse-server-debug.log
# cse - vCD wire logs are logged to:
# ~/.cse-logs/cse-server-wire-debug.log
# cse - nsxt wire logs are logged to:
# ~/.cse-logs/nsxt-wire.log
# cse - pks wire logs are logged to:
# ~/.cse-logs/pks-wire.log
# cse - cloudapi wire logs are logged to:
# ~/.cse-logs/cloudapi-wire.log
# .log files are always the most current, with .log.9 being the oldest
SERVER_ClI_LOGGER_NAME = 'container_service_extension.server-cli'
SERVER_CLI_LOG_FILEPATH = f"{LOGS_DIR_NAME}/cse-server-cli.log"
SERVER_CLI_LOGGER = logging.getLogger(SERVER_ClI_LOGGER_NAME)

SERVER_LOGGER_NAME = 'container_service_extension.server'
SERVER_INFO_LOG_FILEPATH = f"{LOGS_DIR_NAME}/cse-server-info.log"
SERVER_DEBUG_LOG_FILEPATH = f"{LOGS_DIR_NAME}/cse-server-debug.log"
SERVER_LOGGER = logging.getLogger(SERVER_LOGGER_NAME)

# logfile for pyvcloud
SERVER_DEBUG_WIRELOG_FILEPATH = f"{LOGS_DIR_NAME}/cse-server-wire-debug.log"

SERVER_NSXT_WIRE_LOGGER_NAME = 'container_service_extension.server-nsxt.wire'
SERVER_NSXT_WIRE_LOG_FILEPATH = f"{LOGS_DIR_NAME}/nsxt-wire.log"
SERVER_NSXT_WIRE_LOGGER = logging.getLogger(SERVER_NSXT_WIRE_LOGGER_NAME)

SERVER_PKS_WIRE_LOGGER_NAME = 'container_service_extension.server-pks.wire'
SERVER_PKS_WIRE_LOG_FILEPATH = f"{LOGS_DIR_NAME}/pks-wire.log"
SERVER_PKS_WIRE_LOGGER = logging.getLogger(SERVER_PKS_WIRE_LOGGER_NAME)

SERVER_CLOUDAPI_WIRE_LOGGER_NAME = 'container_service_extension.server-cloudapi.wire' # noqa: E501
SERVER_CLOUDAPI_LOG_FILEPATH = f"{LOGS_DIR_NAME}/cloudapi-wire.log"
SERVER_CLOUDAPI_WIRE_LOGGER = logging.getLogger(SERVER_CLOUDAPI_WIRE_LOGGER_NAME) # noqa: E501

# NullLogger doesn't perform logging.
NULL_LOGGER = logging.getLogger('container_service_extension.null-logger')


@run_once
def setup_log_file_directory():
    """Create directory for log files."""
    Path(LOGS_DIR_NAME).mkdir(parents=True, exist_ok=True)


@run_once
def configure_all_file_loggers():
    """Configure all loggers if not configured."""
    setup_log_file_directory()
    LoggerConfig = namedtuple('LoggerConfig', 'name filepath formatter logger')
    configs = [
        LoggerConfig(INSTALL_LOG_FILEPATH, INSTALL_LOG_FILEPATH,
                     DEBUG_LOG_FORMATTER, INSTALL_LOGGER),
        LoggerConfig(CLIENT_LOGGER_NAME, CLIENT_INFO_LOG_FILEPATH,
                     INFO_LOG_FORMATTER, CLIENT_LOGGER),
        LoggerConfig(CLIENT_LOGGER_NAME, CLIENT_DEBUG_LOG_FILEPATH,
                     DEBUG_LOG_FORMATTER, CLIENT_LOGGER),
        LoggerConfig(CLIENT_WIRE_LOGGER_NAME, CLIENT_WIRE_LOGGER_FILEPATH,
                     DEBUG_LOG_FORMATTER, CLIENT_WIRE_LOGGER),
        LoggerConfig(SERVER_ClI_LOGGER_NAME, SERVER_CLI_LOG_FILEPATH,
                     DEBUG_LOG_FORMATTER, SERVER_CLI_LOGGER),
        LoggerConfig(SERVER_LOGGER_NAME, SERVER_INFO_LOG_FILEPATH,
                     INFO_LOG_FORMATTER, SERVER_LOGGER),
        LoggerConfig(SERVER_LOGGER_NAME, SERVER_DEBUG_LOG_FILEPATH,
                     DEBUG_LOG_FORMATTER, SERVER_LOGGER),
        LoggerConfig(SERVER_NSXT_WIRE_LOGGER_NAME, SERVER_NSXT_WIRE_LOG_FILEPATH, # noqa: E501
                     DEBUG_LOG_FORMATTER, SERVER_NSXT_WIRE_LOGGER),
        LoggerConfig(SERVER_PKS_WIRE_LOGGER_NAME, SERVER_PKS_WIRE_LOG_FILEPATH,
                     DEBUG_LOG_FORMATTER, SERVER_PKS_WIRE_LOGGER),
        LoggerConfig(SERVER_CLOUDAPI_WIRE_LOGGER_NAME, SERVER_CLOUDAPI_LOG_FILEPATH, # noqa: E501
                     DEBUG_LOG_FORMATTER, SERVER_CLOUDAPI_WIRE_LOGGER)
    ]

    for logger_config in configs:
        file_handler = RotatingFileHandler(logger_config.filepath,
                                           maxBytes=_MAX_BYTES,
                                           backupCount=_BACKUP_COUNT,
                                           delay=True)
        logger_config.logger.addFilter(RedactingFilter())
        if logger_config.formatter == INFO_LOG_FORMATTER:
            logger_config.logger.setLevel(logging.INFO)
            file_handler.setLevel(logging.INFO)
            file_handler.setFormatter(INFO_LOG_FORMATTER)
        elif logger_config.formatter == DEBUG_LOG_FORMATTER:
            logger_config.logger.setLevel(logging.DEBUG)
            file_handler.setLevel(logging.DEBUG)
            file_handler.setFormatter(DEBUG_LOG_FORMATTER)
        logger_config.logger.addHandler(file_handler)


@run_once
def configure_null_logger():
    """Configure null logger if it is not configured."""
    nullhandler = logging.NullHandler()
    NULL_LOGGER.addHandler(nullhandler)

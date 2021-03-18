# container-service-extension
# Copyright (c) 2017 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause
from pyvcloud.vcd.org import Org

import container_service_extension.common.constants.server_constants as server_constants  # noqa: E501
import container_service_extension.common.utils.core_utils as utils
import container_service_extension.common.utils.pyvcloud_utils as vcd_utils
from container_service_extension.logging.logger import SERVER_CLI_LOGGER


def create_cse_service_role(client,
                            msg_update_callback=utils.NullPrinter(),
                            logger_debug=SERVER_CLI_LOGGER):
    """Create Service Role for CSE operations.

    The method can only be called by System Administrator user
    :param client: pyvcloud.vcd.client to interact with VCD HOST
    :param core_utils.ConsoleMessagePrinter msg_update_callback: Callback object. # noqa: E501

    :raises pyvcloud.vcd.exceptions.BadRequestException when Role already exist
    :raises pyvcloud.vcd.exceptions.EntityNotFoundException when Right doesn't
    exist
    """
    # We can't check if the user is Sysadmin or some other user in system org,
    # as the values will need to be hardcoded.
    # For now just check if its system org or not.
    vcd_utils.raise_error_if_user_not_from_system_org(client)

    system_org = Org(client, resource=client.get_org())
    system_org.create_role(server_constants.CSE_SERVICE_ROLE_NAME,
                           server_constants.CSE_SERVICE_ROLE_DESC,
                           server_constants.CSE_SERVICE_ROLE_RIGHTS)

    msg = f"Successfully created { server_constants.CSE_SERVICE_ROLE_NAME}"
    msg_update_callback.general(msg)
    logger_debug.info(msg)
    return

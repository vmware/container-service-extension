# container-service-extension
# Copyright (c) 2020 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

from enum import Enum
from enum import unique

import click
import pyvcloud.vcd.client as vcd_client
from vcd_cli.utils import restore_session


class ApiVersion(str, Enum):  # TODO(): use pyvcloud constant
    VERSION_34 = '34.0'
    VERSION_35 = '35.0'


@unique
class GroupKey(str, Enum):
    CLUSTER = 'cluster'
    NODE = 'node'


@unique
class CommandNameKey(str, Enum):
    CREATE = 'create'
    NODE = 'node'


# List of unsupported commands by Api Version
UNSUPPORTED_COMMANDS_BY_VERSION = {
    vcd_client.ApiVersion.VERSION_33.value: {
        GroupKey.CLUSTER: ['apply']
    },
    ApiVersion.VERSION_34: {
        GroupKey.CLUSTER: ['apply']
    }
}

# List of unsupported commands by Api Version
UNSUPPORTED_COMMAND_OPTIONS_BY_VERSION = {
    ApiVersion.VERSION_35: {
        GroupKey.CLUSTER: {
            CommandNameKey.CREATE: ['cpu', 'memory']
        }
    }
}


class GroupCommandFilter(click.Group):
    """Filter for CLI group commands.

    Returns set of supported sub-commands by specific API version
    """

    def get_command(self, ctx, cmd_name):
        """Override this click method to customize.

        :param click.core.Context ctx: Click Context
        :param str cmd_name: name of the command (ex:create, delete, resize)
        :return: Click command object for 'cmd_name'
        :rtype: click.Core.Command
        """
        client = self.get_client(ctx)
        # Apply filtering if client is available
        if client:
            version = client.get_api_version()
            # Skip the command if not supported
            if cmd_name in UNSUPPORTED_COMMANDS_BY_VERSION.get(version, {}).get(self.name, []):  # noqa: E501
                return None

            cmd = click.Group.get_command(self, ctx, cmd_name)
            # Remove all unsupported options for this command, if any
            filtered_params = [
                param for param in cmd.params
                if param.name not in UNSUPPORTED_COMMAND_OPTIONS_BY_VERSION.get(version, {}).get(self.name, {}).get(cmd_name, [])]  # noqa: E501
            cmd.params = filtered_params

        return click.Group.get_command(self, ctx, cmd_name)

    def get_client(self, ctx):
        client = None
        try:
            restore_session(ctx)
            client = ctx.obj['client']
        except Exception:
            pass
        return client

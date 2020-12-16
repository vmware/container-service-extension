# container-service-extension
# Copyright (c) 2020 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

from enum import Enum
from enum import unique
import os

import click
import pyvcloud.vcd.client as vcd_client

import container_service_extension.client.constants as cli_constants
import container_service_extension.client.utils as client_utils
from container_service_extension.logger import CLIENT_LOGGER
from container_service_extension.utils import str_to_bool


@unique
class GroupKey(str, Enum):
    CLUSTER = 'cluster'
    NODE = 'node'
    OVDC = 'ovdc'
    PKS = 'pks'
    SYSTEM = 'system'
    TEMPLATE = 'template'
    VERSION = 'version'


@unique
class CommandNameKey(str, Enum):
    CONFIG = 'config'
    CREATE = 'create'
    DELETE = 'delete'
    UPGRADE = 'upgrade'
    UPGRADE_PLAN = 'upgrade-plan'
    INFO = 'info'
    NODE = 'node'
    ENABLE = 'enable'
    DISABLE = 'disable'


# List of unsupported commands by Api Version
UNSUPPORTED_COMMANDS_BY_VERSION = {
    vcd_client.ApiVersion.VERSION_35.value: [GroupKey.NODE]
}


# List of unsupported subcommands by Api Version
UNSUPPORTED_SUBCOMMANDS_BY_VERSION = {
    vcd_client.ApiVersion.VERSION_33.value: {
        GroupKey.CLUSTER: ['apply', 'delete-nfs', 'share', 'share-list'],
        # TODO(metadata based enablement for < v35): Revisit after decision
        # to support metadata way of enabling for native clusters
        GroupKey.OVDC: ['enable', 'disable', 'list', 'info']
    },
    vcd_client.ApiVersion.VERSION_34.value: {
        GroupKey.CLUSTER: ['apply', 'delete-nfs', 'share', 'share-list'],
        # TODO(metadata based enablement for < v35): Revisit after decision
        # to support metadata way of enabling for native clusters
        GroupKey.OVDC: ['enable', 'disable', 'list', 'info']
    },
    vcd_client.ApiVersion.VERSION_35.value: {
        GroupKey.CLUSTER: ['create', 'resize'],
        GroupKey.OVDC: ['compute-policy', 'info']
    }
}

# List of unsupported subcommand options by Api Version
# TODO: All unsupported options depending on the command will go here
UNSUPPORTED_SUBCOMMAND_OPTIONS_BY_VERSION = {
    vcd_client.ApiVersion.VERSION_33.value: {
        GroupKey.CLUSTER: {
            CommandNameKey.CREATE: ['sizing_class'],
            CommandNameKey.DELETE: ['k8_runtime', 'cluster_id'],
            CommandNameKey.INFO: ['k8_runtime', 'cluster_id'],
            CommandNameKey.UPGRADE: ['k8_runtime'],
            CommandNameKey.UPGRADE_PLAN: ['k8_runtime'],
            CommandNameKey.CONFIG: ['k8_runtime', 'cluster_id']
        },
    },

    vcd_client.ApiVersion.VERSION_34.value: {
        GroupKey.CLUSTER: {
            CommandNameKey.CREATE: ['sizing_class'],
            CommandNameKey.DELETE: ['k8_runtime', 'cluster_id'],
            CommandNameKey.INFO: ['k8_runtime', 'cluster_id'],
            CommandNameKey.UPGRADE: ['k8_runtime'],
            CommandNameKey.UPGRADE_PLAN: ['k8_runtime'],
            CommandNameKey.CONFIG: ['k8_runtime', 'cluster_id']
        }
    },

    vcd_client.ApiVersion.VERSION_35.value: {
        GroupKey.CLUSTER: {
            CommandNameKey.CREATE: ['cpu', 'memory']
        },
        GroupKey.OVDC: {
            CommandNameKey.ENABLE: [] if str_to_bool(
                os.getenv(cli_constants.ENV_CSE_TKG_PLUS_ENABLED)) else ['enable_tkg_plus'],  # noqa: E501
            CommandNameKey.DISABLE: [] if str_to_bool(
                os.getenv(cli_constants.ENV_CSE_TKG_PLUS_ENABLED)) else ['disable_tkg_plus']  # noqa: E501
        }
    }
}

UNSUPPORTED_COMMANDS_WITH_SERVER_NOT_RUNNING_BY_VERSION = {
    vcd_client.ApiVersion.VERSION_35.value: [GroupKey.VERSION, GroupKey.OVDC,
                                             GroupKey.SYSTEM, GroupKey.TEMPLATE,  # noqa: E501
                                             GroupKey.PKS]
}

UNSUPPORTED_SUBCOMMANDS_WITH_SERVER_NOT_RUNNING_BY_VERSION = {
    vcd_client.ApiVersion.VERSION_35.value: {
        GroupKey.CLUSTER: ['upgrade', 'upgrade-plan']
    }
}


class GroupCommandFilter(click.Group):
    """Filter for CLI group commands.

    Returns set of supported sub-commands by specific API version
    """

    # TODO(Make get_command hierarchy aware): Since get_command() cannot know
    # the hierarchical context of 'cmd_name', there is a possibility that
    # there will be unintended command ommition.
    # Example: If 'node' command is ommited in cse group, and the filter is
    # used in pks group (which is part of cse group), then the 'node' command
    # under pks group also will be ommitted.
    def get_command(self, ctx, cmd_name):
        """Override this click method to customize.

        :param click.core.Context ctx: Click Context
        :param str cmd_name: name of the command (ex:create, delete, resize)
        :return: Click command object for 'cmd_name'
        :rtype: click.Core.Command
        """
        try:
            if not type(ctx.obj) is dict or not ctx.obj.get('client'):
                client_utils.cse_restore_session(ctx)
            client = ctx.obj['client']
            version = client.get_api_version()

            # Skipping some commands when CSE server is not running
            if client_utils.is_cli_for_tkg_only() and \
                cmd_name in [*UNSUPPORTED_COMMANDS_WITH_SERVER_NOT_RUNNING_BY_VERSION.get(version, []),  # noqa: E501
                             *UNSUPPORTED_SUBCOMMANDS_WITH_SERVER_NOT_RUNNING_BY_VERSION.get(version, {}).get(self.name, [])]:  # noqa: E501
                return None

            # Skip the command if not supported
            if cmd_name in UNSUPPORTED_COMMANDS_BY_VERSION.get(version, []):
                return None

            # Skip the subcommand if not supported
            unsupported_subcommands = UNSUPPORTED_SUBCOMMANDS_BY_VERSION.get(version, {}).get(self.name, [])  # noqa: E501
            if cmd_name in unsupported_subcommands:
                return None

            cmd = click.Group.get_command(self, ctx, cmd_name)
            unsupported_params = UNSUPPORTED_SUBCOMMAND_OPTIONS_BY_VERSION.get(version, {}).get(self.name, {}).get(cmd_name, [])  # noqa: E501
            # Remove all unsupported options for this subcommand, if any
            filtered_params = [param for param in cmd.params if param.name not in unsupported_params]  # noqa: E501
            cmd.params = filtered_params
        except Exception as e:
            CLIENT_LOGGER.debug(f'exception while filtering {cmd_name}: {e}')
            pass

        return click.Group.get_command(self, ctx, cmd_name)

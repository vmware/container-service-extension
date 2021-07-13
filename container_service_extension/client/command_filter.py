# container-service-extension
# Copyright (c) 2020 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

import os

import click
import pyvcloud.vcd.client as vcd_client

import container_service_extension.client.constants as cli_constants
import container_service_extension.client.utils as client_utils
from container_service_extension.common.utils.core_utils import str_to_bool
from container_service_extension.logging.logger import CLIENT_LOGGER


# List of unsupported commands by Api Version
UNSUPPORTED_COMMANDS_BY_VERSION = {
    vcd_client.ApiVersion.VERSION_35.value: [cli_constants.GroupKey.NODE],
    vcd_client.ApiVersion.VERSION_36.value: [cli_constants.GroupKey.NODE]
}


# List of unsupported subcommands by Api Version
UNSUPPORTED_SUBCOMMANDS_BY_VERSION = {
    vcd_client.ApiVersion.VERSION_33.value: {
        cli_constants.GroupKey.CLUSTER:
            ['apply', 'delete-nfs', 'share', 'share-list', 'unshare'],
        # TODO(metadata based enablement for < v35): Revisit after decision
        # to support metadata way of enabling for native clusters
        cli_constants.GroupKey.OVDC: ['enable', 'disable', 'list', 'info']
    },
    vcd_client.ApiVersion.VERSION_34.value: {
        cli_constants.GroupKey.CLUSTER: [
            'apply', 'delete-nfs', 'share', 'share-list', 'unshare'],
        # TODO(metadata based enablement for < v35): Revisit after decision
        # to support metadata way of enabling for native clusters
        cli_constants.GroupKey.OVDC: ['enable', 'disable', 'list', 'info']
    },
    vcd_client.ApiVersion.VERSION_35.value: {
        cli_constants.GroupKey.CLUSTER: ['create', 'resize', 'share',
                                         'share-list', 'unshare'],
        cli_constants.GroupKey.OVDC: ['compute-policy', 'info']
    },
    vcd_client.ApiVersion.VERSION_36.value: {
        cli_constants.GroupKey.CLUSTER: ['create', 'resize', 'upgrade'],
        cli_constants.GroupKey.OVDC: ['compute-policy', 'info']
    }
}

# List of unsupported subcommand options by Api Version
# TODO: All unsupported options depending on the command will go here
UNSUPPORTED_SUBCOMMAND_OPTIONS_BY_VERSION = {
    vcd_client.ApiVersion.VERSION_33.value: {
        cli_constants.GroupKey.CLUSTER: {
            cli_constants.CommandNameKey.CREATE: ['sizing_class'],
            cli_constants.CommandNameKey.DELETE: ['k8_runtime', 'cluster_id'],
            cli_constants.CommandNameKey.INFO: ['k8_runtime', 'cluster_id'],
            cli_constants.CommandNameKey.UPGRADE: ['k8_runtime'],
            cli_constants.CommandNameKey.UPGRADE_PLAN: ['k8_runtime'],
            cli_constants.CommandNameKey.CONFIG: ['k8_runtime', 'cluster_id']
        },
    },

    vcd_client.ApiVersion.VERSION_34.value: {
        cli_constants.GroupKey.CLUSTER: {
            cli_constants.CommandNameKey.CREATE: ['sizing_class'],
            cli_constants.CommandNameKey.DELETE: ['k8_runtime', 'cluster_id'],
            cli_constants.CommandNameKey.INFO: ['k8_runtime', 'cluster_id'],
            cli_constants.CommandNameKey.UPGRADE: ['k8_runtime'],
            cli_constants.CommandNameKey.UPGRADE_PLAN: ['k8_runtime'],
            cli_constants.CommandNameKey.CONFIG: ['k8_runtime', 'cluster_id']
        }
    },

    vcd_client.ApiVersion.VERSION_35.value: {
        cli_constants.GroupKey.CLUSTER: {
            cli_constants.CommandNameKey.CREATE: ['cpu', 'memory']
        },
        cli_constants.GroupKey.OVDC: {
            cli_constants.CommandNameKey.ENABLE: [] if str_to_bool(
                os.getenv(cli_constants.ENV_CSE_TKG_PLUS_ENABLED)) else ['enable_tkg_plus'],  # noqa: E501
            cli_constants.CommandNameKey.DISABLE: [] if str_to_bool(
                os.getenv(cli_constants.ENV_CSE_TKG_PLUS_ENABLED)) else ['disable_tkg_plus']  # noqa: E501
        }
    }
}

UNSUPPORTED_COMMANDS_WITH_SERVER_NOT_RUNNING_BY_VERSION = {
    vcd_client.ApiVersion.VERSION_35.value: [
        cli_constants.GroupKey.VERSION,
        cli_constants.GroupKey.OVDC,
        cli_constants.GroupKey.SYSTEM,
        cli_constants.GroupKey.TEMPLATE,
        cli_constants.GroupKey.PKS
    ]
}

UNSUPPORTED_SUBCOMMANDS_WITH_SERVER_NOT_RUNNING_BY_VERSION = {
    vcd_client.ApiVersion.VERSION_35.value: {
        cli_constants.GroupKey.CLUSTER: ['upgrade', 'upgrade-plan']
    }
}


class GroupCommandFilter(click.Group):
    """Filter for CLI group commands.

    Returns set of supported sub-commands by specific API version
    """

    # TODO(Make get_command hierarchy aware): Since get_command() cannot know
    # the hierarchical context of 'cmd_name', there is a possibility that
    # there will be unintended command omission.
    # Example: If 'node' command is omitted in cse group, and the filter is
    # used in pks group (which is part of cse group), then the 'node' command
    # under pks group also will be omitted.
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
            if client_utils.is_cli_for_tkg_s_only() and \
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

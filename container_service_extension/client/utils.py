# container-service-extension
# Copyright (c) 2020 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause
import click
from pyvcloud.vcd.client import Client
import pyvcloud.vcd.org as vcd_org
import pyvcloud.vcd.utils as vcd_utils
import requests
import six
from vcd_cli.profiles import Profiles
from vcd_cli.utils import stdout

from container_service_extension.client import system as syst
from container_service_extension.client.constants import CSE_SERVER_RUNNING
import container_service_extension.def_.utils as def_utils
from container_service_extension.exceptions import CseResponseError
from container_service_extension.logger import NULL_LOGGER
import container_service_extension.shared_constants as shared_constants
from container_service_extension.shared_constants import CSE_SERVER_API_VERSION
from container_service_extension.shared_constants import CSE_SERVER_BUSY_KEY
from container_service_extension.utils import extract_id_from_href

_RESTRICT_CLI_TO_TKG_OPERATIONS = False


def is_cli_for_tkg_only():
    global _RESTRICT_CLI_TO_TKG_OPERATIONS
    return _RESTRICT_CLI_TO_TKG_OPERATIONS


def restrict_cli_to_tkg_operations():
    global _RESTRICT_CLI_TO_TKG_OPERATIONS
    _RESTRICT_CLI_TO_TKG_OPERATIONS = True


def enable_cli_for_all_operations():
    global _RESTRICT_CLI_TO_TKG_OPERATIONS
    _RESTRICT_CLI_TO_TKG_OPERATIONS = False


def cse_restore_session(ctx, vdc_required=False) -> None:
    """Restores the session with vcd client with right server api version.

    Replace the vcd client in ctx.obj with new client created with server api
    version. Also saves the server api version in profiles.

    :param <click.core.Context> ctx: click context
    :param bool vdc_required: is vdc required or not
    :return:
    """
    # Always override the vcd_client by new client with CSE server api version.
    if type(ctx.obj) is not dict or not ctx.obj.get('client'):
        profiles = Profiles.load()
        token = profiles.get('token')
        if token is None or len(token) == 0:
            raise Exception('Can\'t restore session, please login again.')
        if not profiles.get('verify'):
            if not profiles.get('disable_warnings'):
                click.secho(
                    'InsecureRequestWarning: '
                    'Unverified HTTPS request is being made. '
                    'Adding certificate verification is strongly '
                    'advised.',
                    fg='yellow',
                    err=True)
            requests.packages.urllib3.disable_warnings()

        client = Client(
            profiles.get('host'),
            api_version=profiles.get('api_version'),
            verify_ssl_certs=profiles.get('verify'),
            log_file='vcd.log',
            log_requests=profiles.get('log_request'),
            log_headers=profiles.get('log_header'),
            log_bodies=profiles.get('log_body'))
        client.rehydrate_from_token(
            profiles.get('token'), profiles.get('is_jwt_token'))

        ctx.obj = {}
        ctx.obj['client'] = client

    _override_client(ctx)

    if vdc_required:
        if not ctx.obj['profiles'].get('vdc_in_use') or \
                not ctx.obj['profiles'].get('vdc_href'):
            raise Exception('select a virtual datacenter')


def _override_client(ctx) -> None:
    """Replace the vcd client in ctx.obj with new one.

    New vcd client takes the CSE server_api_version as api_version param.
    Save profile also with 'cse_server_api_version' for subsequent commands.

    :param <click.core.Context> ctx: click context
    """
    profiles = Profiles.load()
    # if the key CSE_SERVER_RUNNING is not present in the profiles.yaml,
    # we make an assumption that CSE server is running
    is_cse_server_running = profiles.get(CSE_SERVER_RUNNING, default=True)
    cse_server_api_version = profiles.get(CSE_SERVER_API_VERSION)
    if not is_cse_server_running:
        restrict_cli_to_tkg_operations()
        ctx.obj['profiles'] = profiles
        return

    # Get server_api_version; save it in profiles if doesn't exist
    if not cse_server_api_version:
        try:
            system = syst.System(ctx.obj['client'])
            sys_info = system.get_info()
            cse_server_api_version = sys_info.get(CSE_SERVER_API_VERSION)
            profiles.set(CSE_SERVER_API_VERSION, cse_server_api_version)
            profiles.set(CSE_SERVER_RUNNING, True)
            profiles.save()
        except CseResponseError:
            # If request to CSE server times out
            profiles.set(CSE_SERVER_RUNNING, False)
            # restrict CLI for only TKG operations
            restrict_cli_to_tkg_operations()
            ctx.obj['profiles'] = profiles
            profiles.save()
            return
    client = Client(
        profiles.get('host'),
        api_version=cse_server_api_version,
        verify_ssl_certs=profiles.get('verify'),
        log_file='vcd.log',
        log_requests=profiles.get('log_request'),
        log_headers=profiles.get('log_header'),
        log_bodies=profiles.get('log_body'))
    client.rehydrate_from_token(profiles.get('token'), profiles.get('is_jwt_token'))  # noqa: E501
    ctx.obj['client'] = client
    ctx.obj['profiles'] = profiles


def construct_filters(**kwargs):
    filters = {}
    if kwargs.get('org'):
        filters[def_utils.ClusterEntityFilterKey.ORG_NAME.value] = kwargs['org']  # noqa: E501
    if kwargs.get('vdc'):
        filters[def_utils.ClusterEntityFilterKey.OVDC_NAME.value] = kwargs['vdc']  # noqa: E501
    return filters


def construct_task_console_message(task_href: str) -> str:
    msg = "Run the following command to track the status of the cluster:\n"
    task_id = task_href.split('/')[-1]
    msg += f"vcd task wait {task_id}"
    return msg


def swagger_object_to_dict(obj):
    """Convert a swagger obejct to a dictionary without changing case type."""
    # reference: https://github.com/swagger-api/swagger-codegen/issues/8948
    result = {}
    o_map = obj.attribute_map

    for attr, _ in six.iteritems(obj.swagger_types):
        value = getattr(obj, attr)
        if isinstance(value, list):
            result[o_map[attr]] = list(map(
                lambda x: swagger_object_to_dict(x) if hasattr(x, "to_dict") else x,  # noqa: E501
                value
            ))
        elif hasattr(value, "to_dict"):
            result[o_map[attr]] = swagger_object_to_dict(value)
        elif isinstance(value, dict):
            result[o_map[attr]] = dict(map(
                lambda item: (item[0], swagger_object_to_dict(item[1]))
                if hasattr(item[1], "to_dict") else item,
                value.items()
            ))
        else:
            result[o_map[attr]] = value

    return result


def filter_columns(result, value_field_to_display_field):
    """Extract selected fields from each list item in result.

    :param list(dict) or dict result: row of records
    :param dict value_field_to_display_field: mapping of value field to
    respective display name in result set. Extract selected fields from result
    based on value fields from this dictionary.
    :return: filtered list or dict of record(s) from result
    :rtype: list(dict) or dict
    """
    if isinstance(result, list):
        filtered_result = []
        for result_record in result:
            filtered_record = {}
            for value_field, display_field in value_field_to_display_field.items():  # noqa: E501
                filtered_record[display_field] = result_record.get(value_field, '')  # noqa: E501
            filtered_result.append(filtered_record)
        return filtered_result
    elif isinstance(result, dict):
        # If the server result is the CSE Server busy message, there is no
        # result to filter, so the CSE Server busy message is returned as is
        if result.get(CSE_SERVER_BUSY_KEY) is not None:
            return result

        filtered_result = {
            display_field: result.get(value_field, '')
            for value_field, display_field in value_field_to_display_field.items()  # noqa: E501
        }
        return filtered_result


def create_user_name_to_id_dict(client: Client, users_set: set, org_href):
    """Get a dictionary of users to user ids from a list of user names.

    :param Client client: current client
    :param set users_set: set of user names
    :param str org_href: href of the org to search in

    :return: dict of user name keys and user id values
    :rtype: dict
    :raise Exception is not all id's are found for users
    """
    own_users_set = users_set.copy()
    org = vcd_org.Org(client, org_href)
    org_users = org.list_users()
    user_name_to_id_dict = {}
    for user_str_elem in org_users:
        curr_user_dict = vcd_utils.to_dict(user_str_elem, exclude=[])
        curr_user_name = curr_user_dict['name']
        if curr_user_name in own_users_set:
            user_id = extract_id_from_href(curr_user_dict['href'])
            user_name_to_id_dict[curr_user_name] = shared_constants.USER_URN_PREFIX + user_id  # noqa: E501
            own_users_set.remove(curr_user_name)

        # Stop searching if all needed names and ids found
        if len(own_users_set) == 0:
            break
    if len(own_users_set) > 0:
        raise Exception(f"No user ids found for: {list(own_users_set)}")
    return user_name_to_id_dict


def access_level_reduced(new_access_urn, curr_access_urn):
    """Check if the access level is reduced.

    Only true is the current access level is full-control and the new access
    level is not full control, or is the current access level is read-write and
    the new access level is read-only.
    """
    if curr_access_urn == shared_constants.FULL_CONTROL_ACCESS_LEVEL_ID and \
            new_access_urn != shared_constants.FULL_CONTROL_ACCESS_LEVEL_ID:
        return True
    if curr_access_urn == shared_constants.READ_WRITE_ACCESS_LEVEL_ID and \
            new_access_urn == shared_constants.READ_ONLY_ACCESS_LEVEL_ID:
        return True
    return False


def print_paginated_result(generator, should_print_all=False, logger=NULL_LOGGER):  # noqa: E501
    """Print results by prompting the user for more results.

    :param Generator[(List[dict], int), None, None] generator: generator which
        yields a list of results and a boolean indicating if more results
        are present.
    :param bool should_print_all: print all the results without prompting the
        user.
    :param logger logger: logger to log the results or exceptions.
    """
    try:
        headers_printed = False
        for result, has_more_results in generator:
            stdout(result, sort_headers=False,
                   show_headers=not headers_printed)
            headers_printed = True
            logger.debug(result)
            if not has_more_results or \
                    not (should_print_all or click.confirm("Do you want more results?")):  # noqa: E501
                break
    except Exception as e:
        logger.error(f"Error while iterating over the paginated response: {e}")
        raise

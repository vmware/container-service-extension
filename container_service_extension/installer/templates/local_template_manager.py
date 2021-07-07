# container-service-extension
# Copyright (c) 2019 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

import ast
import os
import pathlib

from pyvcloud.vcd.client import MetadataDomain
from pyvcloud.vcd.client import MetadataVisibility
from pyvcloud.vcd.org import Org
from pyvcloud.vcd.utils import metadata_to_dict
import semantic_version

from container_service_extension.common.constants.server_constants import LegacyLocalTemplateKey  # noqa: E501
from container_service_extension.common.constants.server_constants import LocalTemplateKey  # noqa: E501
import container_service_extension.common.constants.shared_constants as \
    shared_constants
import container_service_extension.common.utils.core_utils as utils
from container_service_extension.common.utils.pyvcloud_utils import get_org
import container_service_extension.common.utils.server_utils as server_utils
import container_service_extension.logging.logger as logger


LOCAL_SCRIPTS_DIR = '.cse_scripts'


def get_revisioned_template_name(template_name, revision):
    """Construct name of a template to include it's revision number."""
    return f"{template_name}_rev{revision}"


def get_script_filepath(cookbook_version, template_name, revision, script_file_name):  # noqa: E501
    """Construct the absolute path to a given script.

    :param semantic_version.Version cookbook_version: Remote template cookbook
        version
    :param str template_name:
    :param str revision:
    :param str script_file_name:

    :rtype: str
    """
    scripts_sub_dir = str(cookbook_version)
    template_dir = pathlib.Path.home() / LOCAL_SCRIPTS_DIR / \
        scripts_sub_dir / get_revisioned_template_name(template_name, revision)
    template_dir.mkdir(parents=True, exist_ok=True)

    # pathlib '/' operator does not intuitively resolve Enums with str mixin
    # Ex. ScriptFile.CONTROL_PLANE does not resolve to 'mstr'
    # os.path.join is used instead
    return os.path.join(template_dir, script_file_name)


def get_all_k8s_local_template_definition(client, catalog_name, org=None,
                                          org_name=None,
                                          legacy_mode=False,
                                          ignore_metadata_keys=None,
                                          logger_debug=logger.NULL_LOGGER,
                                          msg_update_callback=utils.NullPrinter()):  # noqa: E501
    """Fetch all CSE k8s templates in a catalog.

    A CSE k8s template is a catalog item that has all the necessary metadata
    stamped onto it. If only partial metadata is present on a catalog item,
    that catalog item will be disqualified from the result.

    :param pyvcloud.vcd.Client client: A sys admin client to be used to
        retrieve metadata off the catalog items.
    :param str catalog_name: Name of the catalog where the template resides.
    :param pyvcloud.vcd.Org org: Org object which hosts the catalog.
    :param str org_name: Name of the org that is hosting the catalog. Can be
        provided in lieu of param org, however param org takes precedence.
    :param bool legacy_mode: True, if CSE is running in legacy mode
    :param List ignore_metadata_keys: List of keys to ignore
    :param logging.Logger logger_debug:
    :param utils.NullPrinter msg_update_callback:

    :return: list of dictionaries containing template data

    :rtype: list of dicts
    """
    if not ignore_metadata_keys:
        ignore_metadata_keys = []
    if not org:
        org = get_org(client, org_name=org_name)
    catalog_item_names = [
        entry['name'] for entry in org.list_catalog_items(catalog_name)]
    templates = []

    # Select the right Key enum based on legacy_mode flag
    localTemplateKey = LocalTemplateKey
    if legacy_mode:
        # if template is loaded in legacy mode, make sure to avoid the keys
        # min_cse_version and max_cse_version
        localTemplateKey = LegacyLocalTemplateKey

    for item_name in catalog_item_names:
        md = org.get_all_metadata_from_catalog_item(catalog_name=catalog_name,
                                                    item_name=item_name)
        metadata_dict = metadata_to_dict(md)

        # if catalog item doesn't have all the required metadata keys,
        # CSE should not recognize it as a template
        expected_metadata_keys = \
            set([entry.value for entry in localTemplateKey])
        missing_metadata_keys = expected_metadata_keys - metadata_dict.keys()
        # ignore keys included in the call
        missing_metadata_keys = missing_metadata_keys - set(ignore_metadata_keys)  # noqa: E501
        num_missing_metadata_keys = len(missing_metadata_keys)
        if num_missing_metadata_keys == len(expected_metadata_keys):
            # This catalog item has no CSE related metadata, so skip it.
            continue
        if num_missing_metadata_keys > 0:
            # This catalog item has partial CSE metadata, so skip it but also
            # log relevant information.
            msg = f"Catalog item '{item_name}' missing " \
                  f"{num_missing_metadata_keys} metadata: " \
                  f"{missing_metadata_keys}"  # noqa: F841
            logger_debug.debug(msg)
            msg_update_callback.info(msg)
            continue

        if not legacy_mode:
            # Do not load the template in non-legacy_mode if
            # min_cse_version and max_cse_version are not present
            # in the metadata_dict
            curr_cse_version = server_utils.get_installed_cse_version()
            valid_cse_versions = semantic_version.SimpleSpec(
                f">={metadata_dict[localTemplateKey.MIN_CSE_VERSION]},"
                f"<={metadata_dict[localTemplateKey.MAX_CSE_VERSION]}")
            if not valid_cse_versions.match(curr_cse_version):
                template_name = \
                    metadata_dict.get(localTemplateKey.NAME, "Unknown")
                template_revision = \
                    metadata_dict.get(localTemplateKey.REVISION, "Unknown")
                msg = f"Template '{template_name}' at " \
                      f"revision '{template_revision}' exists but is " \
                      f"not valid for CSE {curr_cse_version}"
                logger_debug.debug(msg)
                msg_update_callback.info(msg)
                continue

        # non-string metadata is written to the dictionary as a string
        # when 'upgrade_from' metadata is empty, vcd returns it as: "['']"
        # when 'upgrade_from' metadata is not empty, vcd returns it as an array
        # coerce "['']" to the more usable empty array []
        if isinstance(metadata_dict[localTemplateKey.UPGRADE_FROM], str):
            metadata_dict[localTemplateKey.UPGRADE_FROM] = \
                ast.literal_eval(metadata_dict[localTemplateKey.UPGRADE_FROM])
        if metadata_dict[localTemplateKey.UPGRADE_FROM] == ['']:
            metadata_dict[localTemplateKey.UPGRADE_FROM] = []

        templates.append(metadata_dict)

    return templates


def get_valid_k8s_local_template_definition(client, catalog_name, org=None,
                                            org_name=None,
                                            legacy_mode=False,
                                            is_tkg_plus_enabled=False,
                                            logger_debug=logger.NULL_LOGGER,
                                            msg_update_callback=utils.NullPrinter()):  # noqa: E501
    """Get valid templates as per the current server configuration.

    :param pyvcloud.vcd.Client client: A sys admin client to be used to
        retrieve metadata off the catalog items.
    :param str catalog_name: Name of the catalog where the template resides.
    :param pyvcloud.vcd.Org org: Org object which hosts the catalog.
    :param str org_name: Name of the org that is hosting the catalog. Can be
        provided in lieu of param org, however param org takes precedence.
    :param bool legacy_mode: boolean indicating if the server is configured
        in legacy_mode
    :param bool is_tkg_plus_enabled: Boolean indicating if server is configured
        to work with TKG+
    :param logging.Logger logger_debug: logger to log the results or
        exceptions.
    :param utils.NullPrinter msg_update_callback:

    :return: list of dictionaries containing template data
    :rtype: list of dicts
    """
    all_templates = get_all_k8s_local_template_definition(
        client=client,
        catalog_name=catalog_name,
        org=org,
        org_name=org_name,
        legacy_mode=legacy_mode,
        logger_debug=logger_debug,
        msg_update_callback=msg_update_callback)
    for template in all_templates:
        if not legacy_mode and \
                template[LocalTemplateKey.KIND] == \
                shared_constants.ClusterEntityKind.TKG_PLUS.value and \
                not is_tkg_plus_enabled:
            # TKG+ is not enabled on CSE config. Skip the template and
            # log the relevant information.
            msg = "Skipping loading template data for " \
                  f"'{template[LocalTemplateKey.NAME]}' as TKG+ is not enabled"
            logger_debug.debug(msg)
            all_templates.remove(template)
            continue
        msg = f"Found K8 template '{template['name']}' at revision " \
              f"{template['revision']} in catalog '{catalog_name}'"
        msg_update_callback.general(msg)
        logger_debug.info(msg)
    return all_templates


def save_metadata(client, org_name, catalog_name, catalog_item_name,
                  template_data, metadata_key_list=None):
    metadata_key_list = metadata_key_list or []
    org_resource = client.get_org_by_name(org_name=org_name)
    org = Org(client, resource=org_resource)
    org.set_multiple_metadata_on_catalog_item(
        catalog_name=catalog_name,
        item_name=catalog_item_name,
        key_value_dict={k: template_data[k] for k in metadata_key_list},
        domain=MetadataDomain.SYSTEM,
        visibility=MetadataVisibility.PRIVATE)

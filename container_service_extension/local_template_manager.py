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

import container_service_extension.logger as logger
from container_service_extension.pyvcloud_utils import get_org
from container_service_extension.server_constants import LocalTemplateKey

LOCAL_SCRIPTS_DIR = '.cse_scripts'


def get_revisioned_template_name(template_name, revision):
    """Construct name of a template to include it's revision number."""
    return f"{template_name}_rev{revision}"


def get_script_filepath(template_name, revision, script_file_name):
    """Construct the absolute path to a given script.

    :param str template_name:
    :param str revision:
    :param str script_file_name:

    :rtype: str
    """
    template_dir = pathlib.Path.home() / LOCAL_SCRIPTS_DIR / \
        get_revisioned_template_name(template_name, revision)
    template_dir.mkdir(parents=True, exist_ok=True)

    # pathlib '/' operator does not intuitively resolve Enums with str mixin
    # Ex. ScriptFile.CONTROL_PLANE does not resolve to 'mstr'
    # os.path.join is used instead
    return os.path.join(template_dir, script_file_name)


def get_all_k8s_local_template_definition(client, catalog_name, org=None,
                                          org_name=None,
                                          logger_debug=logger.NULL_LOGGER):
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
    :param logging.Logger logger_debug:

    :return: list of dictionaries containing template data

    :rtype: list of dicts
    """
    if not org:
        org = get_org(client, org_name=org_name)
    catalog_item_names = [
        entry['name'] for entry in org.list_catalog_items(catalog_name)]
    templates = []
    for item_name in catalog_item_names:
        md = org.get_all_metadata_from_catalog_item(catalog_name=catalog_name,
                                                    item_name=item_name)
        metadata_dict = metadata_to_dict(md)

        # if catalog item doesn't have all the required metadata keys,
        # CSE should not recognize it as a template
        expected_metadata_keys = \
            set([entry.value for entry in LocalTemplateKey])
        missing_metadata_keys = expected_metadata_keys - metadata_dict.keys()
        num_missing_metadata_keys = len(missing_metadata_keys)
        if num_missing_metadata_keys == len(expected_metadata_keys):
            # This catalog item has no CSE related metadata, so skip it.
            continue
        if num_missing_metadata_keys > 0:
            # This catalog item has partial CSE metadata, so skip it but also
            # log relevant information.
            msg = f"Catalog item '{item_name}' missing " \
                  f"{num_missing_metadata_keys} metadata: " \
                  f"{missing_metadata_keys}" # noqa: F841
            logger_debug.debug(msg)
            continue

        # non-string metadata is written to the dictionary as a string
        # when 'upgrade_from' metadata is empty, vcd returns it as: "['']"
        # when 'upgrade_from' metadata is not empty, vcd returns it as an array
        # coerce "['']" to the more usable empty array []
        if isinstance(metadata_dict[LocalTemplateKey.UPGRADE_FROM], str):
            metadata_dict[LocalTemplateKey.UPGRADE_FROM] = ast.literal_eval(metadata_dict[LocalTemplateKey.UPGRADE_FROM]) # noqa: E501
        if metadata_dict[LocalTemplateKey.UPGRADE_FROM] == ['']:
            metadata_dict[LocalTemplateKey.UPGRADE_FROM] = []

        templates.append(metadata_dict)

    return templates


def save_metadata(client, org_name, catalog_name, catalog_item_name,
                  template_data):
    org_resource = client.get_org_by_name(org_name=org_name)
    org = Org(client, resource=org_resource)
    org.set_multiple_metadata_on_catalog_item(
        catalog_name=catalog_name,
        item_name=catalog_item_name,
        key_value_dict={k: template_data[k] for k in LocalTemplateKey},
        domain=MetadataDomain.SYSTEM,
        visibility=MetadataVisibility.PRIVATE)

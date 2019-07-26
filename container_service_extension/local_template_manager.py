# container-service-extension
# Copyright (c) 2019 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

from pyvcloud.vcd.client import MetadataDomain
from pyvcloud.vcd.client import MetadataVisibility
from pyvcloud.vcd.org import Org
from pyvcloud.vcd.utils import metadata_to_dict

from container_service_extension.pyvcloud_utils import get_org
from container_service_extension.server_constants import \
    LocalTemplateKey


def _dict_to_k8s_local_template_definition(dikt):
    valid_keys = [e.value for e in LocalTemplateKey]
    missing_keys = []
    definition = {}
    for key in valid_keys:
        if key in dikt:
            definition[key] = dikt[key]
        else:
            missing_keys.append(key)

    if len(missing_keys) == 0:
        return definition
    else:
        raise ValueError("Invalid template definition. Missing keys : "
                         f"{missing_keys}")


def get_k8s_local_template_definition(client, catalog_name, catalog_item_name,
                                      org=None, org_name=None):
    """Fetch definition of a template.

    Read metadata on a catalog item and construct a dictionary that defines the
    template. If partial data (which indicates a malformed or non k8s template)
    is retrieved from the metadata, an empty dictionary would be sent back.

    :param pyvcloud.vcd.Client client: A sys admin client to be used to
        retrieve metadata off the catalog item.
    :param str catalog_name: Name of the catalog where the template resides.
    :param str catalog_item_name: Name of the template.
    :param pyvcloud.vcd.Org org: Org object which hosts the catalog.
    :param str org_name: Name of the org that is hosting the catalog. Can be
        provided in lieu param org, however param org takes precedence.

    :return: definition of the template.

    :rtype: dict
    """
    if org is None:
        org = get_org(client, org_name=org_name)
    md = org.get_all_metadata_from_catalog_item(catalog_name=catalog_name,
                                                item_name=catalog_item_name)
    try:
        metadata = metadata_to_dict(md)
        return _dict_to_k8s_local_template_definition(metadata)
    except ValueError:
        return None


def get_all_k8s_local_template_definition(client, catalog_name, org=None,
                                          org_name=None):
    """Fetch definitions of all templates in a catalog.

    :param pyvcloud.vcd.Client client: A sys admin client to be used to
        retrieve metadata off the catalog items.
    :param str catalog_name: Name of the catalog where the template resides.
    :param pyvcloud.vcd.Org org: Org object which hosts the catalog.
    :param str org_name: Name of the org that is hosting the catalog. Can be
        provided in lieu param org, however param org takes precedence.

    :return: definition of the templates.

    :rtype: list of dicts
    """
    if not org:
        org = get_org(client, org_name=org_name)
    catalog_item_names = [
        entry['name'] for entry in org.list_catalog_items(catalog_name)]
    result = []
    for catalog_item_name in catalog_item_names:
        template_definition = get_k8s_local_template_definition(
            client, catalog_name, catalog_item_name, org=org)
        if template_definition:
            result.append(template_definition)

    return result


def save_k8s_local_template_definition_as_metadata(
        client, catalog_name, catalog_item_name, template_definition,
        org_resource=None, org_name=None):
    """Save definitions of a templates in a catalog as metadata on the item.

    :param pyvcloud.vcd.Client client: A sys admin client to be used to
        set metadata on the catalog items.
    :param str catalog_name: Name of the catalog where the template resides.
    :param str catalog_item_name: Name of the template.
    :param dict template_definition:
    :param pyvcloud.vcd.Org org: Org object which hosts the catalog.
    :param str org_name: Name of the org that is hosting the catalog. Can be
        provided in lieu param org, however param org takes precedence.

    :return: an object of type EntityType.TASK XML which represents the
        asynchronous task that is updating the metadata.

    :rtype: lxml.objectify.ObjectifiedElement
    """
    if org_resource is None:
        org_resource = client.get_org_by_name(org_name=org_name)
    org = Org(client, resource=org_resource)

    validated_definition = \
        _dict_to_k8s_local_template_definition(template_definition)

    return org.set_multiple_metadata_on_catalog_item(
        catalog_name=catalog_name,
        item_name=catalog_item_name,
        key_value_dict=validated_definition,
        domain=MetadataDomain.SYSTEM,
        visibility=MetadataVisibility.PRIVATE)

# container-service-extension
# Copyright (c) 2019 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

from pyvcloud.vcd.client import MetadataDomain
from pyvcloud.vcd.client import MetadataVisibility
from pyvcloud.vcd.org import Org
from pyvcloud.vcd.utils import metadata_to_dict

from container_service_extension.pyvcloud_utils import get_org


def _filter_template_metadata(template_name, data):
    filtered_data = {}
    if data.get('admin_password'):
        filtered_data['admin_password'] = data.get('admin_password')
    if data.get('compute_policy'):
        filtered_data['compute_policy'] = data.get('compute_policy')
    if data.get('cpu'):
        filtered_data['cpu'] = data.get('cpu')
    if data.get('deprecated'):
        filtered_data['deprecated'] = data.get('deprecated')
    if data.get('description'):
        filtered_data['description'] = data.get('description')
    if data.get('mem'):
        filtered_data['mem'] = data.get('mem')
    if data.get('name'):
        filtered_data['name'] = data.get('name')
    if data.get('revision'):
        filtered_data['revision'] = data.get('revision')
    # if this is a valid K8 template, add the name of the template to result
    if filtered_data:
        filtered_data['catalog_item_name'] = template_name
    return filtered_data


def get_all_metadata_on_catalog_item(client, catalog_name, catalog_item_name,
                                     org=None, org_name=None):
    if org is None:
        org = get_org(client, org_name=org_name)
    md = org.get_all_metadata_from_catalog_item(
        catalog_name=catalog_name,
        item_name=catalog_item_name)
    data = metadata_to_dict(md)
    return _filter_template_metadata(catalog_item_name, data)


def set_metadata_on_catalog_item(client, catalog_name, catalog_item_name,
                                 data, org_resource=None, org_name=None):
    if org_resource is None:
        org_resource = client.get_org_by_name(org_name=org_name)
    org = Org(client, resource=org_resource)

    filtered_data = _filter_template_metadata(catalog_item_name, data)

    return org.set_multiple_metadata_on_catalog_item(
        catalog_name=catalog_name,
        item_name=catalog_item_name,
        key_value_dict=filtered_data,
        domain=MetadataDomain.SYSTEM,
        visibility=MetadataVisibility.PRIVATE)

# container-service-extension
# Copyright (c) 2021 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

"""Logic to import TKGm template in VCD."""

import re

from pyvcloud.vcd.client import MetadataDomain
from pyvcloud.vcd.client import MetadataVisibility

import container_service_extension.common.utils.core_utils as utils
import container_service_extension.common.utils.pyvcloud_utils as vcd_utils
from container_service_extension.logging.logger import NULL_LOGGER


def parse_tkgm_template_name(ova_file_name):
    # matches TKGm standard OVA name e.g.
    # ubuntu-2004-kube-v1.19.8-vmware.1-tkg.0-18171857641727074969.ova
    # ubuntu-2004-kube-v1.18.16-vmware.1-tkg.0-14744207219736322255.ova
    name_regex = re.compile(r"ubuntu-([\d]+)-kube-v([\d]+[.][\d]+[.][\d]+[-vmware.[\d]*]*)-tkg[.][-|\d]*[.]ova")  # noqa: E501
    m = name_regex.match(ova_file_name)
    os_version = None
    kubernetes_version = None
    if m:
        g = m.groups()
        if len(g) == 2:
            os_version = g[0]
            kubernetes_version = g[1]
    return os_version, kubernetes_version


def upload_tkgm_template(
        client,
        ova_file_path,
        catalog_name,
        catalog_item_name,
        org_name,
        force,
        logger=NULL_LOGGER,
        msg_update_callback=utils.NullPrinter()
):
    """."""
    org = vcd_utils.get_org(client, org_name=org_name)
    if vcd_utils.catalog_item_exists(
            org=org,
            catalog_name=catalog_name,
            catalog_item_name=catalog_item_name
    ):
        if not force:
            msg = f"Catalog item '{catalog_item_name}' already exists " \
                  f"in catalog '{catalog_name}'"
            msg_update_callback.info(msg)
            logger.info(msg)
            return
        else:
            msg = f"Deleting catalog item '{catalog_item_name}' " \
                  f"from catalog '{catalog_name}'"
            msg_update_callback.general(msg)
            logger.info(msg)
            org.delete_catalog_item(catalog_name, catalog_item_name)
            org.reload()

    vcd_utils.upload_ova_to_catalog(
        client=client,
        source_filepath=ova_file_path,
        catalog_name=catalog_name,
        catalog_item_name=catalog_item_name,
        org=org,
        logger=logger,
        msg_update_callback=msg_update_callback
    )


def get_template_property(
        client,
        org_name,
        catalog_name,
        catalog_item_name
):
    org = vcd_utils.get_org(client, org_name=org_name)
    item_resource = org.get_catalog_item(
        name=catalog_name,
        item_name=catalog_item_name
    )
    entity_resource = client.get_resource(
        item_resource.Entity.get('href')
    )

    property_map = {}
    if hasattr(entity_resource, "Children") and hasattr(entity_resource.Children, "Vm"):  # noqa: E501
        vm = entity_resource.Children.Vm
        if hasattr(vm, "{http://schemas.dmtf.org/ovf/envelope/1}ProductSection"):  # noqa: E501
            product_section = getattr(vm, "{http://schemas.dmtf.org/ovf/envelope/1}ProductSection")  # noqa: E501
            for item in product_section.getchildren():
                if item.tag == "{http://schemas.dmtf.org/ovf/envelope/1}Property":  # noqa: E501
                    key = item.get('{http://schemas.dmtf.org/ovf/envelope/1}key')  # noqa: E501
                    value = item.get('{http://schemas.dmtf.org/ovf/envelope/1}value')  # noqa: E501
                    property_map[key] = value
    return property_map


def save_metadata(
        client,
        org_name,
        catalog_name,
        catalog_item_name,
        data,
        keys_to_write=None
):
    keys_to_write = keys_to_write or []
    org = vcd_utils.get_org(client, org_name=org_name)
    org.set_multiple_metadata_on_catalog_item(
        catalog_name=catalog_name,
        item_name=catalog_item_name,
        key_value_dict={k: data.get(k, '') for k in keys_to_write},  # noqa: E501
        domain=MetadataDomain.SYSTEM,
        visibility=MetadataVisibility.PRIVATE
    )

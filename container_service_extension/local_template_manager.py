# container-service-extension
# Copyright (c) 2019 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

import ast

from pyvcloud.vcd.utils import metadata_to_dict

from container_service_extension.pyvcloud_utils import get_org
from container_service_extension.server_constants import \
    LocalTemplateKey


def get_template_k8s_version(template_name):
    try:
        tokens = template_name.split('_')
        if len(tokens) == 3:
            k8s_info = tokens[1].split('-')
            if len(k8s_info) == 2 and k8s_info[0] in ('k8', 'esspks'):
                return k8s_info[1]
    except Exception:
        pass

    return "Unknown"


def get_all_k8s_local_template_definition(client, catalog_name, org=None,
                                          org_name=None):
    """Fetch all templates in a catalog.

    A template is a catalog item that has the LocalTemplateKey.NAME and
    LocalTemplateKey.REVISION metadata keys.

    :param pyvcloud.vcd.Client client: A sys admin client to be used to
        retrieve metadata off the catalog items.
    :param str catalog_name: Name of the catalog where the template resides.
    :param pyvcloud.vcd.Org org: Org object which hosts the catalog.
    :param str org_name: Name of the org that is hosting the catalog. Can be
        provided in lieu param org, however param org takes precedence.

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

        # make sure all pre-2.6 template metadata exists on catalog item
        old_metadata_keys = {
            LocalTemplateKey.CATALOG_ITEM_NAME,
            LocalTemplateKey.COMPUTE_POLICY,
            LocalTemplateKey.CPU,
            LocalTemplateKey.DEPRECATED,
            LocalTemplateKey.DESCRIPTION,
            LocalTemplateKey.MEMORY,
            LocalTemplateKey.NAME,
            LocalTemplateKey.REVISION,
        }
        # if catalog item doesn't have the old metadata keys, CSE should
        # not recognize it as a template
        if not metadata_dict.keys() >= old_metadata_keys:
            continue

        # non-string metadata is written to the dictionary as a string
        # 'upgrade_from' should be converted to an array if it is a string
        if LocalTemplateKey.UPGRADE_FROM in metadata_dict and isinstance(metadata_dict[LocalTemplateKey.UPGRADE_FROM], str): # noqa: E501
            metadata_dict[LocalTemplateKey.UPGRADE_FROM] = ast.literal_eval(metadata_dict[LocalTemplateKey.UPGRADE_FROM]) # noqa: E501

        # if 2.5.1+ template metadata is missing, add them to the dict
        template_name = metadata_dict[LocalTemplateKey.NAME]
        template_revision = str(metadata_dict.get(LocalTemplateKey.REVISION, '0')) # noqa: E501

        k8s_version, docker_version = get_k8s_and_docker_versions(template_name, template_revision=template_revision) # noqa: E501
        tokens = template_name.split('_')
        if LocalTemplateKey.OS not in metadata_dict:
            metadata_dict[LocalTemplateKey.OS] = tokens[0]
        if LocalTemplateKey.DOCKER_VERSION not in metadata_dict:
            metadata_dict[LocalTemplateKey.DOCKER_VERSION] = docker_version
        if LocalTemplateKey.KUBERNETES not in metadata_dict:
            metadata_dict[LocalTemplateKey.KUBERNETES] = 'upstream'
        if LocalTemplateKey.KUBERNETES_VERSION not in metadata_dict:
            metadata_dict[LocalTemplateKey.KUBERNETES_VERSION] = k8s_version
        if LocalTemplateKey.CNI not in metadata_dict:
            metadata_dict[LocalTemplateKey.CNI] = tokens[2].split('-')[0]
        if LocalTemplateKey.CNI_VERSION not in metadata_dict:
            metadata_dict[LocalTemplateKey.CNI_VERSION] = tokens[2].split('-')[1] # noqa: E501
        if LocalTemplateKey.UPGRADE_FROM not in metadata_dict:
            metadata_dict[LocalTemplateKey.UPGRADE_FROM] = []

        # final check that all keys in LocalTemplateKey exist in the template
        # should never fail, but useful to double check dev work
        missing_metadata = set(LocalTemplateKey) - metadata_dict.keys()
        num_missing_metadata = len(missing_metadata)
        if num_missing_metadata > 0:
            raise ValueError(f"Template '{template_name}' missing "
                             f"{num_missing_metadata} metadata: "
                             f"{missing_metadata}")

        templates.append(metadata_dict)

    return templates


def get_k8s_and_docker_versions(template_name, template_revision='0',
                                cse_version=None):
    k8s_version = '0.0.0'
    docker_version = '0.0.0'
    if 'photon' in template_name:
        docker_version = '17.06.0'
        if template_revision == '1':
            docker_version = '18.06.2'
        if '1.8' in template_name:
            k8s_version = '1.8.1'
        elif '1.9' in template_name:
            k8s_version = '1.9.6'
        elif '1.10' in template_name:
            k8s_version = '1.10.11'
        elif '1.12' in template_name:
            k8s_version = '1.12.7'
        elif '1.14' in template_name:
            k8s_version = '1.14.6'
    if 'ubuntu' in template_name:
        docker_version = '18.09.7'
        if '1.9' in template_name:
            docker_version = '17.12.0'
            k8s_version = '1.9.3'
        elif '1.10' in template_name:
            docker_version = '18.03.0'
            k8s_version = '1.10.1'
            if cse_version in ('1.2.5', '1.2.6, 1.2.7'):
                k8s_version = '1.10.11'
            if cse_version in ('1.2.7'):
                docker_version = '18.06.2'
        elif '1.13' in template_name:
            docker_version = '18.06.3'
            k8s_version = '1.13.5'
            if template_revision == '2':
                k8s_version = '1.13.12'
        elif '1.15' in template_name:
            docker_version = '18.09.7'
            k8s_version = '1.15.3'
            if template_revision == '2':
                k8s_version = '1.15.5'

    return k8s_version, docker_version

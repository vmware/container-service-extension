# container-service-extension
# Copyright (c) 2019 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause


import yaml


INSTRUCTIONS_FOR_PKS_CONFIG_FILE = "\
# Config file for PKS enabled CSE Server to be filled by administrators.\n\
# This config file has the following four sections:\n\
#   1. pks_api_servers:\n\
#       a. Each entry in the list represents a PKS api server that is part \n\
#          of the deployment.\n\
#       b. The field 'name' in each entry should be unique. The value of \n\
#          the field has no bearing on the real world PKS api server, it's \n\
#          used to tie in various segments of the config file together.\n\
#       c. The field 'vc' represents the name with which the PKS vCenter \n\
#          is registered in vCD.\n\
#       d. The field 'cpi' needs to be retrieved by executing \n\
#          'bosh cpi-config' on Enterprise PKS set up. \n\
#   2. pks_accounts:\n\
#       a. Each entry in the list represents a PKS account that can be used \n\
#          talk to a certain PKS api server.\n\
#       b. The field 'name' in each entry should be unique. The value of \n\
#          the field has no bearing on the real world PKS accounts, it's \n\
#          used to tie in various segments of the config file together.\n\
#       c. The field 'pks_api_server' is a reference to the PKS api server \n\
#          which owns this account. It's value should be equal to value of \n\
#          the field 'name' of the corresponding PKS api server.\n\
#   3. pvdcs:\n\
#       a. Each entry in the list represents a Provider VDC in vCD that is \n\
#          backed by a cluster of the PKS managed vCenter server.\n\
#       b. The field 'name' in each entry should be the name of the \n\
#          Provider VDC as it appears in vCD.\n\
#       c. The field 'pks_api_server' is a reference to the PKS api server \n\
#          which owns this account. It's value should be equal to value of \n\
#          the field 'name' of the corresponding PKS api server.\n\
#   4. nsxt_servers:\n\
#       a. Each entry in the list represents a NSX-T server that has been \n\
#          alongside a PKS server to manage its networking. CSE needs these \n\
#          details to enforce network isolation of clusters.\n\
#       b. The field 'name' in each entry should be unique. The value of \n\
#          the field has no bearing on the real world NSX-T server, it's \n\
#          used to tie in various segments of the config file together.\n\
#       c. The field 'pks_api_server' is a reference to the PKS api server \n\
#          which owns this account. It's value should be equal to value of \n\
#          the field 'name' of the corresponding PKS api server.\n\
#       d. The field 'distributed_firewall_section_anchor_id' should be \n\
#          populated with id of a Distributed Firewall Section e.g. it can \n\
#          be the id of the section called 'Default Layer3 Section' which \n\
#          PKS creates on installation.\n\
# For more information, please refer to CSE documentation page:\n\
# https://vmware.github.io/container-service-extension/INSTALLATION.html\n"

NOTE_FOR_PKS_KEY_IN_CONFIG_FILE = "\
# Filling out this key for regular CSE set up is optional and should be left\n\
# as is. Only for CSE set up enabled for PKS container provider, this value\n\
# needs to point to a valid PKS config file name.\n"

PKS_CONFIG_NOTE = "\
# [OPTIONAL] PKS CONFIGS\n\
# These configs are required only for customers with PKS enabled CSE.\n\
# Regular CSE users, with no PKS container provider in their system, do not \n\
# need these configs to be filled out in a separate yaml file."

SAMPLE_AMQP_CONFIG = {
    'amqp': {
        'host': 'amqp.vmware.com',
        'port': 5672,
        'prefix': 'vcd',
        'username': 'guest',
        'password': 'guest',
        'exchange': 'cse-ext',
        'routing_key': 'cse',
        'ssl': False,
        'ssl_accept_all': False,
        'vhost': '/'
    }
}

SAMPLE_VCD_CONFIG = {
    'vcd': {
        'host': 'vcd.vmware.com',
        'port': 443,
        'username': 'administrator',
        'password': 'my_secret_password',
        'api_version': '31.0',
        'verify': True,
        'log': True
    }
}

SAMPLE_VCS_CONFIG = {
    'vcs': [
        {
            'name': 'vc1',
            'username': 'cse_user@vsphere.local',
            'password': 'my_secret_password',
            'verify': True
        },
        {
            'name': 'vc2',
            'username': 'cse_user@vsphere.local',
            'password': 'my_secret_password',
            'verify': True
        }
    ]
}

SAMPLE_SERVICE_CONFIG = {
    'service': {
        'listeners': 5,
        'enforce_authorization': False
    }
}

SAMPLE_TEMPLATE_PHOTON_V2 = {
    'name': 'photon-v2',
    'catalog_item': 'photon-custom-hw11-2.0-304b817-k8s',
    'source_ova_name': 'photon-custom-hw11-2.0-304b817.ova',
    'source_ova': 'http://dl.bintray.com/vmware/photon/2.0/GA/ova/photon-custo\
m-hw11-2.0-304b817.ova',
    'sha256_ova': 'cb51e4b6d899c3588f961e73282709a0d054bb421787e140a1d80c24d4f\
d89e1',
    'temp_vapp': 'photon2-temp',
    'cleanup': True,
    'cpu': 2,
    'mem': 2048,
    'admin_password': 'guest_os_admin_password',
    'description': 'PhotonOS v2\nDocker 17.06.0-9\nKubernetes 1.12.7\nweave \
2.3.0'
}

SAMPLE_TEMPLATE_UBUNTU_16_04 = {
    'name': 'ubuntu-16.04',
    'catalog_item': 'ubuntu-16.04-server-cloudimg-amd64-k8s',
    'source_ova_name': 'ubuntu-16.04-server-cloudimg-amd64.ova',
    'source_ova': 'https://cloud-images.ubuntu.com/releases/xenial/release-201\
80418/ubuntu-16.04-server-cloudimg-amd64.ova',
    'sha256_ova': '3c1bec8e2770af5b9b0462e20b7b24633666feedff43c099a6fb1330fcc\
869a9',
    'temp_vapp': 'ubuntu1604-temp',
    'cleanup': True,
    'cpu': 2,
    'mem': 2048,
    'admin_password': 'guest_os_admin_password',
    'description': 'Ubuntu 16.04\nDocker 18.06.3~ce\nKubernetes 1.13.5\nweave\
 2.3.0'
}

SAMPLE_BROKER_CONFIG = {
    'broker': {
        'type': 'default',
        'org': 'myorg',
        'vdc': 'myorgvdc',
        'catalog': 'cse',
        'network': 'mynetwork',
        'ip_allocation_mode': 'pool',
        'storage_profile': '*',
        'remote_template_cookbook_url': 'https://raw.githubusercontent.com/rocknes/container-service-extension/remote_template/template.yaml',  # noqa
        'default_template': SAMPLE_TEMPLATE_PHOTON_V2['name'],
        'templates': [SAMPLE_TEMPLATE_PHOTON_V2, SAMPLE_TEMPLATE_UBUNTU_16_04],
        'cse_msg_dir': '/tmp/cse'
    }
}

PKS_CONFIG_FILE_LOCATION_SECTION_KEY = 'pks_config'
SAMPLE_PKS_CONFIG_FILE_LOCATION = {
    PKS_CONFIG_FILE_LOCATION_SECTION_KEY: None
}

PKS_SERVERS_SECTION_KEY = 'pks_api_servers'
SAMPLE_PKS_SERVERS_SECTION = {
    PKS_SERVERS_SECTION_KEY: [
        {
            'name': 'pks-api-server-1',
            'host': 'pks-api-server-1.pks.local',
            'port': '9021',
            'uaac_port': '8443',
            # 'proxy': 'proxy1.pks.local:80',
            'datacenter': 'pks-s1-dc',
            'clusters': ['pks-s1-az-1', 'pks-s1-az-2', 'pks-s1-az-3'],
            'cpi': 'cpi1',
            'vc': 'vc1',
            'verify': True
        }, {
            'name': 'pks-api-server-2',
            'host': 'pks-api-server-2.pks.local',
            'port': '9021',
            'uaac_port': '8443',
            # 'proxy': 'proxy2.pks.local:80',
            'datacenter': 'pks-s2-dc',
            'clusters': ['pks-s2-az-1', 'pks-s2-az-2', 'pks-s2-az-3'],
            'cpi': 'cpi2',
            'vc': 'vc2',
            'verify': True
        }
    ]
}

PKS_ACCOUNTS_SECTION_KEY = 'pks_accounts'
SAMPLE_PKS_ACCOUNTS_SECTION = {
    PKS_ACCOUNTS_SECTION_KEY: [
        {
            'name': 'Org1ServiceAccount1',
            'pks_api_server': 'pks-api-server-1',
            'secret': 'secret',
            'username': 'org1Admin'
        }, {
            'name': 'Org1ServiceAccount2',
            'pks_api_server': 'pks-api-server-2',
            'secret': 'secret',
            'username': 'org1Admin'
        }, {
            'name': 'Org2ServiceAccount',
            'pks_api_server': 'pks-api-server-2',
            'secret': 'secret',
            'username': 'org2Admin'
        }
    ]
}

PKS_ORGS_SECTION_KEY = 'orgs'
SAMPLE_PKS_ORGS_SECTION = {
    PKS_ORGS_SECTION_KEY: [
        {
            'name': 'Org1',
            'pks_accounts': ['Org1ServiceAccount1', 'Org1ServiceAccount2']
        }, {
            'name': 'Org2',
            'pks_accounts': ['Org2ServiceAccount']
        }
    ]
}

PKS_PVDCS_SECTION_KEY = 'pvdcs'
SAMPLE_PKS_PVDCS_SECTION = {
    PKS_PVDCS_SECTION_KEY: [
        {
            'name': 'pvdc1',
            'pks_api_server': 'pks-api-server-1',
            'cluster': 'pks-s1-az-1',
        }, {
            'name': 'pvdc2',
            'pks_api_server': 'pks-api-server-2',
            'cluster': 'pks-s2-az-1'
        }, {
            'name': 'pvdc3',
            'pks_api_server': 'pks-api-server-1',
            'cluster': 'pks-s1-az-2'
        }
    ]
}

PKS_NSXT_SERVERS_SECTION_KEY = 'nsxt_servers'
SAMPLE_PKS_NSXT_SERVERS_SECTION = {
    PKS_NSXT_SERVERS_SECTION_KEY: [
        {
            'name': 'nsxt-server-1',
            'host': 'nsxt1.domain.local',
            'username': 'admin',
            'password': 'secret',
            'pks_api_server': 'pks-api-server-1',
            # 'proxy': 'proxy1.pks.local:80',
            'nodes_ip_block_ids': ['id1', 'id2'],
            'pods_ip_block_ids': ['id1', 'id2'],
            'distributed_firewall_section_anchor_id': 'id',
            'verify': True
        }, {
            'name': 'nsxt-server-2',
            'host': 'nsxt2.domain.local',
            'username': 'admin',
            'password': 'secret',
            'pks_api_server': 'pks-api-server-2',
            # 'proxy': 'proxy2.pks.local:80',
            'nodes_ip_block_ids': ['id1', 'id2'],
            'pods_ip_block_ids': ['id1', 'id2'],
            'distributed_firewall_section_anchor_id': 'id',
            'verify': True
        }
    ]
}


def generate_sample_config(output=None, pks_output=None):
    """Generate sample configs for cse.

    If config file names are
    provided, configs are dumped into respective files.

    :param str output: name of the config file to dump the CSE configs.
    :param str pks_output: name of the PKS config file to dump the PKS
    configs.

    :return: sample config/ sample config files

    :rtype: dict
    """
    sample_config = yaml.safe_dump(SAMPLE_AMQP_CONFIG,
                                   default_flow_style=False) + '\n'
    sample_config += yaml.safe_dump(SAMPLE_VCD_CONFIG,
                                    default_flow_style=False) + '\n'
    sample_config += yaml.safe_dump(SAMPLE_VCS_CONFIG,
                                    default_flow_style=False) + '\n'
    sample_config += yaml.safe_dump(SAMPLE_SERVICE_CONFIG,
                                    default_flow_style=False) + '\n'
    sample_config += yaml.safe_dump(SAMPLE_BROKER_CONFIG,
                                    default_flow_style=False) + '\n'
    sample_config += NOTE_FOR_PKS_KEY_IN_CONFIG_FILE + '\n'

    if pks_output:
        pks_config_location_dict = {}
        pks_config_location_dict[PKS_CONFIG_FILE_LOCATION_SECTION_KEY] = \
            f"{pks_output}"
        sample_config += yaml.safe_dump(pks_config_location_dict,
                                        default_flow_style=False)
    else:
        sample_config += yaml.safe_dump(SAMPLE_PKS_CONFIG_FILE_LOCATION,
                                        default_flow_style=False)

    sample_pks_config = yaml.safe_dump(
        SAMPLE_PKS_SERVERS_SECTION, default_flow_style=False) + '\n'
    sample_pks_config += yaml.safe_dump(
        SAMPLE_PKS_ACCOUNTS_SECTION, default_flow_style=False) + '\n'
    # Org - PKS account mapping section will be supressed for CSE 2.0 alpha
    # sample_pks_config += yaml.safe_dump(
    #    SAMPLE_PKS_ORGS_SECTION, default_flow_style=False) + '\n'
    sample_pks_config += yaml.safe_dump(
        SAMPLE_PKS_PVDCS_SECTION, default_flow_style=False) + '\n'
    sample_pks_config += yaml.safe_dump(
        SAMPLE_PKS_NSXT_SERVERS_SECTION, default_flow_style=False)

    if output:
        with open(output, 'w') as f:
            f.write(sample_config)
    if pks_output:
        with open(pks_output, 'w') as f:
            f.write(f"{INSTRUCTIONS_FOR_PKS_CONFIG_FILE}\n{sample_pks_config}")

    return sample_config.strip() + '\n\n' + PKS_CONFIG_NOTE + '\n\n' + \
        sample_pks_config.strip()

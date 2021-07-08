# container-service-extension
# Copyright (c) 2019 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

import yaml


INSTRUCTIONS_FOR_PKS_CONFIG_FILE = "\
# Enterprise PKS config file to enable Enterprise PKS functionality on CSE\n\
# Please fill out the following four sections:\n\
#   1. pks_api_servers:\n\
#       a. Each entry in the list represents a Enterprise PKS api server\n\
#          that is part of the deployment.\n\
#       b. The field 'name' in each entry should be unique. The value of\n\
#          the field has no bearing on the real world Enterprise PKS api\n\
#          server, it's used to tie in various segments of the config file\n\
#          together.\n\
#       c. The field 'vc' represents the name with which the Enterprise PKS\n\
#          vCenter is registered in vCD.\n\
#       d. The field 'cpi' needs to be retrieved by executing\n\
#          'bosh cpi-config' on Enterprise PKS set up.\n\
#   2. pks_accounts:\n\
#       a. Each entry in the list represents a Enterprise PKS account that\n\
#          can be used talk to a certain Enterprise PKS api server.\n\
#       b. The field 'name' in each entry should be unique. The value of\n\
#          the field has no bearing on the real world Enterprise PKS\n\
#          accounts, it's used to tie in various segments of the config\n\
#          file together.\n\
#       c. The field 'pks_api_server' is a reference to the Enterprise PKS\n\
#          api server which owns this account. It's value should be equal to\n\
#          value of the field 'name' of the corresponding Enterprise PKS api\n\
#          server.\n\
#   3. pvdcs:\n\
#       a. Each entry in the list represents a Provider VDC in vCD that is\n\
#          backed by a cluster of the Enterprise PKS managed vCenter server.\n\
#       b. The field 'name' in each entry should be the name of the\n\
#          Provider VDC as it appears in vCD.\n\
#       c. The field 'pks_api_server' is a reference to the Enterprise PKS\n\
#          api server which owns this account. Its value should be equal to\n\
#          value of the field 'name' of the corresponding Enterprise PKS api\n\
#          server.\n\
#   4. nsxt_servers:\n\
#       a. Each entry in the list represents a NSX-T server that has been\n\
#          alongside an Enterprise PKS server to manage its networking. CSE\n\
#          needs these details to enforce network isolation of clusters.\n\
#       b. The field 'name' in each entry should be unique. The value of\n\
#          the field has no bearing on the real world NSX-T server, it's\n\
#          used to tie in various segments of the config file together.\n\
#       c. The field 'pks_api_server' is a reference to the Enterprise PKS\n\
#          api server which owns this account. Its value should be equal to\n\
#          value of the field 'name' of the corresponding Enterprise PKS api\n\
#          server.\n\
#       d. The field 'distributed_firewall_section_anchor_id' should be\n\
#          populated with id of a Distributed Firewall Section e.g. it can\n\
#          be the id of the section called 'Default Layer3 Section' which\n\
#          Enterprise PKS creates on installation.\n\
# For more information, please refer to CSE documentation page:\n\
# https://vmware.github.io/container-service-extension/INSTALLATION.html\n"

SAMPLE_AMQP_CONFIG = {
    'amqp': {
        'host': 'amqp.vmware.com',
        'port': 5672,
        'prefix': 'vcd',
        'username': 'guest',
        'password': 'guest',
        'exchange': 'cse-ext',
        'routing_key': 'cse',
        'vhost': '/'
    }
}

SAMPLE_MQTT_CONFIG = {
    'mqtt': {
        'verify_ssl': True
    }
}

SAMPLE_VCD_CONFIG = {
    'vcd': {
        'host': 'vcd.vmware.com',
        'port': 443,
        'username': 'administrator',
        'password': 'my_secret_password',
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
        'processors': 15,
        'enforce_authorization': False,
        'log_wire': False,
        'telemetry': {
            'enable': True
        },
        'legacy_mode': False
    }
}

SAMPLE_BROKER_CONFIG = {
    'broker': {
        'org': 'my_org',
        'vdc': 'my_org_vdc',
        'catalog': 'cse',
        'network': 'my_network',
        'ip_allocation_mode': 'pool',
        'storage_profile': '*',
        'default_template_name': 'my_template',
        'default_template_revision': 0,
        'remote_template_cookbook_url': 'https://raw.githubusercontent.com/vmware/container-service-extension-templates/master/template_v2.yaml',  # noqa: E501
    }
}

TEMPLATE_RULE_NOTE = """# [Optional] Template rule section
# Rules can be defined to override template definitions as defined by remote
# template cookbook.
# Any rule defined in this section can match exactly one template.
# Template name and revision must be provided for the rule to be processed.
# Templates will still have the default attributes that were defined during template creation.
# These newly defined attributes only affect new cluster deployments from templates.
# Template rules can override the following attributes:
# * compute_policy
# * cpu
# * memory

# Example 'template_rules' section:

#template_rules:
#- name: Rule1
#  target:
#    name: photon-v2_k8-1.12_weave-2.3.0
#    revision: 1
#  action:
#    compute_policy: "sample policy"
#    cpu: 4
#    mem: 512
#- name: Rule2
#  target:
#    name: my_template
#    revision: 2
#  action:
#    cpu: 2
#    mem: 1024
"""  # noqa: E501

COMMENTED_AMQP_SECTION = """\
# Only one of the amqp or mqtt sections should be present.

#amqp:
#  exchange: cse-ext
#  host: amqp.vmware.com
#  password: guest
#  port: 5672
#  prefix: vcd
#  routing_key: cse
#  username: guest
#  vhost: /
"""


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
            'clusters': ['vsphere-cluster-1', 'vsphere-cluster-2',
                         'vsphere-cluster-3'],
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
            'clusters': ['vSphereCluster-1', 'vSphereCluster-2',
                         'vSphereCluster-3'],
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
            'cluster': 'vsphere-cluster-1',
        }, {
            'name': 'pvdc2',
            'pks_api_server': 'pks-api-server-2',
            'cluster': 'vsphere-cluster-4'
        }, {
            'name': 'pvdc3',
            'pks_api_server': 'pks-api-server-1',
            'cluster': 'vsphere-cluster-2'
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
            'password': 'my_secret_password',
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
            'password': 'my_secret_password',
            'pks_api_server': 'pks-api-server-2',
            # 'proxy': 'proxy2.pks.local:80',
            'nodes_ip_block_ids': ['id1', 'id2'],
            'pods_ip_block_ids': ['id1', 'id2'],
            'distributed_firewall_section_anchor_id': 'id',
            'verify': True
        }
    ]
}


def generate_sample_config(
        output_file_name: str, generate_pks_config: bool, legacy_mode=False):
    """Generate sample configs for cse.

    If output config file name is provided, config is dumped into the file.

    :param str output_file_name: name of the config file to dump the
        CSE configs.
    :param bool generate_pks_config: Flag to generate sample of PKS specific
        configuration file instead of sample regular CSE configuration file.
    :param bool legacy_mode: if True to configure CSE with whose maximum
    supported api_version < 35. if False to configure CSE with whose maximum
    supported api_version >= 35

    :return: sample config

    :rtype: dict
    """
    if not generate_pks_config:
        # Select message protocol section
        if not legacy_mode:
            sample_config = COMMENTED_AMQP_SECTION + '\n'
            sample_config += yaml.safe_dump(SAMPLE_MQTT_CONFIG) + '\n'
        else:
            sample_config = yaml.safe_dump(SAMPLE_AMQP_CONFIG,
                                           default_flow_style=False) + '\n'

        sample_config += yaml.safe_dump(SAMPLE_VCD_CONFIG,
                                        default_flow_style=False) + '\n'
        sample_config += yaml.safe_dump(SAMPLE_VCS_CONFIG,
                                        default_flow_style=False) + '\n'

        if legacy_mode:
            SAMPLE_SERVICE_CONFIG['service']['legacy_mode'] = True

        sample_config += yaml.safe_dump(SAMPLE_SERVICE_CONFIG,
                                        default_flow_style=False) + '\n'

        if legacy_mode:
            SAMPLE_BROKER_CONFIG['broker']['remote_template_cookbook_url'] = 'https://raw.githubusercontent.com/vmware/container-service-extension-templates/master/template.yaml'  # noqa: E501

        sample_config += yaml.safe_dump(SAMPLE_BROKER_CONFIG,
                                        default_flow_style=False) + '\n'

        if SAMPLE_SERVICE_CONFIG['service']['legacy_mode']:
            sample_config += TEMPLATE_RULE_NOTE + '\n'
    else:
        sample_config = yaml.safe_dump(
            SAMPLE_PKS_SERVERS_SECTION, default_flow_style=False) + '\n'
        sample_config += yaml.safe_dump(
            SAMPLE_PKS_ACCOUNTS_SECTION, default_flow_style=False) + '\n'
        # Org - PKS account mapping section will be suppressed for
        #   CSE 2.0 alpha
        # sample_pks_config += yaml.safe_dump(
        # SAMPLE_PKS_ORGS_SECTION, default_flow_style=False) + '\n'
        sample_config += yaml.safe_dump(
            SAMPLE_PKS_PVDCS_SECTION, default_flow_style=False) + '\n'
        sample_config += yaml.safe_dump(
            SAMPLE_PKS_NSXT_SERVERS_SECTION, default_flow_style=False)
        sample_config = f"{INSTRUCTIONS_FOR_PKS_CONFIG_FILE}\n{sample_config}"

    if output_file_name:
        with open(output_file_name, 'w') as f:
            f.write(sample_config)

    return sample_config.strip()

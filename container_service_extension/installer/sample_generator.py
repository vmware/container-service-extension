# container-service-extension
# Copyright (c) 2019 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause
from typing import Dict

import yaml

from container_service_extension.common.constants.config_constants import \
    COMMENTED_EXTRA_OPTIONS_SECTION, INSTRUCTIONS_FOR_PKS_CONFIG_FILE, \
    SAMPLE_AMQP_CONFIG, SAMPLE_BROKER_CONFIG, SAMPLE_EXTRA_OPTIONS_CONFIG, \
    SAMPLE_MQTT_CONFIG, SAMPLE_PKS_ACCOUNTS_SECTION, \
    SAMPLE_PKS_NSXT_SERVERS_SECTION, SAMPLE_PKS_PVDCS_SECTION, \
    SAMPLE_PKS_SERVERS_SECTION, SAMPLE_SERVICE_CONFIG, SAMPLE_VCD_CONFIG, \
    SAMPLE_VCS_CONFIG, TEMPLATE_RULE_NOTE


def generate_sample_cse_config(legacy_mode: bool = False):
    """."""
    sample_config = {}

    sample_config.update(**SAMPLE_VCD_CONFIG)
    sample_config.update(**SAMPLE_VCS_CONFIG)
    sample_config.update(**SAMPLE_SERVICE_CONFIG)
    sample_config['service']['legacy_mode'] = legacy_mode
    sample_config.update(**SAMPLE_BROKER_CONFIG)
    sample_config.update(**SAMPLE_EXTRA_OPTIONS_CONFIG)

    if legacy_mode:
        sample_config.update(**SAMPLE_AMQP_CONFIG)
        sample_config['broker']['remote_template_cookbook_url'] = 'https://raw.githubusercontent.com/vmware/container-service-extension-templates/master/template.yaml'  # noqa: E501
    else:
        sample_config.update(**SAMPLE_MQTT_CONFIG)

    return sample_config


def generate_sample_config_text(
        sample_config: Dict,
        output_file_name: str,
        generate_pks_config: bool,
        legacy_mode: bool = False
):
    """Generate sample configs for cse.

    If output config file name is provided, config is dumped into the file.

    :param dict sample_config:
    :param str output_file_name: name of the config file to dump the
        CSE configs.
    :param bool generate_pks_config: Flag to generate sample of PKS specific
        configuration file instead of sample regular CSE configuration file.
    :param bool legacy_mode: if True to configure CSE with whose maximum
    supported api_version < 35. if False to configure CSE with whose maximum
    supported api_version >= 35

    :return: sample config

    :rtype: str
    """
    if not generate_pks_config:
        if not legacy_mode:
            message_broker_section = {
                'mqtt': sample_config.get('mqtt', SAMPLE_MQTT_CONFIG['mqtt'])
            }
        else:
            message_broker_section = {
                'amqp': sample_config.get('amqp', SAMPLE_AMQP_CONFIG['amqp'])
            }
        sample_config_text = yaml.safe_dump(message_broker_section, default_flow_style=False) + '\n'  # noqa: E501

        vcd_section = {
            'vcd': sample_config.get('vcd', SAMPLE_VCD_CONFIG['vcd'])
        }
        sample_config_text += yaml.safe_dump(vcd_section, default_flow_style=False) + '\n'  # noqa: E501

        vcs_section = {
            'vcs': sample_config.get('vcs', SAMPLE_VCS_CONFIG['vcs'])
        }
        sample_config_text += yaml.safe_dump(vcs_section, default_flow_style=False) + '\n'  # noqa: E501

        service_section = {
            'service': sample_config.get('service', SAMPLE_SERVICE_CONFIG['service'])  # noqa: E501
        }
        sample_config_text += yaml.safe_dump(service_section, default_flow_style=False) + '\n'  # noqa: E501

        broker_section = {
            'broker': sample_config.get('broker', SAMPLE_BROKER_CONFIG['broker'])  # noqa: E501
        }
        sample_config_text += yaml.safe_dump(broker_section, default_flow_style=False) + '\n'  # noqa: E501

        extra_options_section = {
            'extra_options': sample_config.get('extra_options', SAMPLE_EXTRA_OPTIONS_CONFIG['extra_options'])  # noqa: E501
        }
        sample_config_text += yaml.safe_dump(extra_options_section, default_flow_style=False) + '\n'  # noqa: E501

        if legacy_mode:
            sample_config_text += TEMPLATE_RULE_NOTE + '\n'
        else:
            sample_config_text += COMMENTED_EXTRA_OPTIONS_SECTION + '\n'
    else:
        sample_config_text = yaml.safe_dump(SAMPLE_PKS_SERVERS_SECTION, default_flow_style=False) + '\n'  # noqa: E501
        sample_config_text += yaml.safe_dump(SAMPLE_PKS_ACCOUNTS_SECTION, default_flow_style=False) + '\n'  # noqa: E501
        # Org - PKS account mapping section will be suppressed for
        #   CSE 2.0 alpha
        # sample_pks_config += yaml.safe_dump(
        # SAMPLE_PKS_ORGS_SECTION, default_flow_style=False) + '\n'
        sample_config_text += yaml.safe_dump(SAMPLE_PKS_PVDCS_SECTION, default_flow_style=False) + '\n'  # noqa: E501
        sample_config_text += yaml.safe_dump(SAMPLE_PKS_NSXT_SERVERS_SECTION, default_flow_style=False)  # noqa: E501
        sample_config_text = f"{INSTRUCTIONS_FOR_PKS_CONFIG_FILE}\n{sample_config_text}"  # noqa: E501

    if output_file_name:
        with open(output_file_name, 'w') as f:
            f.write(sample_config_text)

    return sample_config_text.strip()

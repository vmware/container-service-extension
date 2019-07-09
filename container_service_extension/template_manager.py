# container-service-extension
# Copyright (c) 2019 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

import os
from pathlib import Path
from unittest.mock import Mock

import requests
import yaml

from container_service_extension.install_utils import download_file
from container_service_extension.server_constants import ScriptFile
from container_service_extension.utils import get_server_runtime_config


REMOTE_TEMPLATE_COOKBOOK_FILENAME = 'template.yaml'
REMOTE_SCRIPTS_DIR = 'scripts'
LOCAL_SCRIPTS_DIR = '.cse_scripts'


def download_file_into_memory(url):
    """Download a file and store it in memory.

    This method is meant to download really small files (in order of few KBs).
    It shouldn't be abused to download larger file and store them in memory.

    :param str url: url of the file to be downloaded.

    :return: downloaded file's content.

    :rtype: str
    """
    response = requests.get(url)
    if response.status_code == requests.codes.ok:
        return response.text
    else:
        return None


def _get_base_url_from_remote_template_cookbook_url(url):
    """."""
    tokens = url.split('/')
    if tokens[-1] == REMOTE_TEMPLATE_COOKBOOK_FILENAME:
        return '/'.join(tokens[:-1])
    else:
        raise ValueError("Inalid url for template cookbook.")


def _scripts_folder_name(template_name, revision):
    return f"{template_name}_rev{revision}"


def _construct_remote_script_url(
        base_url, template_name, revision, script_file):
    return base_url + \
        f"/{REMOTE_SCRIPTS_DIR}/" \
        f"{_scripts_folder_name(template_name, revision)}/{script_file}"


def _construct_local_script_file_location(
        template_name, revision, script_file):
    home_dir = os.path.expanduser('~')
    cse_scripts_dir = os.path.join(
        home_dir, LOCAL_SCRIPTS_DIR,
        _scripts_folder_name(template_name, revision))
    Path(cse_scripts_dir).mkdir(parents=True, exist_ok=True)
    script_abs_path = os.path.join(cse_scripts_dir, script_file)
    return script_abs_path


def get_remote_template_cookbook_url():
    config = get_server_runtime_config()
    if config['broker']:
        return config['broker'].get('remote_template_cookbook_url')
    return None


def get_remote_template_cookbook():
    url = get_remote_template_cookbook_url()
    template_cookbook_as_str = download_file_into_memory(url)
    return yaml.safe_load(template_cookbook_as_str)


def download_template_scripts(template_name, revision):
    url = get_remote_template_cookbook_url()
    base_url = _get_base_url_from_remote_template_cookbook_url(url)
    for script_file in ScriptFile:
        remote_script_url = \
            _construct_remote_script_url(
                base_url, template_name, revision, script_file)
        local_script_file_location = _construct_local_script_file_location(
            template_name, revision, script_file)
        download_file(url=remote_script_url,
                      filepath=local_script_file_location,
                      quiet=False,
                      force_overwrite=True)


def download_all_template_scripts(remote_template_cookbook):
    for template in remote_template_cookbook['templates']:
        template_name = template['name']
        revision = template['revision']
        download_template_scripts(template_name, revision)


def __test():
    remote_template_cookbook = get_remote_template_cookbook()
    download_all_template_scripts(remote_template_cookbook)


if __name__ == '__main__':
    # mocking a running cse server
    get_server_runtime_config = Mock()  # noqa
    get_server_runtime_config.return_value = {
        'broker': {
            'remote_template_cookbook_url': 'https://raw.githubusercontent.com/rocknes/container-service-extension/remote_template/template.yaml',  # noqa
        }
    }
    __test()

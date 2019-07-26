# container-service-extension
# Copyright (c) 2019 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

import os
from pathlib import Path

import requests
import yaml

from container_service_extension.server_constants import ScriptFile
from container_service_extension.utils import download_file


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


def get_revisioned_template_name(template_name, revision):
    """Construct name of a template to include it's revision number."""
    return f"{template_name}_rev{revision}"


def get_local_script_filepath(template_name, revision, script_file_name):
    """Construct the absolute path to a given script.

    :param str template_name:
    :param str revision:
    :param str script_file_name:
    """
    home_dir = os.path.expanduser('~')
    cse_scripts_dir = os.path.join(
        home_dir, LOCAL_SCRIPTS_DIR,
        get_revisioned_template_name(template_name, revision))
    Path(cse_scripts_dir).mkdir(parents=True, exist_ok=True)
    script_abs_path = os.path.join(cse_scripts_dir, script_file_name)
    return script_abs_path


class RemoteTemplateManager():
    """Manage interaction with remote template cookbook.

    Exposes methods to download template cookbook and associated scripts.
    """

    def __init__(self, remote_template_cookbook_url, logger=None,
                 msg_update_callback=None):
        """.

        :param str remote_template_cookbook_url:
        :param logging.Logger logger: optional logger to log with.
        :param utils.ConsoleMessagePrinter msg_update_callback: Callback
            object that writes messages onto console.
        """
        self.url = remote_template_cookbook_url
        self.logger = logger
        self.msg_update_callback = msg_update_callback
        self.cookbook = None

    def _get_base_url_from_remote_template_cookbook_url(self):
        tokens = self.url.split('/')
        if tokens[-1] == REMOTE_TEMPLATE_COOKBOOK_FILENAME:
            return '/'.join(tokens[:-1])
        else:
            raise ValueError("Inalid url for template cookbook.")

    def _get_remote_script_url(self, template_name, revision,
                               script_file_name):
        """.

        The scripts of all templates are kept relative to templates.yaml,
        under the 'scripts' folder. Scripts of a particular template is kept
        inside a sub-directory of 'scripts' named after the revisioned
        template.

        e.g.
        templates.yaml is kept at <base_url>/templates.yaml
        * Template X at revsion 2 will have it's scripts under
        <base_url>/scripts/X_rev2/...
        * Template Y at revsion 6 will have it's scripts under
        <base_url>/scripts/Y_rev6/...

        :param str template_name:
        :param str revision:
        :param str script_file_name:
        """
        base_url = self._get_base_url_from_remote_template_cookbook_url()
        url = base_url + \
            f"/{REMOTE_SCRIPTS_DIR}" \
            f"/{get_revisioned_template_name(template_name, revision)}" \
            f"/{script_file_name}"
        return url

    def get_remote_template_cookbook(self):
        """Get the remote template cookbook as a dictionary.

        :returns: the contents of the cookbook.

        :rtype: dict
        """
        if self.cookbook:
            if self.logger:
                self.logger.debug("Re-using cached copy of template cookbook.")
        else:
            template_cookbook_as_str = download_file_into_memory(self.url)
            self.cookbook = yaml.safe_load(template_cookbook_as_str)
            if self.logger:
                self.logger.debug("Downloaded remote template cookbook from "
                                  f"{self.url}")
        return self.cookbook

    def download_template_scripts(self, template_name, revision,
                                  force_overwrite=False):
        """Download all scripts of a template to local scripts folder.

        :param str template_name:
        "param str revision:
        :param bool force_overwrite: if True, will download the script even if
            it already exists.
        """
        for script_file in ScriptFile:
            remote_script_url = \
                self._get_remote_script_url(template_name, revision,
                                            script_file)

            local_script_filepath = get_local_script_filepath(
                template_name, revision, script_file)

            download_file(url=remote_script_url,
                          filepath=local_script_filepath,
                          force_overwrite=force_overwrite,
                          logger=self.logger,
                          msg_update_callback=self.msg_update_callback)

    def download_all_template_scripts(self, force_overwrite=False):
        """Download all scripts for all templates mentioned in cookbook.

        :param bool force_overwrite: if True, will download the script even if
            it already exists.
        """
        remote_template_cookbook = self.get_remote_template_cookbook()
        for template in remote_template_cookbook['templates']:
            template_name = template['name']
            revision = template['revision']
            self.download_template_scripts(template_name, revision,
                                           force_overwrite=force_overwrite)

# container-service-extension
# Copyright (c) 2019 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

import os
import stat
from typing import Optional

import requests
import semantic_version
import yaml

from container_service_extension.common.constants.server_constants import RemoteTemplateCookbookVersion  # noqa: E501
from container_service_extension.common.constants.server_constants import ScriptFile  # noqa: E501
from container_service_extension.common.constants.server_constants import TemplateScriptFile  # noqa: E501
from container_service_extension.common.utils.core_utils import download_file
from container_service_extension.common.utils.core_utils import NullPrinter
import container_service_extension.common.utils.server_utils as server_utils
import container_service_extension.installer.templates.local_template_manager as ltm  # noqa: E501
from container_service_extension.logging.logger import NULL_LOGGER


def download_file_into_memory(url):
    """Download a file and store it in memory.

    This method is meant to download really small files (in order of few KBs).
    It shouldn't be abused to download larger file and store them in memory.

    :param str url: url of the file to be downloaded.

    :return: downloaded file's content.

    :rtype: str
    """
    response = requests.get(url, headers={'Cache-Control': 'no-cache'})
    if response.status_code == requests.codes.ok:
        return response.text
    response.raise_for_status()


class RemoteTemplateManager:
    """Manage interaction with remote template cookbook.

    Exposes methods to download template cookbook and associated scripts.
    """

    def __init__(self, remote_template_cookbook_url, legacy_mode: bool = False,
                 cookbook_version=None, logger=NULL_LOGGER,
                 msg_update_callback=NullPrinter()):
        """.

        :param str remote_template_cookbook_url:
        :param bool legacy_mode:
        :param semantic_version.Version cookbook_version: Use this parameter
            to optionally set the value for cookbook_version. This value is
            automatically filled by get_filtered_cookbook() or
            get_unfiltered_cookbook()
        :param logging.Logger logger: logger to log with.
        :param utils.ConsoleMessagePrinter msg_update_callback:
            Callback object.
        """
        self.legacy_mode = legacy_mode
        self.url = remote_template_cookbook_url
        self.logger = logger
        self.msg_update_callback = msg_update_callback
        self.filtered_cookbook = None
        self.unfiltered_cookbook = None
        self.cookbook_version: semantic_version.Version = cookbook_version
        self.scripts_directory_path: Optional[str] = None

    def _get_base_url_from_remote_template_cookbook_url(self) -> str:
        """Get base URL of the cookbook.

        Example: if cookbook url is:
        'https://raw.githubusercontent.com/vmware/container-service-extension-templates/master/template.yaml'
        The base url returned is:
        'https://raw.githubusercontent.com/vmware/container-service-extension-templates/master'

        :rtype: str
        """
        return os.path.dirname(self.url)

    def _get_remote_script_url(self, template_name, revision,
                               script_file_name):
        """.

        The scripts of all templates are kept relative to templates.yaml,
        under the 'scripts' folder. Scripts of a particular template is kept
        inside a sub-directory of 'scripts' named after the revisioned
        template.

        e.g.
        templates.yaml is kept at <base_url>/templates.yaml
        * Template X at revision 2 will have it's scripts under
        <base_url>/scripts/X_rev2/...
        * Template Y at revision 6 will have it's scripts under
        <base_url>/scripts/Y_rev6/...

        :param str template_name:
        :param str revision:
        :param str script_file_name:
        """
        base_url = self._get_base_url_from_remote_template_cookbook_url()
        revisioned_template_name = \
            ltm.get_revisioned_template_name(template_name, revision)
        return base_url + \
            f"/{self.scripts_directory_path}" \
            f"/{revisioned_template_name}" \
            f"/{script_file_name}"

    def _filter_unsupported_templates(self):
        """Remove template descriptors which is not supported."""
        # No need to filter templates if CSE is configured in legacy mode.
        if self.legacy_mode:
            msg = "Skipping filtering templates as CSE is being" \
                  " executed in legacy mode"
            self.filtered_cookbook = self.unfiltered_cookbook
            self.logger.debug(msg)
            self.msg_update_callback.general(msg)
            return
        # Cookbook version 1.0 doesn't have supported version information.
        if self.cookbook_version < \
                RemoteTemplateCookbookVersion.Version2.value:
            msg = "Skipping filtering templates as cookbook version " \
                f"{self.cookbook_version} doesn't have supported " \
                "CSE version information."
            self.logger.debug(msg)
            self.msg_update_callback.general(msg)
            return
        # Fetch current CSE version
        current_cse_version = server_utils.get_installed_cse_version()
        supported_templates = []
        remote_template_key = server_utils.get_template_descriptor_keys(self.cookbook_version)  # noqa: E501
        for template_description in self.unfiltered_cookbook['templates']:
            # only include the template if the current CSE version
            # supports it
            # template is supported if current CSE version is between
            # min_cse_version and max_cse_version of the template
            template_supported_cse_versions = semantic_version.SimpleSpec(
                f">={template_description[remote_template_key.MIN_CSE_VERSION]},"  # noqa: E501
                f"<={template_description[remote_template_key.MAX_CSE_VERSION]}")  # noqa: E501
            msg = f"Template {template_description['name']} revision {template_description['revision']}"  # noqa: E501
            if template_supported_cse_versions.match(current_cse_version):
                msg += " is supported"
                supported_templates.append(template_description)
            else:
                msg += " is not supported"
            msg += f" by CSE {current_cse_version}"
            self.logger.debug(msg)
        self.filtered_cookbook = self.unfiltered_cookbook
        # update templates list with only supported templates
        self.filtered_cookbook['templates'] = supported_templates

        msg = "Successfully filtered unsupported templates."
        self.logger.debug(msg)

    def _validate_remote_template_cookbook(self):
        """Check if the remote template cookbook supplied is valid.

        If CSE is configured in legacy mode, template descriptors in the
        remote template cookbook are not expected to have min_cse_version and
        max_cse_version.

        If CSE is configured in non-legacy mode, template descriptors in the
        remote template cookbook should have min_cse_version and
        max_cse_version.
        """
        # if there are no templates in the cookbook, the remote template
        # cookbook is invalid
        if 'templates' not in self.unfiltered_cookbook:
            msg = "No 'templates' found."
            self.logger.error(msg)
            self.msg_update_callback.error(msg)
            raise ValueError(msg)

        template_descriptor_keys = server_utils.get_template_descriptor_keys(self.cookbook_version)  # noqa: E501
        key_set_expected = set([k.value for k in template_descriptor_keys])

        # Validate template yaml contents
        for template_descriptor in self.unfiltered_cookbook.get('templates', []):  # noqa: E501
            existing_template_descriptor_keys = set(template_descriptor.keys())
            key_difference = key_set_expected - existing_template_descriptor_keys  # noqa: E501
            if len(key_difference) > 0:
                msg = f'Remote template cookbook is missing the following keys: {list(key_difference)}'  # noqa: E501
                self.logger.error(msg)
                self.msg_update_callback.error(msg)
                raise ValueError(msg)

        msg = f"Template cookbook {self.url} is valid"
        self.logger.debug(msg)

    def _verify_cookbook_compatibility(self):
        """Verify if the template yaml is compatible with the server config."""
        is_cookbook_compatible = True
        incompatible_template_cookbook_msg = \
            f"Template cookbook version {self.cookbook_version} is " \
            f"incompatible with CSE running in "
        if self.legacy_mode and \
                self.cookbook_version > RemoteTemplateCookbookVersion.Version1.value:  # noqa: E501
            incompatible_template_cookbook_msg += "legacy mode"
            is_cookbook_compatible = False
        if not self.legacy_mode and \
                self.cookbook_version < RemoteTemplateCookbookVersion.Version2.value:  # noqa: E501
            incompatible_template_cookbook_msg += "non-legacy mode"
            is_cookbook_compatible = False

        if not is_cookbook_compatible:
            self.logger.error(incompatible_template_cookbook_msg)
            self.msg_update_callback.error(incompatible_template_cookbook_msg)
            raise Exception(incompatible_template_cookbook_msg)

    def get_filtered_remote_template_cookbook(self):
        """Get the remote template cookbook as a dictionary.

        Loads both filtered and unfiltered cookbooks into memory

        :returns: the contents of the cookbook.

        :rtype: dict
        """
        if self.filtered_cookbook:
            msg = "Re-using cached copy of filtered template cookbook."
            self.logger.debug(msg)
            self.msg_update_callback.general(msg)
        else:
            self.get_unfiltered_remote_template_cookbook()
            self._filter_unsupported_templates()
        return self.filtered_cookbook

    def get_unfiltered_remote_template_cookbook(self):
        """Get the unvalidated remote template cookbook as a dictionary.

        The unfiltered remote template cookbook will contain both supported
        and unsupported CSE template descriptors

        Handles validating if the template cookbook contains all required keys
        in each template descriptor.

        :returns: the contents of the cookbook

        :rtype: dict
        """
        if self.unfiltered_cookbook:
            msg = "Re-using cached copy of unfiltered template cookbook."
            self.logger.debug(msg)
            self.msg_update_callback(msg)
        else:
            template_cookbook_as_str = download_file_into_memory(self.url)
            self.unfiltered_cookbook = yaml.safe_load(template_cookbook_as_str)
            msg = f"Downloaded remote template cookbook from {self.url}"
            self.logger.debug(msg)
            self.msg_update_callback.general(msg)

            # set cookbook version from the key 'version' in the template
            # cookbook.
            # Since 1.0.0 version may not have the key 'version', if the key
            # 'version' is not present, set it to '1.0.0'
            self.cookbook_version = \
                semantic_version.Version(self.unfiltered_cookbook.get('version', '1.0.0'))  # noqa: E501
            msg = f"Template cookbook version: {self.cookbook_version}"
            self.logger.debug(msg)

            # set scripts directory path from the key 'scripts_directory' in
            # the template cookbook.
            # Since the key 'scripts_directory' may not be present as part of
            # '1.0.0' cookbook, set the value to 'scripts/' if the key is not
            # present
            self.scripts_directory_path = \
                self.unfiltered_cookbook.get('scripts_directory', 'scripts')

            self._verify_cookbook_compatibility()
            self._validate_remote_template_cookbook()
        return self.unfiltered_cookbook

    def download_template_scripts(self, template_name, revision,
                                  force_overwrite=False):
        """Download all scripts of a template to local scripts folder.

        :param str template_name:
        :param str revision:
        :param bool force_overwrite: if True, will download the script even if
            it already exists.
        """
        if not self.cookbook_version:
            raise ValueError('Invalid value for cookbook_version')
        # Multiple code paths enter into this. Hence all scripts are
        # downloaded. When vcdbroker.py id deprecated, the scripts should
        # loop through TemplateScriptFile to download scripts.
        scripts_to_download = TemplateScriptFile
        if self.legacy_mode:
            # if server configuration is indicating legacy_mode,
            # download cluster-scripts from template repository.
            scripts_to_download = ScriptFile
        for script_file in scripts_to_download:
            remote_script_url = \
                self._get_remote_script_url(
                    template_name, revision,
                    script_file)

            local_script_filepath = ltm.get_script_filepath(
                self.cookbook_version, template_name, revision, script_file)
            download_file(url=remote_script_url,
                          filepath=local_script_filepath,
                          force_overwrite=force_overwrite,
                          logger=self.logger,
                          msg_update_callback=self.msg_update_callback)

            # Set Read,Write permission only for the owner
            if os.name != 'nt':
                os.chmod(local_script_filepath, stat.S_IRUSR | stat.S_IWUSR)

    def download_all_template_scripts(self, force_overwrite=False):
        """Download all scripts for all templates mentioned in cookbook.

        :param bool force_overwrite: if True, will download the script even if
            it already exists.
        """
        self.get_filtered_remote_template_cookbook()
        for template in self.filtered_cookbook['templates']:
            template_name = template['name']
            revision = template['revision']
            self.download_template_scripts(template_name, revision,
                                           force_overwrite=force_overwrite)

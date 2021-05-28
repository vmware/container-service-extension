# container-service-extension
# Copyright (c) 2019 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

import os
import stat

import requests
import semantic_version
import yaml

from container_service_extension.common.constants.server_constants import RemoteTemplateKey # noqa: E501
from container_service_extension.common.constants.server_constants import ScriptFile  # noqa: E501
from container_service_extension.common.constants.server_constants import TemplateScriptFile  # noqa: E501
from container_service_extension.common.utils.core_utils import download_file
from container_service_extension.common.utils.core_utils import NullPrinter
import container_service_extension.common.utils.server_utils as server_utils
import container_service_extension.installer.templates.local_template_manager as ltm  # noqa: E501
from container_service_extension.logging.logger import NULL_LOGGER

REMOTE_TEMPLATE_COOKBOOK_V2_FILENAME = 'template_v2.yaml'
REMOTE_TEMPLATE_COOKBOOK_FILENAME = 'template.yaml'
REMOTE_SCRIPTS_V2_DIR = 'scripts_v2'
REMOTE_SCRIPTS_DIR = 'scripts'


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


class RemoteTemplateManager():
    """Manage interaction with remote template cookbook.

    Exposes methods to download template cookbook and associated scripts.
    """

    def __init__(self, remote_template_cookbook_url, legacy_mode: bool = False,
                 logger=NULL_LOGGER, msg_update_callback=NullPrinter()):
        """.

        :param str remote_template_cookbook_url:
        :param bool legacy_mode:
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
        self.cookbook_version = None

    def _get_base_url_from_remote_template_cookbook_url(self):
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
        * Template X at revsion 2 will have it's scripts under
        <base_url>/scripts/X_rev2/...
        * Template Y at revsion 6 will have it's scripts under
        <base_url>/scripts/Y_rev6/...

        :param str template_name:
        :param str revision:
        :param str script_file_name:
        """
        base_url = self._get_base_url_from_remote_template_cookbook_url()
        revisioned_template_name = \
            ltm.get_revisioned_template_name(template_name, revision)
        if self.legacy_mode:
            return base_url + \
                f"/{REMOTE_SCRIPTS_DIR}" \
                f"/{revisioned_template_name}" \
                f"/{script_file_name}"
        return base_url + \
            f"/{REMOTE_SCRIPTS_V2_DIR}" \
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
        # Fetch current CSE version
        current_cse_version = server_utils.get_installed_cse_version()
        supported_templates = []
        for template_description in self.unfiltered_cookbook['templates']:
            # only include the template if the current CSE version
            # supports it
            # template is supported if current CSE version is between
            # min_cse_version and max_cse_version of the template
            template_supported_cse_versions = semantic_version.SimpleSpec(
                f">={template_description[RemoteTemplateKey.MIN_CSE_VERSION]},"
                f"<={template_description[RemoteTemplateKey.MAX_CSE_VERSION]}")
            msg = f"Template {template_description['name']}"
            if template_supported_cse_versions.match(current_cse_version):
                msg += " is supported"
                supported_templates.append(template_description)
            else:
                msg += " is not supported"
            msg += f" by CSE {current_cse_version}"
            self.logger.debug(msg)
            self.msg_update_callback.general(msg)
        self.filtered_cookbook = {
            'templates': supported_templates
        }
        msg = "Successfully filtered unsupported templates."
        self.logger.debug(msg)
        self.msg_update_callback.general(msg)

    def _validate_remote_template_cookbook(self):
        """Check if the remote template cookbook supplied is valid.

        If CSE is configured in legacy mode, template descriptors in the
        remote template cookbook are not expected to have min_cse_version and
        max_cse_version.

        If CSE is configured in non-legacy mode, template descriptors in the
        remote template cookbook should have min_cse_version and
        max_cse_version.
        """
        invalid_template_cookbook_msg = f"Invalid template cookbook ({self.url}): "  # noqa: E501
        is_cookbook_invalid = False

        # if there are no templates in the cookbook, the remote template
        # cookbook is invalid
        if 'templates' not in self.unfiltered_cookbook:
            msg = "No 'templates' found."
            is_cookbook_invalid = True

        # Validate template yaml contents
        for template_descriptor in self.unfiltered_cookbook.get('templates', []):  # noqa: E501
            if self.cookbook_version == '2.0' and (RemoteTemplateKey.MIN_CSE_VERSION not in template_descriptor or RemoteTemplateKey.MAX_CSE_VERSION not in template_descriptor):
                # version 2.0 template cookbook should contain min_cse_version
                # and max_cse_version keys.
                is_min_max_key_present = \
                    RemoteTemplateKey.MIN_CSE_VERSION in template_descriptor and \
                    RemoteTemplateKey.MAX_CSE_VERSION in template_descriptor
                if is_min_max_key_present:
                    # min_cse_version and max_cse_version keys are not supported
                    # in the template descriptor if running in legacy_mode
                    invalid_template_cookbook_msg += \
                        "min_cse_version and max_cse_version keys are " \
                        "not supported in the template descriptor " \
                        "if running in legacy_mode."
                    is_cookbook_invalid = True
                    break
            elif not is_min_max_key_present and not self.legacy_mode:
                # min_cse_version and max_cse_version keys are required in the
                # template descriptor if not running in legacy_mode
                invalid_template_cookbook_msg += \
                    "min_cse_version and max_cse_version keys are required " \
                    "in the template descriptor if not running in legacy_mode."
                is_cookbook_invalid = True
                break

        # raise Error if cookbook supplied is invalid
        if is_cookbook_invalid:
            self.logger.error(invalid_template_cookbook_msg)
            self.msg_update_callback.error(invalid_template_cookbook_msg)
            raise ValueError(invalid_template_cookbook_msg)

        msg = f"Template cookbook {self.url} is valid"
        self.logger.debug(msg)
        self.msg_update_callback.general(msg)

    def _verify_cookbook_compatibility(self):
        """Verifies if the template yaml is compatible with the CSE server."""
        if (self.legacy_mode and self.cookbook_version != '1.0') or \
                (not self.legacy_mode and self.cookbook_version != '2.0'):
            incompatible_template_cookbook_msg = \
                f"Template cookbook version {self.cookbook_version} is " \
                f"incompatible with CSE executing in legacy_mode: {self.legacy_mode}"  # noqa: E501
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

            # get template cookbook version. If version string is not present,
            # set the version string to 1.0
            self.cookbook_version = self.unfiltered_cookbook.get('version', '1.0')  # noqa: E501
            msg = f"template cookbook version: {self.cookbook_version}"
            self.logger.debug(msg)
            self.msg_update_callback.general(msg)

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
        # Multiple codepaths enter into this. Hence all scripts are downloaded.
        # When vcdbroker.py id deprecated, the scripts should loop through
        # TemplateScriptFile to download scripts.
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
                template_name, revision, script_file)
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
        :param bool legacy_mode: If true, only template scripts will be
            downloaded.
        """
        self.get_filtered_remote_template_cookbook()
        for template in self.filtered_cookbook['templates']:
            template_name = template['name']
            revision = template['revision']
            self.download_template_scripts(template_name, revision,
                                           force_overwrite=force_overwrite)

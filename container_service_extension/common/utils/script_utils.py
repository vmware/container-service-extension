# container-service-extension
# Copyright (c) 2021 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause
import importlib
import importlib.resources as pkg_resources

from container_service_extension.common.constants.server_constants \
    import ClusterScriptFile


def get_package_file_contents(package_path: str, filename: str) -> str:
    """Get file content from a package.

    :param str package_path: path to package relative to cse package
    :param str filename: name of file to be read
    """
    out_module = importlib.import_module(package_path)
    with pkg_resources.open_text(out_module, filename) as out_file:
        out = out_file.read()
    return out


def get_cluster_script_file_contents(filename: str, version: str) -> str:
    """Get content of file in the cluster_scripts folder under an RDE version.

    :param str filename: name of file, not a path
    :param str version: version of RDE, must exist in `ClusterScriptFile`
    """
    return get_package_file_contents(
        f'{ClusterScriptFile.SCRIPTS_DIR}.{version}', filename)

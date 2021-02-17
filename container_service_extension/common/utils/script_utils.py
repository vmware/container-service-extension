import importlib
import importlib.resources as pkg_resources

from container_service_extension.common.constants.server_constants import K8SScriptFile  # noqa: E501


def get_package_file_contents(parent: str, filename: str) -> str:
    out_module = importlib.import_module(parent)
    out = ""
    with pkg_resources.open_text(out_module, filename) as out_file:
        out = out_file.read()
    return out


def get_k8s_package_file_contents(filename: str) -> str:
    return get_package_file_contents(f'{K8SScriptFile.SCRIPTS_DIR}', filename)

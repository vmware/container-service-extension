# flake8: noqa

import argparse, json, os, requests, sys, time
from pathlib import Path

class PluginManager:
    def __init__(self):
        connectionParams = json.load(open('manage_plugin.json', 'r'))
        self.vcdUrlBase = connectionParams['vcdUrlBase']
        self.username = connectionParams['username']
        self.org = connectionParams['org']
        self.password = connectionParams['password']

        self._connectionParams = json.load(open('manage_plugin.json', 'r'))
        self._session = requests.Session()
        self._session.verify = False
        self._session.headers={'Accept': 'application/*+json;version=30.0'}
        self._login()

    def register(self, pluginDir):
        manifest = json.load(open(os.path.join(pluginDir,'.','manifest.json'), 'r'))
        registerRequest = json.dumps({
            'pluginName': manifest['name'],
            'vendor': manifest['vendor'],
            'description': manifest['description'],
            'version': manifest['version'],
            'license': manifest['license'],
            'link': manifest['link'],
            'tenant_scoped': "tenant" in manifest['scope'],
            'provider_scoped': "service-provider" in manifest['scope'],
            'enabled': True
        })
        response = self._session.post('{}/cloudapi/extensions/ui'.format(self.vcdUrlBase), data=registerRequest)
        pluginId = response.json()['id']
        print('Registered plugin:')
        print(json.dumps(response.json(), indent=4))

        transferRequest = json.dumps({
            "fileName": 'container-ui-plugin.zip',
            "size": os.stat(os.path.join(pluginDir,'.','container-ui-plugin.zip')).st_size
        })
        response = self._session.post('{}/cloudapi/extensions/ui/{}/plugin'.format(self.vcdUrlBase, pluginId), transferRequest)
        transferUrl = response.headers["Link"].split('>')[0][1:]
        print('Obtained transfer link for plugin upload: {}'.format(transferUrl))
        response = self._session.put(transferUrl, data=open(os.path.join(pluginDir,'.','container-ui-plugin.zip'), 'rb'))
        response.raise_for_status()

        print('Waiting for plugin to become available...')
        time.sleep(3)
        response = self._session.get('{}/cloudapi/extensions/ui/{}'.format(self.vcdUrlBase, pluginId), data=registerRequest)
        print('Plugin status: {}'.format(response.json()['plugin_status']))
        return

    def list(self):
        response = self._session.get('{}/cloudapi/extensions/ui'.format(self.vcdUrlBase))
        print('Currently registered plugins:')
        for plugin in response.json():
            print('- {} by {}\n    Version: {}\n    ID: {}'.format(plugin['pluginName'], plugin['vendor'], plugin['version'], plugin['id']))

        return

    def unregister(self, id):
        response = self._session.delete('{}/cloudapi/extensions/ui/{}'.format(self.vcdUrlBase, id))
        response.raise_for_status()
        print('Removed plugin with id of {}'.format(id))
        return

    def _login(self):
        print('Logging into {} with user {}@{}'.format(self.vcdUrlBase, self.username, self.org))
        response = self._session.post('{}/api/sessions'.format(self.vcdUrlBase),
            auth=('{}@{}'.format(self.username, self.org), self.password),
            json={})
        response.raise_for_status()
        self._session.headers.update({'x-vcloud-authorization': response.headers['x-vcloud-authorization']})
        self._session.headers.update({'Accept': 'application/json'})
        self._session.headers.update({'Content-Type': 'application/json'})
        return

class DirType:
    def __call__(self, value):
        if not os.path.exists(value):
            raise argparse.ArgumentTypeError('Path <{}> does not exist'.format(os.path.abspath(value)))
        if not os.path.isdir(value):
            raise argparse.ArgumentTypeError('<{}> is not a directory'.format(os.path.abspath(value)))
        if not os.path.isdir(os.path.join(value, '.')):
            raise argparse.ArgumentTypeError('<dist> directory not found in <{}>. Ensure plugin is built before registering'.format(os.path.abspath(value)))

        return value

def main():
    args = processCommandLine()

    if not Path('manage_plugin.json').exists():
        print('manage_plugin.json configuration not found, exiting')
        sys.exit(1)

    try:
        pluginManager = PluginManager();
    except KeyError as err:
        print('Missing configuration parameter', err)
        sys.exit(1)
    except requests.exceptions.ConnectionError as err:
        print('Couldn''t connect to vCloud Director instance', err.request.url)
        sys.exit(1)
    except requests.exceptions.HTTPError as err:
        print('Invalid credentials specified for', err.request.url)
        sys.exit(1)

    args.func(args, pluginManager)


def listPlugins(args, pluginManager):
    pluginManager.list()

def unregisterPlugin(args, pluginManager):
    pluginManager.unregister(args.id)

def registerPlugin(args, pluginManager):
    pluginManager.register(args.pluginDir)

def processCommandLine():
    parser = argparse.ArgumentParser(description='Manage plugins for a vCloud Director instance')
    subparsers = parser.add_subparsers(dest='command')
    registerParser = subparsers.add_parser('register', help='Registers a plugin')
    registerParser.add_argument('pluginDir', type=DirType(), default='.', help='root directory of a plugin', nargs='?')
    registerParser.set_defaults(func=registerPlugin)
    listParser = subparsers.add_parser('list', help='Lists all registered plugins')
    listParser.set_defaults(func=listPlugins)
    unregisterParser = subparsers.add_parser('unregister', help='Removes a plugin registration')
    unregisterParser.add_argument('id', help='vCD identifier of plugin to remove')
    unregisterParser.set_defaults(func=unregisterPlugin)

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(1)

    return args

main()

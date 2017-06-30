#!/usr/bin/env python

# container-service-extension
# Copyright (c) 2017 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

import base64, json, sys, logging, thread, time, os, traceback
import pkg_resources

def print_help():
    print('Container Service Extension for vCloud Director, version %s'
        % pkg_resources.require("cse-vcd")[0].version)
    print('Usage:')
    print('  cse version')
    print('  cse config.yml')
    sys.exit(0)

def signal_handler(signal, frame):
    print('\nCrtl+C detected')
    sys.exit(0)

def main():
    global config
    if len(sys.argv)>0:
        if len(sys.argv)>1:
            if sys.argv[1] == 'version':
                version = pkg_resources.require("cse-vcd")[0].version
                print(version)
                sys.exit(0)
        else:
            print_help()

if __name__ == '__main__':
    main()

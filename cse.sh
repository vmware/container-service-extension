#!/usr/bin/env bash

USER_DIR=/home/vmware
PYTHONPATH=$USER_DIR/.local/lib/python3.6/site-packages
$USER_DIR/.local/bin/cse run $USER_DIR/config.yaml
#$USER_DIR/.local/bin/cse run $USER_DIR/config.yaml --pks-config $USER_DIR/pks.yaml

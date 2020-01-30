#!/usr/bin/env bash

### recommended to use a virtual environment
# CSE_VENV_PATH=/root/cse-venv
# source $CSE_VENV_PATH/bin/activate

### CSE config file should be encrypted for security (using `cse encrypt` command)
### Encryption password should be stored in the environment variable `CSE_CONFIG_PASSWORD`
### Environment variable can be declared 2 ways:
### (1) Plaintext in this script
# export CSE_CONFIG_PASSWORD=mypassword
### (2) Create a file to store the environment variable. The file should contain the line: `CSE_CONFIG_PASSWORD=mypassword`
### Add `EnvironmentFile=/path/to/file` under `[Service]` in `cse.service`
### Note: If `EnvironmentFile=/path/to/file` exists under `[Service]` in `cse.service` but the file does not exist, CSE will fail to start

### Edit this with your CSE config file path
CSE_CONFIG_PATH=/root/cse-config.yaml
### To use a plaintext CSE config file, add `-s` to the `cse run` command
cse run $CSE_CONFIG_PATH

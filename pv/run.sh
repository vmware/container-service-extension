#!/bin/bash

export HOST=`hostname`
export CSE_MSG_DIR=/tmp/cse
$GOPATH/src/github.com/vmware/container-service-extension/pv/pv

#!/bin/bash

mkdir -p $GOPATH/src/github.com/vmware/container-service-extension/pv
cp glide.* vcd-provider.go $GOPATH/src/github.com/vmware/container-service-extension/pv
cd $GOPATH/src/github.com/vmware/container-service-extension/pv
glide install --strip-vendor
go build

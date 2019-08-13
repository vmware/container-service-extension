# container-service-extension
# Copyright (c) 2019 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

# This makefile may be run by the VMware build system, which defines the
# following variables:
#
#   BUILD_NUMBER:    8+ digit build number
#   PRODUCT_BUILD_NUMBER:   Unique semantic version
#   CHANGE_NUMBER:   SHA of the git changeset
#   BRANCH_NAME:     the git branch name
#   OFFICIALKEY:     will be "1" for offical builds
#

# Build target for go-build and default target
.PHONY: container-service-extension
container-service-extension: build

###
# Version support
#

VERSION_FILE = container_service_extension/version.py

.PHONY: version
version:
	echo "__version__ = {" >${VERSION_FILE}
	echo "'product': 'CSE'," >>${VERSION_FILE}
	echo "'description': 'Container Service Extension for VMware vCloud Director'," >>${VERSION_FILE}
	echo "'version': '${LONG_VERSION}'," >>${VERSION_FILE}
	echo "'build': '${BUILD_NUMBER}'" >>${VERSION_FILE}
	echo "}" >>${VERSION_FILE}

PRODUCT_BUILD_NUMBER ?= ${USER}
OFFICIALKEY ?= 0

ifeq ($(origin FOO), undefined)
  BUILD_NUMBER := $(shell date +'%Y%m%d%H%M%S')
endif

ifeq ($(OFFICIALKEY),1)
  LONG_VERSION=$(PRODUCT_BUILD_NUMBER)
else
  LONG_VERSION=$(PRODUCT_BUILD_NUMBER).$(BUILD_NUMBER)
endif

###
# Docker support
#
# Build a docker image, and tag it for the VMware staging server
#

SRC_FILES = Dockerfile \
		requirements.txt \
		cse.sh \
		container_service_extension/*.py \
		scripts/*

.PHONY: build
build: clean version $(SRC_FILES)
	docker build \
		-t vcd-docker.build-artifactory.eng.vmware.com/container-service-extension:${PRODUCT_BUILD_NUMBER}-${BUILD_NUMBER} .

.PHONY: docker-run
docker-run: build
	docker run \
		 -t vcd-docker.build-artifactory.eng.vmware.com/container-service-extension:${PRODUCT_BUILD_NUMBER}-${BUILD_NUMBER} \
		 version

###
# Code style
#
# Use artificial targets to let make do some dependency
# analysis and speed up rebuilds
#

.PHONY: check
check: .server-check-style .client-check-style .tests-check-style

.server-check-style: container_service_extension/*.py
	yapf -i $+
	flake8 $+
	touch $@

.client-check-style: container_service_extension/client/*.py
	yapf -i $+
	flake8 $+
	touch $@

.tests-check-style: tests/*.py
	yapf -i $+
	flake8 $+
	touch $@

###
# Helpful Python project commands
#

.PHONY: clean
clean: clean-pyc clean-build

.PHONY: clean-pyc
clean-pyc:
	find . -name '*.pyc' -delete
	find . -name '*.log' -delete

.PHONY: clean-build
clean-build:
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info

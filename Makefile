# container-service-extension
# Copyright (c) 2019 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

# This makefile may be run by the VMware build system, which defines the
# following variables:
#
#   BUILD_NUMBER:    8+ digit build number
#   PRODUCT_BUILD_NUMBER:   Unique semantic version
#   CHANGE_NUMBER:   SHA of the git changeset
#   BRANCH_NAME:     git branch name
#   BRANCH_NAME:     the current branch
#   OFFICIALKEY:     will be "1" for offical builds
#

# Build target for go-build and default targer
.PHONY: container-service-extension
container-service-extension: build

###
# Version support
#

.PHONY: version
version: container_service_extension/version.py

PRODUCT_BUILD_NUMBER ?= 1.2.x
BUILD_NUMBER ?= ${USER}-latest
OFFICIALKEY ?= 0

ifeq ($(OFFICIALKEY),1)
  LONG_VERSION=$(PRODUCT_BUILD_NUMBER)
else
  LONG_VERSION=$(PRODUCT_BUILD_NUMBER).$(BUILD_NUMBER)
endif

container_service_extension/version.py :
	echo "__version__ = {" >>$@
	echo "'product': 'CSE'," >>$@
	echo "'description': 'Container Service Extension for VMware vCloud Director'," >>$@
	echo "'version': '${LONG_VERSION}'," >>$@
	echo "'build': '${BUILD_NUMBER}'" >>$@
	echo "}" >>$@

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
		-t vcd-docker.build-artifactory.eng.vmware.com/container-service-extension:${BUILD_NUMBER} .

.PHONY: docker-run
docker-run: build
	docker run \
		 -t vcd-docker.build-artifactory.eng.vmware.com/container-service-extension:${BUILD_NUMBER} \
		 version

###
# Code style
#
# Use artificial targets to let make do some dependency
# analysis and speed up rebuilds
#

.PHONY: check
check: .server-checkstyle .client-checkstyle .tests-checkstyle

.server-checkstyle: container_service_extension/*.py
	yapf -i $+
	flake8 $+
	touch $@

.client-checkstyle: container_service_extension/client/*.py
	yapf -i $+
	flake8 $+
	touch $@

.tests-checkstyle: tests/*.py
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

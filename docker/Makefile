# container-service-extension
# Copyright (c) 2019 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause

run: build
	docker run -t \
		container-service-extension version
# 		-v $(CURDIR):/var/config \

build: .build-dev

.build-dev: Dockerfile ../requirements.txt ../cse.sh ../container_service_extension/*.py
	docker build -t dockerhub.artifactory.eng.vmware.com/container-service-extension:${USER} .
	touch $@

VERSION = latest

# Build the dockerfile for docker hub
build-hub: Dockerfile
	docker build \
		-t vmware/container-service-extension:${VERSION} \
		-t dockerhub.artifactory.eng.vmware.com/vmware/container-service-extension:${VERSION} \
		.

# Mark phony labels, which are targets that ar enot backed by files
.PHONY: run build build-hub

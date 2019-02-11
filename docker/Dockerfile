# container-service-extension
# Copyright (c) 2019 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause
FROM photon:2.0-20190122

RUN tdnf install -y \
    python3-3.6.5-3.ph2 \
    python3-pip-3.6.5-3.ph2 \
    gzip tar \
    && pip3 install --upgrade pip setuptools

RUN mkdir /var/config
VOLUME /var/config

## Set WORKDIR, PORT, expose $PORT, cd to $WORKDIR
ENV WORKDIR=/root \
    PORT=8080 \
    LANG=en_US.UTF-8 \
    LC_ALL=en_US.UTF-8 \
    PYTHONPATH=/root:/usr/local/lib/python36.zip:/usr/local/lib/python3.6:/usr/local/lib/python3.6/lib-dynload:/usr/local/lib/python3.6/site-packages

RUN pip3 install container_service_extension==1.2.6

EXPOSE ${PORT}
WORKDIR ${WORKDIR}

ENTRYPOINT [ "/usr/bin/cse" ]

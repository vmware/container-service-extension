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

## Set WORKDIR, cd to $WORKDIR
ENV LANG=en_US.UTF-8 \
    LC_ALL=en_US.UTF-8 \
    CSE_CONFIG=/var/config/config.yaml \
    CSE_PKS_CONFIG=/var/config/pks.yaml \
    CSE_USE_LOCAL_VERSION=True \
    PYTHONPATH=/root:/usr/local/lib/python36.zip:/usr/local/lib/python3.6:/usr/local/lib/python3.6/lib-dynload:/usr/local/lib/python3.6/site-packages

COPY LICENSE.txt \
     requirements.txt \
     cse.sh \
     /root/
COPY container_service_extension/ /root/container_service_extension/
COPY scripts/ /root/scripts/

RUN pip3 install -r /root/requirements.txt
RUN /bin/python3 -c "import compileall; compileall.compile_dir('/root/')"

RUN chmod a+x /root/cse.sh

WORKDIR /root
ENTRYPOINT [ "/bin/python3", "container_service_extension/cse.py" ]

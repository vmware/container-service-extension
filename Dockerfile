# container-service-extension
# Copyright (c) 2019 VMware, Inc. All Rights Reserved.
# SPDX-License-Identifier: BSD-2-Clause
FROM photon:2.0-20190122

# Install all of the RPM prerequisites
RUN tdnf install -y \
    python3-3.6.5-3.ph2 \
    python3-pip-3.6.5-3.ph2 \
    gzip tar \
    && pip3 install --upgrade pip setuptools

# Create and declare the directory that will hold the configuration files.
RUN mkdir /var/config
VOLUME /var/config

# Set up the environment variables.
#
# Since we will map config files from outside the container to
# the /var/config directory within the container, we can configure
# the file paths.
#
# The scripts will recognize that we are running from local
# source (instead of PyPi packages because of the CSE_USE_LOCAL_VERSION flag.
# (this is only used by the code the prints the version)
#
ENV LANG=en_US.UTF-8 \
    LC_ALL=en_US.UTF-8 \
    CSE_CONFIG=/var/config/config.yaml \
    CSE_PKS_CONFIG=/var/config/pks.yaml \
    CSE_USE_LOCAL_VERSION=True \
    PYTHONPATH=/root:/usr/local/lib/python36.zip:/usr/local/lib/python3.6:/usr/local/lib/python3.6/lib-dynload:/usr/local/lib/python3.6/site-packages

# Install the Python pre-reqs
COPY requirements.txt /root/
RUN pip3 install -r /root/requirements.txt

# Copy all of the server files into the container
COPY LICENSE.txt \
     cse.sh \
     /root/
COPY scripts/ /root/scripts/
COPY container_service_extension/ /root/container_service_extension/


# Precompile the python files to shave a few millseconds of container startup time
RUN /bin/python3 -c "import compileall; compileall.compile_dir('/root/')"

# The default entrypoint for the container is the cse.py script
# this allows arguments to be passed more naturally when running
# from docker on the command line.
WORKDIR /root
ENTRYPOINT [ "/bin/python3", "container_service_extension/cse.py" ]

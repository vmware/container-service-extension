# container-service-extension container

This folder contains the Dockerfile that is used to
build the container-service-extension container posted to
hub.docker.com.

## Usage

The entrypoint for the container is configured to be the python
script, so run the container and pass arguments as normal.

For example:

`docker run -it --rm vmware/container-service-extension:latest version`

## Running as a service

Docker has easy mechanisms to run a container as a daemon service.

`docker run -dit --restart unless-stopped vmware/container-service-extension:latest run`

## Development

A developer-friendly version of the Dockerfile is also provided
for building containers against local sources.

#!/usr/bin/env bash

yapf -i container_service_extension/*.py
yapf -i container_service_extension/client/*.py
yapf -i tests/*.py
flake8 container_service_extension/*.py
flake8 container_service_extension/client/*.py
flake8 tests/*.py

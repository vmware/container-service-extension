#!/usr/bin/env bash

rm -rf container_service_extension/*.pyc
rm -rf build dist
python setup.py develop
python setup.py sdist bdist_wheel
twine upload dist/*

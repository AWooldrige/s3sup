#!/usr/bin/env bash
set -eu
pip install moto[server]
moto_server s3 -p5000

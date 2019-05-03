#!/usr/bin/env bash
set -eu

export AWS_SECRET_ACCESS_KEY='foo'
export AWS_ACCESS_KEY_ID='bar'

s3sup status -v -p test_proj

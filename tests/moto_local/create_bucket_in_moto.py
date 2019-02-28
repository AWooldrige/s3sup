#!/usr/bin/env python3
import os
import boto3

if __name__ == '__main__':
    os.environ['AWS_ACCESS_KEY_ID'] = 'FOO'
    os.environ['AWS_SECRET_ACCESS_KEY'] = 'BAR'

    c = boto3.resource(
        service_name='s3',
        region_name='eu-west-1',
        endpoint_url='http://localhost:5000'
    )
    c.create_bucket(Bucket='www.example.com')

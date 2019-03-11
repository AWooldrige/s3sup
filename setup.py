from setuptools import setup, find_packages
import os

here = os.path.abspath(os.path.dirname(__file__))

with open(os.path.join(here, 'README.md'), encoding='utf-8') as f:
    # Filter out demo GIFs from the pypi version
    long_description = ''.join(
        l for l in f.readlines()
        if '<img src' not in l and ' demo ' not in l)

setup(
    name='s3sup',
    version='0.2.1',
    description='Static site uploader for Amazon S3',
    long_description=long_description,
    long_description_content_type='text/markdown',
    url='https://github.com/awooldrige/s3sup',
    author='Alistair Wooldrige',
    author_email='s3sup@woolie.co.uk',

    # For a list of valid classifiers, see https://pypi.org/classifiers/
    classifiers=[  # Optional
        # How mature is this project? Common values are
        #   3 - Alpha
        #   4 - Beta
        #   5 - Production/Stable
        'Development Status :: 4 - Beta',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: GNU General Public License v3 (GPLv3)',
        'Programming Language :: Python :: 3 :: Only',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7'
    ],
    keywords='s3sup AWS S3 static',
    packages=find_packages(exclude=['contrib', 'docs', 'tests']),
    python_requires='>=3, <4',
    install_requires=[
        'boto3>=1,<2',
        'click>=7,<9',
        'humanize>=0.4,<1',
        'inflect>=2,<3',
        'jsonschema>=2,<4',
        'toml>=0.9,<1'
    ],
    include_package_data=True,
    extras_require={
        'test': ['flake8', 'moto'],
    },
    entry_points={
        'console_scripts': [
            's3sup=s3sup.scripts.s3sup:cli',
        ],
    },
    project_urls={
        'Bug Reports': 'https://github.com/awooldrige/s3sup/issues',
        'Source': 'https://github.com/awooldrige/s3sup/'
    }
)

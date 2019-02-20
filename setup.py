from setuptools import setup, find_packages
from os import path

here = path.abspath(path.dirname(__file__))

with open(path.join(here, 'README.md'), encoding='utf-8') as f:
    long_description = f.read()

setup(
    name='s3sup',
    version='0.1.0',
    description='Static site uploader for Amazon S3',
    long_description=long_description,
    long_description_content_type='text/markdown',
    url='https://github.com/awooldrige/s3sup',
    author='Alistair Wooldrige',

    # For a list of valid classifiers, see https://pypi.org/classifiers/
    classifiers=[  # Optional
        # How mature is this project? Common values are
        #   3 - Alpha
        #   4 - Beta
        #   5 - Production/Stable
        'Development Status :: 4 - Beta',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: GNU General Public License v3 (GPLv3)',
        'Programming Language :: Python :: 3 :: Only'
    ],
    keywords='s3sup AWS S3 static',
    packages=find_packages(exclude=['contrib', 'docs', 's3sup.tests']),
    python_requires='>=3, <4',
    install_requires=[
        'boto3>=1,<2',
        'click>=7,<8',
        'jsonschema>=2,<3',
        'toml>=0.10,<1',
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

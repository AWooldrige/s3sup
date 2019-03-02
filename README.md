# s3sup - static site uploader for Amazon S3
s3sup may be better than other S3 syncing solutions (e.g. `s3sync`) if you host
a static site on S3. Features include:

 * MIME type detection, with `Content-Type` set correctly.
 * Set HTTP headers (e.g. `Cache-Control`) on groups of files/pages or
   individually.
 * Fast and efficient synchronisation to S3 (through maintaining a catalogue of
   state), reducing pain when making frequent small site changes.

s3sup can be installed using `pip`. Please note `s3sup` supports Python 3 only:

    pip install s3sup

Quick demo for a new site created using the "Getting started" guide below:

<p align="center"><img src="/docs/termrecs/render_s3supdemo_newsite.gif?raw=true"/></p>

# Getting started

## 1) Add s3sup.toml file to your local static site root
Change into your local static site directory and run:

    s3sup init

Then edit the skeleton s3sup configuration file created at `./s3sup.toml`

## 2) Configure AWS credentials
AWS credentials can be configured using [any method that the underlying boto3 library supports](https://boto3.amazonaws.com/v1/documentation/api/latest/guide/configuration.html).
For most users, this will mean creating a credentials file at
`~/.aws/credentials` following this template:

    [default]
    aws_access_key_id=foo
    aws_secret_access_key=bar

Or alternatively providing the credentials as environment variables
`AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY`.


## 3) Run s3sup
Check what changes s3sup thinks needs to be made to S3:

    s3sup status

Then upload changes:

    s3sup upload

At any point, add `--help` onto a command or subcommand for usage information:

    $ s3sup upload --help
    Usage: s3sup upload [OPTIONS]

      Synchronise local static site to S3.

      Use --dryrun to test behaviour without changes actually being made to S3.
      Or use "s3sup status".

    Options:
      -v, --verbose          Output running commentary.
      -p, --projectdir TEXT  Local s3sup project directory. Containing the
                             s3sup.toml file.
      -d, --dryrun           Simulate changes to be made. Don't modify files on
                             S3, read operations only.
      --help                 Show this message and exit.


# Configuration file
s3sup expects an `s3sup.toml` configuration file within the root directory of
your static site.  This configuration file allows you to:

 * Set page/object specific headers, for example setting a long Cache-Control
   on CSS and images, but a short one on all webpages.

If multiple `[[path_specific]]` entries match a path:
  * Directives are combined from all matching `[[path_specific]]` entries.
  * The last matching `[[path_specific]]` wins for equivalent directive keys.


## Example site configuration
The following example configuration:

 * Sets by default all objects to have a cache lifetime of two minutes
 * Sets a longer cache lifetime on PDFs and sets response header so that they
   are downloaded by the browser rather than displayed.

s3sup.toml:

    [aws]
    region_name = 'eu-west-1'
    s3_bucket_name = 'mys3websitebucket'
    s3_project_root = ''


    [[path_specific]]
    path = '^.*$'
    Cache-Control = 'max-age=120'

    [[path_specific]]
    path= '^/assets/download/[0-9]+.pdf$'
    Content-Disposition = 'attachment'
    Cache-Control = 'max-age=360'


# s3sup internals
## Catalogue file
The catalogue file contains hashes of all files in a s3sup project. Paths are
relative to the project directory. The catalog file (`s3sup.catalogue.csv`) is
uploaded to the S3 destination (without being publicly readable) to allow s3sup
to upload only what is needed during subsequent uploads.

Example structure:

    file_path,content_hash,headers_hash
    "/assets/logo.svg",AAA,BBB
    "/index.html",XXX,YYY


## Development backlog

Documentation
 * [ ] Add guide for using s3sup with existing projects already uploaded to S3.
 * [ ] Add guide for using s3sup with new site completely from scratch.
 * [ ] Add example terminal GIFs to the getting started guide.

New features
 * [ ] Add --nodelete option and config setting.
 * [ ] Add --force option to upload as if no remote catalogue available.
 * [ ] Allow S3 website redirects to be set.
 * [ ] Allow custom error page to be set.
 * [ ] Parallelise S3 operations.

Improvements
 * [ ] Detect when S3 bucket doesn't exist. Stacktrace at the moment.
 * [ ] Add python 3 type hints.
 * [ ] Sort out usage of temporary files. Make sure tests and main source don't
   spew files to `/tmp` in error conditions.
 * [ ] Standardise on using pathlib.Path where possible.

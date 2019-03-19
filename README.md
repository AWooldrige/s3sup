# s3sup - static site uploader for Amazon S3
s3sup may be better than other S3 syncing solutions (e.g. `s3sync`) if you host
a static site on S3. Main features include:

 * MIME type detection, with `Content-Type` set correctly automatically.
 * Setting important HTTP headers (e.g. `Cache-Control` and
   `Content-Disposition`) on groups of files or individually.
 * Fast and efficient synchronisation to S3 through maintaining a catalogue of
   content already on S3.

s3sup can be installed using `pip`. Please note `s3sup` supports Python 3 only:

    pip3 install s3sup

New site being uploaded to S3:

<p align="center"><img src="/docs/termrecs/render_s3supdemo_newsite.gif?raw=true"/></p>

## Getting started

#### 1) Add s3sup.toml file to your local static site root
Inside your local static site directory, run:

    s3sup init

Then edit the skeleton s3sup configuration file created at `./s3sup.toml`.

#### 2) Configure AWS credentials
AWS credentials can be configured using [any method that the underlying boto3 library supports](https://boto3.amazonaws.com/v1/documentation/api/latest/guide/configuration.html).
For most users, this will mean creating a credentials file at
`~/.aws/credentials` following this template:

    [default]
    aws_access_key_id=foo
    aws_secret_access_key=bar

Or alternatively credentials can be provided as environment variables
`AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY`.


#### 3) Run s3sup
Check what changes s3sup thinks needs to be made to S3:

    s3sup status

Then upload changes:

    s3sup upload


## Configuration file
s3sup expects an `s3sup.toml` configuration file within the root directory of
your static site. Only the `[aws]` section must be included at minimum:

### `[aws]` section
An `[aws]` section, telling s3sup where to find your S3 bucket:

    [aws]
    region_name = ''  # E.g. 'eu-west-1'
    s3_bucket_name = '' # E.g. 'mys3websitebucketname'
    s3_project_root = ''  # Root location for project within S3, e.g. 'staging/'

### `[[path_specific]]` sections
One or more `[[path_specific]]` sections. Each `[[path_specific]]` section must
contain a `path` for which the directives in that section should apply to.  The
`path` can be the relative path to a file within the project directory, or a
regular expression matching multiple paths.

If multiple `[[path_specific]]` entries match the same path, directives are
combined from all matching `[[path_specific]]` entries, with the last matching
`[[path_specific]]` directive entry winning for equivalent directive keys.

Along with `path`, the following directives can be set:
 * `ACL`: One of: private, public-read, authenticated-read. Default:
   'public-read'.
 * `StorageClass`: For an S3 website, usually either 'STANDARD' or
   'REDUCED_REDUNDANCY'. Default: 'STANDARD'.
 * `WebsiteRedirectLocation`: Instruct S3 to respond with a redirect to this
   URL, rather than serving the file.
 * `Cache-Control`: Set HTTP header value to control cache lifetime. Default:
   'max-age=10'.
 * `Content-Disposition`: Set HTTP header value.
 * `Content-Type`: Set HTTP header value. Only override this if absolutely
   necessary as s3sup MIME type detection normally sets this header correctly.
   Default: automatically determined.
 * `charset`: Manually specify the character encoding of the file, which is
   appended to `Content-Type`. Usually setting charset in the global
   configuration section is adequate but this directives allows control on a
   path level.
 * `Content-Encoding`: Set HTTP header value. Only override this if absolutely
   necessary, s3sup encoding detection normally covers this.
 * `Content-Type`: Set HTTP header value. Only override this if necessary as
   s3sup content encoding detection normally sets this header correctly.
   Default: automatically determined.

Use `s3sup inspect <filename>` to check the attributes that s3sup will set
based on your configuration settings and defaults:

    $ s3sup inspect index.html
    ************************************************************
    * PROJECT INFORMATION
    ************************************************************
      - Local project dir: . (current dir)
      - AWS region: eu-west-1
      - S3 bucket: s3://www.example.com/test

    File: index.html
    ****************
      - Local path: /home/awooldrige/www.example.com/index.html
      - S3 path: s3://www.example.com/test/index.html
      - Attributes:
        - ACL: public-read
        - Cache-Control: private; max-age=300
        - Content-Type: text/html; charset=utf-8
      - Content size: 166 Bytes
      - Content hash: e1086538d9d7f9e458c0890b17e768f7ace099b9df922de65fb0009865784284
      - Attributes hash: f5a7cc18a936c3a406d958ea1d64dd8e760bf3d9cabb830810089f0a44fe8ab6

### `[mimetype_overrides]` section
Optional, usually not required. Provide manual mappings of file extensions to
MIME type, which will take precedence over any automatic MIME type detection
that s3sup has made. E.g.

    [mimetype_overrides]
    '.woff2' = 'font/woff2'
    '.toml' = 'application/toml'


### Example configuration file
The following example configuration:

 * Sets all files with a cache lifetime of two minutes by default.
 * Sets a longer cache lifetime on PDFs and a response header to trigger the
   browser to download the file rather than display it.

Example `s3sup.toml`:

    [aws]
    region_name = 'eu-west-1'
    s3_bucket_name = 'mys3websitebucket'


    [[path_specific]]
    path = '^.*$'
    Cache-Control = 'max-age=120'

    [[path_specific]]
    path= '^/assets/download/[0-9]+.pdf$'
    Content-Disposition = 'attachment'
    Cache-Control = 'max-age=360'

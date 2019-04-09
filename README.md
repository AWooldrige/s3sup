# s3sup - static site uploader for Amazon S3
s3sup may be better than other S3 syncing solutions (e.g. `s3sync`) if you host
a static site on S3. Main features include:

 * MIME type detection, with `Content-Type` set correctly for most files.
 * Fast and efficient synchronisation to S3 through maintaining a catalogue of
   content/metadata checksums for files already uploaded.
 * Hierarchical configuration of important HTTP headers (e.g. `Cache-Control`
   and `Content-Disposition`) on groups of files or individually.

Demo of new site being uploaded to S3:

<p align="center"><img src="/docs/termrecs/render_s3supdemo_newsite.gif?raw=true"/></p>

## Getting started
Follow these steps to get a new site uploaded to S3 with s3sup.

#### 1) Add s3sup.toml file to your local static site root
Inside your local static site directory, add an s3sup configuration file for
the first time using:

    s3sup init

Then edit the skeleton configuration file created at `./s3sup.toml`. For a
guide to the configuration settings, see section below. To verify the
destination path, HTTP headers and defaults that s3sup will set for an
individual file, use:

    s3sup inspect <filepath>


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
Check what changes s3sup thinks needs to be made to S3. At the beginning, this
will indicate that all files are new and need to be uploaded:

    s3sup status

Then upload changes to S3:

    s3sup push


## Installation
s3sup can be installed using `pip`. Please note `s3sup` supports Python 3 only:

    pip3 install s3sup

No distribution specific packages are available yet, please use the `pip`
installation method or download source from
[GitHub](https://github.com/awooldrige/s3sup).

To see the commands available, run s3sup with `--help`:

    $ s3sup --help
    Usage: s3sup [OPTIONS] COMMAND [ARGS]...

      s3sup - Amazon S3 static site uploader

    Options:
      --help  Show this message and exit.

    Commands:
      init     Create a skeleton s3sup.toml in the current directory.
      inspect  Show calculated metadata for individual files.
      push     Synchronise local static site to S3.
      status   Show S3 changes that will be made on next push.

Each command also provides a `--help`:

    $ s3sup push --help
    Usage: s3sup push [OPTIONS]

      Synchronise local static site to S3.

      Use --dryrun to test behaviour without changes actually being made to S3.
      Or use "s3sup status".

      This command has two other aliases: upload or sync.

    Options:
      -v, --verbose          Output more informational messages than normal.
      -p, --projectdir TEXT  Specify local s3sup static site directory (containing
                             s3sup.toml). By default the current directory is
                             used.
      -n, --nodelete         Do not delete any files on S3, add/modify operations
                             only. Alternatively set "preserve_deleted_files" in
                             s3sup.toml.
      -d, --dryrun           Simulate changes to be made. Do not modify files on
                             S3.
      --help                 Show this message and exit.


## Configuration file guide
s3sup expects an `s3sup.toml` configuration file within the root directory of
your static site. Only the `[aws]` section must be included at minimum:


### Optional: Global configuration section
These settings must be placed at the top of the `s3sup.toml` file otherwise
schema validation errors will occur (TOML interprets them as as belonging to
the previous section otherwise):

| Configuration key | Required | Default | Type | Expected value |
| ----------------- | -------- | ------- | ---- | -------------- |
| `preserve_deleted_files` | Optional | `false` |  Boolean | Setting to `true` will prevent files being deleted from S3 when they are deleted in the local project. This can be useful if your site has a long cache lifetime and you don't want cached pages to reference stylesheets/JavaScript files that suddenly disappear. This feature only prevents file deletions, it doesn't prevent file contents being overwritten if updated locally. This can also be achieved by supplying `--nodelete` as a command line option. |
| `charset` | Optional | `'utf-8'` | String | Specify the character encoding of text files within this s3sup project. The charset is appended to `Content-Type` header. This can also be overriden on a `[[path_specific]]` basis. |


### Required: `[aws]` section
Configuration settings related to AWS:

| Configuration key | Required | Default | Type | Expected value |
| ----------------- | -------- | ------- | ---- | -------------- |
| `region_name` | Required | N/A | String | AWS region that the S3 bucket is located in. E.g. 'eu-west-1'. |
| `s3_bucket_name` | Required | N/A | String | Name of the S3 bucket. E.g.  'mywebsitebucketname' |
| `s3_project_root` | Optional | Bucket root | String | S3 sub path where the local project should be uploaded to, without a leading slash. E.g. 'staging/'. By default the local project is uploaded to the root of the S3 bucket. |

### Optional: One or more `[[path_specific]]` sections
One or more `[[path_specific]]` sections may be included. Each
`[[path_specific]]` section must contain a `path` specification for which the
directives in that section should apply to.  The `path` can be the relative
path to a file within the project directory, or a regular expression matching
multiple paths.

If multiple `[[path_specific]]` entries match the same path, directives are
combined from all matching `[[path_specific]]` entries, with the last matching
`[[path_specific]]` directive entry in the configuration file winning for
equivalent directive keys.

Along with `path`, the following directives can be set:

| Configuration key | Required | Default | Type | Expected value |
| ----------------- | -------- | ------- | ---- | -------------- |
| `path` | Required | N/A | String | Regular expression matching multiple relative paths, or an individual relative path to a file. |
| `ACL` | Optional | `'public-read'` | String | S3 access permissions for the matching paths. One of: private, public-read, authenticated-read. |
| `StorageClass` | Optional | `'STANDARD'` | String | S3 storage resiliency class. One of: STANDARD, REDUCED_REDUNDANCY, STANDARD_IA, ONEZONE_IA, INTELLIGENT_TIERING or GLACIER. |
| `WebsiteRedirectLocation` | Optional | None | String | Instead of serving the file when a client requests this path, instruct S3 to respond with a redirect to the specified URL instead. Note that URLs must be absolute, e.g. 'https://www.example.com/new_home'. |
| `Cache-Control` | Optional | `max-age=10` | String | Set HTTP header value to control cache lifetime. A short default cache lifetime is set to provide basic origin shielding should an explicit one not be set. |
| `Content-Disposition` | Optional | None | String | Set HTTP header value to control whether the browser should display the file contents or provide a download dialog to the user |
| `Content-Type` | Optional | Automatic | String | Override Content-Type HTTP header value. Only override this if absolutely necessary as s3sup MIME type detection normally sets this header correctly. |
| `charset` | Optional | `'utf-8'` | String | Manually specify the character encoding of text containing files. This is appended to `Content-Type` HTTP header. Usually setting `charset` in the global configuration section is adequate but this directives allows control on a path level. |
| `Content-Encoding` | Optional | Automatic | String | Set Content-Encoding HTTP header value. Only override this if absolutely necessary as s3sup detects encoding automatically. For wide browser support, it is recommended to store content uncompressed in S3 and then use dynamic gzip compression in a CDN layer. |

Use `s3sup inspect <filename>` to check the attributes that s3sup will set
based on your configuration settings and defaults.

### Optional: `[mimetype_overrides]` section
Optional, usually not required. Provide manual mappings of file extensions to
MIME type, which will take precedence over any automatic MIME type detection
that s3sup has made. This can be useful for very modern MIME types E.g.

    [mimetype_overrides]
    '.woff3' = 'font/woff3'
    '.oml' = 'application/oml'


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

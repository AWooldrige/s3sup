# s3sup internals
## Catalogue file
The catalogue file contains hashes of all files in a s3sup project. Paths are
relative to the project directory. The catalog file (`s3sup.cat`) is
uploaded to the S3 destination (without being publicly readable) to allow s3sup
to upload only what is needed during subsequent uploads.


## Old CSV catalogue file
Before the move to SQLite, the catalogue used to be a simple CSV file. Example
structure:

    file_path,content_hash,headers_hash
    "/assets/logo.svg",AAA,BBB
    "/index.html",XXX,YYY

This is no longer used and s3sup versions >= 0.4.0 will automatically migrate
to the new SQLite format. An intentionally corrupt `.s3sup.catalogue.csv` is
put in its place so that older versions of s3sup (<= 0.3.0) fail hard, rather
than not being aware of the new format and attempting to upload the whole
project again.


## Development backlog

Documentation
 * [ ] Add guide for using s3sup with existing projects already uploaded to S3.
 * [ ] Add guide for using s3sup with new site completely from scratch.

New features
 * [ ] Add profiles support, e.g. for 'staging' and 'prod'.
 * [ ] Add --force option to upload as if no remote catalogue available.
 * [ ] Allow S3 website redirects to be set.
 * [ ] Allow custom error page to be set.
 * [ ] Progress indicator for individual large files.
 * [ ] Parallelise S3 operations.

Improvements
 * [ ] Add tests to make sure performant (cycles/mem) with huge projects
 * [ ] If no projectdir provided, walk up dirs to find s3sup.toml, like git.
 * [ ] Detect when S3 bucket doesn't exist. Stacktrace at the moment.
 * [ ] Add retry to S3 uploads.
 * [ ] Add python 3 type hints.
 * [ ] Sort out usage of temporary files. Make sure tests and main source don't
   spew files to `/tmp` in error conditions.
 * [ ] Standardise on using pathlib.Path where possible.

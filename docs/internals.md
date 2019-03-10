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

New features
 * [ ] Add profiles support, e.g. for 'staging' and 'prod'.
 * [ ] Add --nodelete option and config setting.
 * [ ] Add --force option to upload as if no remote catalogue available.
 * [ ] Add `s3sup attrs <local_fpath>` which displays attributes to be set
   and final S3 path.
 * [ ] Allow S3 website redirects to be set.
 * [ ] Allow custom error page to be set.
 * [ ] Progress bar for individual large files?
 * [ ] Parallelise S3 operations.

Improvements
 * [ ] If no projectdir provided, walk up dirs to find s3sup.toml, like git.
 * [ ] Detect when S3 bucket doesn't exist. Stacktrace at the moment.
 * [ ] Add python 3 type hints.
 * [ ] Add retry to S3 uploads
 * [ ] Find  best practice way to memoize function return values in FilePrepper
 * [ ] Sort out usage of temporary files. Make sure tests and main source don't
   spew files to `/tmp` in error conditions.
 * [ ] Standardise on using pathlib.Path where possible.

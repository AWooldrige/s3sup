# Changelog
All notable changes to s3sup are documented in this file with each release
version. ChangeLog format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.5.0] - 2019-06-10
### Changed
 - Prevent HTML files referencing static assets (stylesheets/scripts/images)
   before they exist on S3. Achieved by applying a crude but effective ordering
   to the upload sequence to ensure HTML files are uploaded after all other
   assets.


## [0.4.0] - 2019-05-03
### Changed
 - Remote catalogue now a gzipped SQLite database rather than an uncompressed
   CSV file. This will speed up s3sup status and push commands. Migration is
   automatic and requires no intervention. One caveat is that after running an
   `s3sup push` with this version or newer, it will no longer be possible to
   use _older_ versions of s3sup (<= 0.3.0) with the same project.


## [0.3.0] - 2019-04-09
### Added
 - Prevent files being deleted on S3 even when they are removed locally.
   Supply command line option `--nodelete` or global configuration value
   `preserve_deleted_files`.
 - Additional MIME type detection for TOML, WOFF and WOFF2 files.

### Changed
 - `s3sup upload` renamed to `push` for consistency with command line tool best
   practice. Aliases `upload` and `sync` added to maintain backwards
   compatibility.
 - Perform preflight checks to ensure the S3 bucket exists before attempting to
   upload. Previously a boto3 stack trace would have been presented at the
   start of upload.
 - Improved README and command line help text.

### Fixed
 - Make S3 attribute changes only once, previously they were being repeated
   twice, unnecessarily due to double listing in catalogue.change\_list.


## [0.2.2] - 2019-03-19
### Fixed
 - Handle `s3_project_root` being either not set or set as empty string.


## [0.2.1] - 2019-03-11
### Added
 - New command: `s3sup inspect` for reviewing attributes calculated from the
   s3sup configuration file.

### Changed
 - Minor performance improvements from memoization.
 - Display file size along with uploads.


## [0.1.1] - 2019-03-02
### Added
- Initial release

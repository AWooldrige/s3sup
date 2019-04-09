# Changelog
All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]
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

### Fixed
 - Make S3 attribute changes only once, previously they were being repeated
   twice, unnecessarily due to double listing in catalogue.change_list.

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

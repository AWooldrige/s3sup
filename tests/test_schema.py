import unittest
import jsonschema
import s3sup.rules


class BaseSchemaTestCase(unittest.TestCase):

    def setUp(self):
        self.schema = s3sup.rules._load_schema()

    def assertValid(self, rules):
        self.assertTrue(jsonschema.validate(rules, self.schema) is None)

    def assertInvalid(self, rules):
        self.assertRaises(
            jsonschema.ValidationError, jsonschema.validate, rules,
            self.schema)


class ValidateMimetypeOverrides(BaseSchemaTestCase):

    def test_not_required(self):
        self.assertValid({})

    def test_can_be_empty_object(self):
        self.assertValid({"mimetype_overrides": {}})

    def test_cannot_be_other_types(self):
        self.assertInvalid({"mimetype_overrides": "text/html"})
        self.assertInvalid({"mimetype_overrides": ["type", "text/html"]})
        self.assertInvalid({"mimetype_overrides": 123})
        self.assertInvalid({"mimetype_overrides": True})

    def test_valid_use_cases(self):
        self.assertValid({"mimetype_overrides": {"html": "text/html"}})
        self.assertValid({"mimetype_overrides": {
            "7z": "application/x-7z-compressed",
            "apk": "application/vnd.android.package-archive"
        }})


class ValidatePathSpecificHeadersPropertyTestCase(BaseSchemaTestCase):

    def test_not_required(self):
        self.assertValid({})

    def test_can_be_empty_list(self):
        self.assertValid({"path_specific": []})

    def test_cannot_be_other_types(self):
        self.assertInvalid({"path_specific": "dancing"})
        self.assertInvalid({"path_specific": {"_path": r"^.*$"}})
        self.assertInvalid({"path_specific": 123})
        self.assertInvalid({"path_specific": True})


class ValidatePathSpecificDirective(BaseSchemaTestCase):

    def assertDirectiveValid(self, directive):
        self.assertValid({"path_specific": [directive]})

    def assertDirectiveInvalid(self, directive):
        self.assertInvalid({"path_specific": [directive]})

    def test_path_must_be_present(self):
        self.assertDirectiveInvalid({})

    def test_path_must_not_be_empty(self):
        self.assertDirectiveInvalid({"path": ""})

    def test_path_valid_use_cases(self):
        self.assertDirectiveValid({"path": "robots.txt"})
        self.assertDirectiveValid({"path": r"image/[0-9].jpg$"})
        self.assertDirectiveValid({"path": r"^recipe/.*"})

    def test_path_must_be_string(self):
        self.assertDirectiveInvalid({"path": ["robots.txt", "index.html"]})
        self.assertDirectiveInvalid({"path": 123})
        self.assertDirectiveInvalid({"path": True})
        self.assertDirectiveInvalid({"path": {"a": "b"}})

    def test_cache_control_cant_be_empty(self):
        self.assertDirectiveInvalid({
            "path": r"^recipe/.*",
            "Cache-Control": ""})

    def test_acl_must_be_known_type(self):
        self.assertDirectiveValid({
            "path": r"^recipe/.*",
            "ACL": "private"})
        self.assertDirectiveInvalid({
            "path": r"^recipe/.*",
            "ACL": "DenyAll"})

    def test_storage_class_must_be_known_type(self):
        self.assertDirectiveValid({
            "path": r"^recipe/.*",
            "StorageClass": "STANDARD"})
        self.assertDirectiveInvalid({
            "path": r"^recipe/.*",
            "StorageClass": "TAPE"})

    def test_valid_use_cases(self):
        self.assertDirectiveValid({
            "path": r"^recipe/.*",
            "Cache-Control": "max-age=10"})
        self.assertDirectiveValid({
            "path": r"^recipe/.*",
            "Cache-Control": "private, max-age=10",
            "Content-Type": "text/plain; test",
            "StorageClass": "REDUCED_REDUNDANCY",
            "ACL": "private",
            "S3Metadata": {
                "blah": "blam"
            }
        })

    def test_cachecontrol_must_be_string_to_string_map(self):
        self.assertDirectiveInvalid({
            "path": r"^recipe/.*",
            "Cache-Control": 10})
        self.assertDirectiveInvalid({
            "path": r"^recipe/.*",
            "Cache-Control": True})
        self.assertDirectiveInvalid({
            "path": r"^recipe/.*",
            "Cache-Control": [1]})
        self.assertDirectiveInvalid({
            "path": r"^recipe/.*",
            "Cache-Control": {"max-age": "10"}})

    def test_directives_extra_properties_no_allowed(self):
        self.assertDirectiveInvalid({
            "path": "robots.txt",
            "steak": "medium rare"})


if __name__ == '__main__':
    unittest.main()

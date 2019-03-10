import re
import toml
import json
import pkgutil

import jsonschema


def directives_for_path(path, rules):
    attrs = {}
    notransfer = {'path', 'path_re', '_comment'}
    try:
        path_specific_rules = rules['path_specific']
    except KeyError:
        return attrs
    for p in path_specific_rules:
        if p['path_re'].match(path) is not None:
            to_add = {k: v for (k, v) in p.items() if k not in notransfer}
            attrs = {**attrs, **to_add}
    return attrs


def _load_schema():
    schema = pkgutil.get_data(__package__, 'rules.schema.json')
    return json.loads(schema)


def _compile_path_regex(rules):
    if 'path_specific' in rules:
        for r in rules['path_specific']:
            r['path_re'] = re.compile(r['path'])
    return rules


def load_rules(rules_path):
    schema = _load_schema()
    with open(rules_path) as rf:
        rules = toml.load(rf)
    jsonschema.validate(rules, schema)
    rules = _compile_path_regex(rules)
    return rules

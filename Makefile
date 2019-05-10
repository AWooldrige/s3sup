###############################################################################
# Properish targets
###############################################################################
venv: venv/bin/activate
venv/bin/activate: requirements.txt
	test -d venv || python3 -m venv venv
	. venv/bin/activate && python3 -m pip install -r requirements.txt
	touch -c venv/bin/activate

# TODO: this needs to depend on all source files
dist: venv setup.py MANIFEST.in README.md $(shell find s3sup)
	. venv/bin/activate && python3 -m pip install setuptools wheel twine
	. venv/bin/activate && python3 setup.py sdist bdist_wheel


###############################################################################
# Standardish targets
###############################################################################
.PHONY: clean
clean::
	rm -rf venv build dist s3sup.egg-info
	find . -name '*.pyc' -delete

.PHONY: test
test:: venv flake8 twine_check unittest

.PHONY: unittest
unittest:: venv
	. venv/bin/activate && python3 -m unittest

.PHONY: unittest_profile
unittest_profile:: venv
	. venv/bin/activate && python3 -m cProfile -o profiler.output -m unittest
	. venv/bin/activate && python3 -m pstats profiler.output

###############################################################################
# Targets lazily using a Makefile a script runner
###############################################################################
.PHONY: flake8
flake8:: venv
	. venv/bin/activate && flake8 s3sup/ tests/

.PHONY: twine_check
twine_check:: dist venv
	. venv/bin/activate && twine check dist/*

.PHONY: twine_test_upload
twine_test_upload:: dist venv
	. venv/bin/activate && twine upload --repository-url https://test.pypi.org/legacy/ dist/*

.PHONY: twine_upload
twine_upload:: dist venv
	. venv/bin/activate && twine upload dist/*

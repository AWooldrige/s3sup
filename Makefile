###############################################################################
# Properish targets
###############################################################################
venv: venv/bin/activate
venv/bin/activate: requirements.txt
	test -d venv || python3 -m venv venv
	. venv/bin/activate && python3 -m pip install -r requirements.txt

# TODO: this needs to depend on all source files
dist: venv
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
test:: flake8 twine_check venv
	. venv/bin/activate && python3 -m unittest


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

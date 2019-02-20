.PHONY: test
test:: venv
	. venv/bin/activate && python3 -m unittest

.PHONY: flake8
flake8:: venv
	. venv/bin/activate && flake8 s3sup/ tests/

venv: venv/bin/activate
venv/bin/activate: requirements.txt
	test -d venv || python3.7 -m venv venv
	. venv/bin/activate && pip install -r requirements.txt
	touch venv/bin/activate

.PHONY: clean
clean::
	rm -rf venv
	find . -name '*.pyc' -delete

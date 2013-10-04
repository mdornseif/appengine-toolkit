GAE_VERSION=1.7.3

check: google_appengine
	pyflakes gaetk/
	pep8 -r --ignore=E501 gaetk/
	-pylint -iy --max-line-length=110 gaetk/__init__.py gaetk/extjs.py gaetk/handler.py # -rn

dependencies: pythonenv google_appengine

google_appengine:
	curl -s -O http://googleappengine.googlecode.com/files/google_appengine_$(GAE_VERSION).zip
	#/google/__init__.py:
	unzip google_appengine_$(GAE_VERSION).zip
	rm -Rf google_appengine_$(GAE_VERSION).zip

clean:
	rm -rf google/__init__.py pythonenv
	find . -name '*.pyc' -or -name '*.pyo' -delete

TEST_ARGS=-v -s --without-sandbox --with-gae --gae-lib-root=google_appengine --gae-application=./examples
test: dependencies
	PYTHONPATH=examples nosetests $(TEST_ARGS) tests/*.py

pythonenv:
	pip -q install huTools 
	pip -q install WebTest gaetestbed 
	pip -q install coverage mock fixture
	pip -q install nose nosegae 

.PHONY: clean check

GAE_VERSION=1.5.1

check: google/__init__.py
	pyflakes gaetk/
	pep8 -r --ignore=E501 gaetk/
	-pylint -iy --max-line-length=110 gaetk/__init__.py gaetk/extjs.py gaetk/handler.py # -rn

google/__init__.py:
	curl -O http://googleappengine.googlecode.com/files/google_appengine_$(GAE_VERSION).zip
	unzip google_appengine_$(GAE_VERSION).zip
	mv google_appengine/google .
	rm -Rf google_appengine
	rm -Rf google_appengine_$(GAE_VERSION).zip google_appengine

clean:
	find . -name '*.pyc' -or -name '*.pyo' -delete

.PHONY: clean check

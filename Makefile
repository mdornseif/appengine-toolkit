check: google/__init__.py
	pep8 -r --ignore=E501 gaetk/__init__.py gaetk/extjs.py gaetk/handler.py
	pyflakes gaetk/__init__.py gaetk/extjs.py gaetk/handler.py
	-pylint -iy --max-line-length=110 gaetk/__init__.py gaetk/extjs.py gaetk/handler.py # -rn

google/__init__.py:
	curl -O http://googleappengine.googlecode.com/files/google_appengine_1.3.8.zip
	unzip google_appengine_1.3.8.zip
	mv google_appengine/google .
	rm -Rf google_appengine
	rm -Rf google_appengine_1.3.8.zip google_appengine

clean:
	find . -name '*.pyc' -or -name '*.pyo' -delete

.PHONY: clean check

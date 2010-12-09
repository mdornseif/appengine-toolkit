deploy:
	appcfg.py update .

check: lib/google_appengine/google/__init__.py
	pep8 -r --ignore=E501 views/ *.py
	sh -c 'PYTHONPATH=`python config.py` pyflakes *.py views/'
	-sh -c 'PYTHONPATH=`python config.py` pylint -iy --max-line-length=110 *.py views/' # -rn

# Appengine SDK lokal installieren, damit pyLint und pyFlakes das finden
lib/google_appengine/google/__init__.py:
	curl -O http://googleappengine.googlecode.com/files/google_appengine_1.3.8.zip
	unzip google_appengine_1.3.8.zip
	rm -Rf lib/google_appengine
	mv google_appengine lib/
	rm google_appengine_1.3.8.zip

dependencies: clean
	git submodule update --init lib/gaetk
	git submodule update --init lib/jinja2
	virtualenv --python=python2.5 --no-site-packages --unzip-setuptools pythonenv
	pythonenv/bin/pip -q install -E pythonenv -r requirements.txt

clean:
	rm -Rf pythonenv/
	find . -name '*.pyc' -or -name '*.pyo' -delete

.PHONY: deploy pylint dependencies_for_check_target clean check dependencies

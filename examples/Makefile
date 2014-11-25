GAE_VERSION=1.9.1
APPID?= e~hudoraexpress
OPENAPPID?= hudoraexpress

LINT_LINE_LENGTH= 110
LINT_FLAKE8_ARGS= --max-complexity=40 --builtins=_ --max-line-length=$(LINT_LINE_LENGTH)
LINT_FILES= views/ *.py

deploy:
	# appcfg.py update .
	appcfg.py update -V dev-`whoami` -A $(APPID) .
	# TESTHOST=dev-`whoami`.$(APPID).appspot.com make resttest
	make opendev

checknodeps:
	flake8 $(LINT_FLAKE8_ARGS) $(LINT_FILES)
	#sh -c 'PYTHONUNBUFFERED=1 LC_ALL=en_US.UTF-8 PYTHONPATH=`python config.py`:$(MYPYTHONPATH) pylint $(PYLINT_ARGS) $(STRICT_LINT_FILES)'
	#@# der erste Durchlauf zeigt alle Probleme inkl. TODOs an
	#-sh -c 'LC_ALL=en_US.UTF-8 PYTHONPATH=`python config.py`:$(MYPYTHONPATH) pylint $(PYLINT_ARGS) $(LINT_FILES)'

check: lib/google_appengine/google/__init__.py checknodeps

# Install AppEngine SDK locally so pyLint und pyFlakes find it
lib/google_appengine/google/__init__.py:
	curl -s -O http://googleappengine.googlecode.com/files/google_appengine_$(GAE_VERSION).zip
	unzip -q google_appengine_$(GAE_VERSION).zip
	rm -Rf lib/google_appengine
	mv google_appengine lib/
	rm google_appengine_$(GAE_VERSION).zip

dependencies: clean
	git submodule update --init
	# rm -f lib/submodules.pth
	# git submodule foreach 'echo ./`basename ${path}` >> ../submodules.pth'

clean:
	rm -Rf pythonenv/
	find . -name '*.pyc' -or -name '*.pyo' -delete

openlogs:
	open "https://appengine.google.com/logs?app_id=s%7E$(OPENAPPID)&version_id=dev-`whoami`"

opendev:
	open http://dev-`whoami`.$(OPENAPPID).appspot.com/
	echo open http://dev-`whoami`.$(OPENAPPID).appspot.com/

.PHONY: deploy pylint dependencies_for_check_target clean check dependencies

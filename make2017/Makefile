# Defaults for gaetk appengine applications

-include ./lib/appengine-toolkit/include2017.mk

default: check

# Install AppEngine SDK locally so pyLint und pyFlakes find it
lib/google_appengine/google/__init__.py:
	curl -s -O https://storage.googleapis.com/appengine-sdks/featured/google_appengine_$(GAE_VERSION).zip
	unzip -q google_appengine_$(GAE_VERSION).zip
	rm -Rf lib/google_appengine
	mv google_appengine lib/
	rm google_appengine_$(GAE_VERSION).zip

# check without calling dependencies
checknodeps:
	flake8 $(LINT_FLAKE8_ARGS) $(LINT_FILES)
	# --disable=W0511 no TODOs
	sh -c 'PYTHONUNBUFFERED=1 LC_ALL=en_US.UTF-8 PYTHONPATH=`python config.py`:$(MYPYTHONPATH) pylint --disable=W0511 $(PYLINT_ARGS) $(PYLINT_ARGS_ADDON) $(LINT_FILES)'
	# TODOs anzeigen
	sh -c 'PYTHONUNBUFFERED=1 LC_ALL=en_US.UTF-8 PYTHONPATH=`python config.py`:$(MYPYTHONPATH) pylint $(PYLINT_ARGS) $(PYLINT_ARGS_ADDON) --disable=all --enable=W0511 $(LINT_FILES)'

check: lib/google_appengine/google/__init__.py checknodeps

# put onto dev-server run tests
deploy:
	# appcfg.py update .
	appcfg.py update -A $(APPID) -V dev-`whoami` .
	TESTHOST=dev-`whoami`-dot-$(OPENAPPID).appspot.com make resttest
	make check
	make opendev

# put onto staging server, run tests, then put onto production server
deploy_production:
	# wir legen ein komplett neues tmp verzeichnis mit einem sauberen checkout an und gehen von da weiter
	rm -Rf tmp
	mkdir tmp
	(cd tmp ; git clone git@github.com:hudora/$(REPOSNAME).git)
	(cd tmp/$(REPOSNAME) ; git checkout production ; make boot; NODE_ENV=production make dependencies code)
	(cd tmp/$(REPOSNAME) ; git show-ref --hash=7 refs/remotes/origin/production > version.txt)
	(cd tmp/$(REPOSNAME) ; curl https://$(OPENAPPID).appspot.com/version.txt > lastversion.txt)
	# Erst getaggte Version hochladen
	-appcfg.py update -A $(APPID) -V "v`cat tmp/$(REPOSNAME)/version.txt`" tmp/$(REPOSNAME)
	# Dann testen
	(cd tmp/$(REPOSNAME) ; TESTHOST="v`cat version.txt`"-dot-$(OPENAPPID).appspot.com make resttest)
	# Wenn das geklappt hat: produktionsversion aktivieren.
	appcfg.py update -A $(APPID) -V $(PRODUCTIONNAME) tmp/$(REPOSNAME)
	curl -X POST --data-urlencode 'payload={"channel": "#development", "username": "webhookbot", "text": "<$(PRODUCTIONURL)> neu deployed"}' https://hooks.slack.com/services/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
	(cd tmp/$(REPOSNAME) ; git log --pretty='* %s (%ae)' `cat lastversion.txt`..`cat version.txt`)

# beautify source code
fixup:
	autopep8 --global-config=/dev/null --recursive --in-place --pep8-passes 2000 --max-line-length=110 -a -a --experimental --ignore=E711,E712,E401 *.py modules/ tests/ lib/CentralServices/cs
	# Tailing Whitespace
	find modules -name '*.py' -print0 | xargs -0 perl -pe 's/[\t ]+$$//g' -i
	find templates -name '*.html' -print0 | xargs -0 perl -pe 's/[\t ]+$$//g' -i
	find text -name '*.markdown' -print0 | xargs -0 perl -pe 's/[\t ]+$$//g' -i
	# Tabs in Templates
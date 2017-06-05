# Defaults for gaetk appengine applications

# Use something like this at the bottom your Makefile:

# [your defs]
# -include ./lib/appengine-toolkit/make2017/include.mk
# boot:
# 	git submodule update --init
#	pip install --upgrade --target lib/site-packages -r requirements.txt
# [your targets]
# %: force
#	@$(MAKE) -f ./lib/appengine-toolkit/make2017/Makefile $@
# force: ;
#
# see also https://www.gnu.org/software/make/manual/html_node/Overriding-Makefiles.html

-include ./lib/appengine-toolkit/make2017/include.mk

default: check

# Install AppEngine SDK locally so pyLint und pyFlakes find it
lib/google_appengine/google/__init__.py:
	curl -s -O https://storage.googleapis.com/appengine-sdks/featured/google_appengine_$(GAE_VERSION).zip
	unzip -q google_appengine_$(GAE_VERSION).zip
	rm -Rf lib/google_appengine
	mv google_appengine lib/
	rm google_appengine_$(GAE_VERSION).zip


# check code quality
check: lib/google_appengine/google/__init__.py
	# erster, schnellere, grober check
	flake8 --builtins=_ --max-line-length=110 --ignore=E711,E712,N801,C901 $(PYCODE_FILES)
	# pip install prospector[with_vulture] --user python
	prospector --no-external-config --output-format pylint

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

openlogs:
	open "https://console.cloud.google.com/logs/viewer?project=$(APPID)&resource=gae_app%2Fmodule_id%2Fdefault%2Fversion_id%2Fdev-`whoami`&minLogLevel=0&expandAll=false&serviceId=default&versionId=dev-`whoami`&logName=projects%2Fhuwawi2%2Flogs%2Fappengine.googleapis.com%252Frequest_log"

opendev:
	open https://dev-`whoami`-dot-$(OPENAPPID).appspot.com$(DEVPAGE)

test:
	TESTHOST=dev-`whoami`-dot-$(OPENAPPID).appspot.com make resttest

resttest:
	sh -c "PYTHONPATH=lib/huTools-checkout:lib/appengine-toolkit:$(MYPYTHONPATH) python $(RESTTESTSUITE) --hostname=$(TESTHOST)"

# pull logs from server
# 4 for CRITICAL, 3 for ERROR, 2 for WARNING, 1 for INFO, 0 for DEBUG
LOG_SEVERITY?=2
LOG_DAYS?=5
request_logs:
	appcfg.py --oauth2 request_logs --module workers -V standard -A $(APPID) --severity=$(LOG_SEVERITY) --include_all -n $(LOG_DAYS) . request_workers.log
	appcfg.py --oauth2 request_logs -V production -A $(APPID) --severity=$(LOG_SEVERITY) --include_all -n $(LOG_DAYS) . request_production.log
	appcfg.py --oauth2 request_logs -V dev-`whoami` -A $(APPID) --include_all -n $(LOG_DAYS) request_dev-`whoami`.log


# beautify source code
fixup:
	autopep8 --global-config=/dev/null --recursive --in-place --pep8-passes 2000 --max-line-length=110 -a -a --experimental --ignore=E711,E712,E401 *.py modules/ tests/ lib/CentralServices/cs
	# Tailing Whitespace
	find modules -name '*.py' -print0 | xargs -0 perl -pe 's/[\t ]+$$//g' -i
	find templates -name '*.html' -print0 | xargs -0 perl -pe 's/[\t ]+$$//g' -i
	find text -name '*.markdown' -print0 | xargs -0 perl -pe 's/[\t ]+$$//g' -i
	# Tabs in Templates

# some stats about this project
stats:
	sloccount $(PYCODE_FILES)
	cloc --unicode templates/ $(PYCODE_FILES) $(JSCODE_FILES)

# Defaults for gaetk appengine applications

# Use something like this at the bottom your Makefile:

# [your defs]
# -include ./lib/appengine-toolkit/make2017/include.mk
# boot:
#	pip install --upgrade --target lib/site-packages -r requirements.txt
# 	git submodule update --init
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
	flake8 --builtins=_ --max-line-length=110 --ignore=E711,E712,E722,E741,N801,C901 $(PYCODE_FILES)
	# pip install prospector[with_vulture] --user python
	PYTHONPATH=$(MYPYTHONPATH) prospector --no-external-config --output-format pylint

# put onto dev-server run tests
deploy:
	-$(MAKE) code
	-$(MAKE) deploy_predeploy
	$(APPCFG) update -A $(APPID) -V dev-`whoami` .
	-$(MAKE) deploy_postdeploy
	TESTHOST=dev-`whoami`-dot-$(OPENAPPID).appspot.com $(MAKE) resttest
	$(MAKE) check
	$(MAKE) unittest
	$(MAKE) opendev

deploy_predeploy:
	echo "deploy_predeploy - this can be overwritten in the project Makefile"
deploy_postdeploy:
	echo "deploy_postdeploy - this can be overwritten in the project Makefile"

code:
	# echo "should build javascript etc.
	echo "doing code"
	[ -f ./js_src/Makefile ] && (cd js_src; $(MAKE) code)
code_production: code
	# echo "should minify javascript etc."
	[ -f ./js_src/Makefile ] && (cd js_src; $(MAKE) code_production)

# put onto staging server, run tests, then put onto production server
deploy_production:
	# wir legen ein komplett neues tmp Verzeichnis mit einem sauberen Checkout an und gehen von da weiter
	rm -Rf tmp
	mkdir tmp
	(cd tmp ; git clone --branch production --recurse-submodules git@github.com:hudora/$(REPOSNAME).git)
	(cd tmp/$(REPOSNAME) ; git checkout production ; $(MAKE) boot; NODE_ENV=production $(MAKE) dependencies)
	(cd tmp/$(REPOSNAME) ; (date +"%y%m%d"; git show-ref --hash=7 refs/remotes/origin/production)|tr -d '\n' > version.txt)
	(cd tmp/$(REPOSNAME) ; curl https://$(OPENAPPID).appspot.com/version.txt > lastversion.txt)
	(cd tmp/$(REPOSNAME) ; $(MAKE) code_production)
	(cd tmp/$(REPOSNAME) ; $(MAKE) deploy_production_predeploy)
	# Erst getaggte Version hochladen
	-$(APPCFG) update -A $(APPID) -V "v`cat tmp/$(REPOSNAME)/version.txt`" tmp/$(REPOSNAME)
	# Dann testen
	(cd tmp/$(REPOSNAME) ; TESTHOST="v`cat version.txt`"-dot-$(OPENAPPID).appspot.com $(MAKE) resttest)
	(cd tmp/$(REPOSNAME) ; $(MAKE) deploy_production_posttest)
	# Wenn das geklappt hat: produktionsversion aktivieren.
	$(APPCFG) update -A $(APPID) -V $(PRODUCTIONNAME) tmp/$(REPOSNAME)
	(cd tmp/$(REPOSNAME) ; $(MAKE) deploy_production_postdeploy)
	# Meldung per Slack
	curl -X POST --data-urlencode 'payload={"channel": "#development", "username": "webhookbot", "text": "<$(PRODUCTIONURL)> neu deployed"}' https://hooks.slack.com/services/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
	# Änderungen in der Console auflisten
	# (cd tmp/$(REPOSNAME) ; git log --pretty='* %s (%ae)' `cut -c 7-99 lastversion.txt`..`cut -c 7-99 version.txt`)
	(cd tmp/$(REPOSNAME) ; $(MAKE) deploy_production_finish)
	# Show logfile
	(cd tmp/$(REPOSNAME) ; $(MAKE) openlogs_production)

deploy_production_predeploy:
	echo "deploy_production_predeploy - this can be overwritten in the project Makefile"
deploy_production_posttest:
	echo "deploy_production_posttest - this can be overwritten in the project Makefile"
deploy_production_postdeploy:
	echo "deploy_production_postdeploy - this can be overwritten in the project Makefile"
deploy_production_finish:
	echo "deploy_production_finish - this can be overwritten in the project Makefile"

openlogs:
	open "https://console.cloud.google.com/logs/viewer?project=$(OPENAPPID)&resource=gae_app%2Fmodule_id%2Fdefault%2Fversion_id%2Fdev-`whoami`&minLogLevel=&expandAll=false&key1=default&key2=dev-`whoami`&logName=projects%2F$(OPENAPPID)%2Flogs%2Fappengine.googleapis.com%252Frequest_log"
openlogs_production:
	open "https://console.cloud.google.com/logs/viewer?project=$(OPENAPPID)&resource=gae_app%2Fmodule_id%2Fdefault%2Fversion_id%2Fproduction&minLogLevel=400&expandAll=false&key1=default&logName=projects%2F$(OPENAPPID)%2Flogs%2Fappengine.googleapis.com%252Frequest_log"

opendev:
	open https://dev-`whoami`-dot-$(OPENAPPID).appspot.com$(DEVPAGE)

test:
	TESTHOST=dev-`whoami`-dot-$(OPENAPPID).appspot.com make resttest

resttest:
	sh -c "PYTHONPATH=lib/huTools-checkout:lib/appengine-toolkit:$(MYPYTHONPATH) python $(RESTTESTSUITE) --hostname=$(TESTHOST)"
	-$(MAKE) resttest_finish
resttest_finish:
	echo "resttest_finish - this can be overwritten in the project Makefile"

# pull logs from server
# 4 for CRITICAL, 3 for ERROR, 2 for WARNING, 1 for INFO, 0 for DEBUG
LOG_SEVERITY?=2
LOG_DAYS?=5
request_logs:
	$(APPCFG) request_logs --module workers -V standard -A $(APPID) --severity=$(LOG_SEVERITY) --include_all -n $(LOG_DAYS) . request_workers.log
	$(APPCFG) request_logs -V production -A $(APPID) --severity=$(LOG_SEVERITY) --include_all -n $(LOG_DAYS) . request_production.log
	$(APPCFG) request_logs -V dev-`whoami` -A $(APPID) --include_all -n $(LOG_DAYS) request_dev-`whoami`.log


# beautify source code
fixup:
	autopep8 --global-config=/dev/null --recursive --in-place --pep8-passes 2000 --max-line-length=110 -a -a --experimental --ignore=E711,E712,E401 *.py modules/ tests/ lib/CentralServices/cs
	# Tailing Whitespace
	find modules -name '*.py' -print0 | xargs -0 perl -pe 's/[\t ]+$$//g' -i
	find templates -name '*.html' -print0 | xargs -0 perl -pe 's/[\t ]+$$//g' -i
	find text -name '*.markdown' -print0 | xargs -0 perl -pe 's/[\t ]+$$//g' -i
	# Tabs in Templates

unittest:
	echo can be overwritten

precommit: dependencies fixup check unittest deploy

# some stats about this project
stats:
	sloccount $(PYCODE_FILES)
	cloc --unicode templates/ $(PYCODE_FILES) $(JSCODE_FILES)
	# cloc `git ls-files | grep -v lib`

.PHONY: doc deploy_production_pretest deploy_production_posttest deploy_production_postdeploy code code_production


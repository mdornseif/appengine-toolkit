GAE_VERSION=1.9.18

# we don't want to know about:
# [C0103(invalid-name), ] Invalid constant name "application"
# [C0330(bad-continuation), ] Wrong continued indentation.
# [E1103(maybe-no-member), shop_link] Instance of 'list' has no 'nachfolger_ist' member (but some types could not be inferred)
# [R0201(no-self-use), ArtikelMultiStammdatenHandler.get] Method could be a function
# [R0903(too-few-public-methods), gaetk_Snippet] Too few public methods (0/2)
# [R0904(too-many-public-methods), ShowKategorie] Too many public methods (22/20)
# [W0142(star-args), CheckoutHandler.get] Used * or ** magic
# [W0201(attribute-defined-outside-init), wwwHandler.default_template_vars] Attribute 'title' defined outside __init__
# [W0212(protected-access)] we know what we are doing
# [W0221(arguments-differ), ShowLieferschein.get] Arguments number differs from overridden method
# [W0232(no-init), gaetk_Snippet] Class has no __init__ method
# [W0703(broad-except), show_snippet] Catching too general exception Exception]

PYLINT_ARGS= "--msg-template={path}:{line}: [{msg_id}({symbol}), {obj}] {msg}" \
			 -rn --ignore=config.py \
             --dummy-variables-rgx="_|dummy" \
             --generated-members=request,response,data,_fields,errors \
             --ignored-classes=Struct,Model,google.appengine.api.memcache,google.appengine.api.files,google.appengine.ext.ndb \
             --no-docstring-rgx="(__.*__|get|post|head)" \
             --max-line-length=$(LINT_LINE_LENGTH) \
             --good-names=application \
             --disable=C0103,C0330 \
             --disable=E1103 \
             --disable=R0201,R0903,R0904 \
             --disable=W0142,W0201,W0212,W0221,W0232,W0232,W0703

LINT_FILES= modules/ tests/ *.py lib/appengine-toolkit/gaetk/login.py lib/appengine-toolkit/gaetk/handler.py lib/appengine-toolkit/gaetk/defaulthandlers.py lib/CentralServices/cs/huwawi*.py

LINT_LINE_LENGTH= 110
LINT_FLAKE8_ARGS= --max-complexity=12 --builtins=_ --exclude=appengine_config.py --max-line-length=$(LINT_LINE_LENGTH) --ignore=E711,E712
MYPYTHONPATH= lib/google_appengine:lib/google_appengine/lib/jinja2-2.6:./lib/google_appengine/lib/webob-1.2.3

default: check

# Install AppEngine SDK locally so pyLint und pyFlakes find it
lib/google_appengine/google/__init__.py:
	curl -s -O https://storage.googleapis.com/appengine-sdks/featured/google_appengine_$(GAE_VERSION).zip
	unzip -q google_appengine_$(GAE_VERSION).zip
	rm -Rf lib/google_appengine
	mv google_appengine lib/
	rm google_appengine_$(GAE_VERSION).zip

checknodeps:
	flake8 $(LINT_FLAKE8_ARGS) $(LINT_FILES)
	sh -c 'PYTHONUNBUFFERED=1 LC_ALL=en_US.UTF-8 PYTHONPATH=`python config.py`:$(MYPYTHONPATH) pylint $(PYLINT_ARGS) $(LINT_FILES)'

check: lib/google_appengine/google/__init__.py checknodeps

deploy:
	# appcfg.py update .
	appcfg.py --oauth2 update -V dev-`whoami` -A $(APPID) .
	TESTHOST=dev-`whoami`-dot-$(OPENAPPID).appspot.com make resttest
	make opendev

deploy_production:
	# wir legen ein komplett neues tmp verzeichnis mit einem sauberen checkout an und gehen von da weiter
	rm -Rf tmp
	mkdir tmp
	(cd tmp ; git clone git@github.com:hudora/$(REPOSNAME).git)
	(cd tmp/$(REPOSNAME) ; git checkout production ; make boot dependencies)
	(cd tmp/$(REPOSNAME) ; git show-ref --hash=7 refs/remotes/origin/production > version.txt)
	# Erst getaggte Version hochladen
	-appcfg.py --oauth2 update -V "v`cat tmp/$(REPOSNAME)/version.txt`" -A $(APPID) tmp/$(REPOSNAME)
	# Dann testen
	(cd tmp/$(REPOSNAME) ; TESTHOST="v`cat version.txt`"-dot-$(OPENAPPID).appspot.com make resttest)
	# Wenn das geklappt hat: produktionsversion aktivieren.
	appcfg.py --oauth2 update -V production -A $(APPID) tmp/$(REPOSNAME)
	curl -X POST --data-urlencode 'payload={"channel": "#general", "username": "webhookbot", "text": "<http://express.hudora.de> neu deployed"}' https://hooks.slack.com/services/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

fixup:
	# Tailing Whitespace
	find modules -name '*.py' -print0 | xargs -0 perl -pe 's/[\t ]+$$//g' -i
	find templates -name '*.html' -print0 | xargs -0 perl -pe 's/[\t ]+$$//g' -i
	find text -name '*.markdown' -print0 | xargs -0 perl -pe 's/[\t ]+$$//g' -i
	# Tabs in Templates
	find templates -name '*.html' -print0 | xargs -0 perl -pi -e 'print expand $$_' -i
	find text -name '*.markdown' -print0 | xargs -0 perl -pi -e 'print expand $$_' -i
	# line endings
	find templates -name '*.html' -print0 | xargs -0 perl -pi -e 's/\r\n/\n/g;s/\r/\n/g'
	find text -name '*.markdown' -print0 | xargs -0 perl -pi -e 's/\r\n/\n/g;s/\r/\n/g'

dependencies: clean
	git submodule update --init

clean:
	find . -name '*.pyc' -or -name '*.pyo' -delete

openlogs:
	open "https://appengine.google.com/logs?app_id=e%7E$(OPENAPPID)&version_id=dev-`whoami`"

opendev:
	open http://dev-`whoami`-dot-$(OPENAPPID).appspot.com/

test:
	TESTHOST=dev-`whoami`-dot-$(OPENAPPID).appspot.com make resttest

RESTTESTSUITE?=tests/resttest.py
resttest:
	sh -c "PYTHONPATH=lib/huTools-checkout:lib/appengine-toolkit python $(RESTTESTSUITE) --hostname=$(TESTHOST) --credentials-user=$(CREDENTIALS_USER)"

.PHONY: deploy pylint dependencies_for_check_target clean check dependencies resttest

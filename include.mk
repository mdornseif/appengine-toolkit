GAE_VERSION=1.9.40
PRODUCTIONURL?= https://$(APPID).appspot.com/
PRODUCTIONNAME?= production
DEVPAGE?= /
OPENAPPID?= $(APPID)


# we don't want to know about:
# [C0103(invalid-name), ] Invalid constant name "application"
# [C0121(singleton-comparison)] clashes with NDB
# [C0201(consider-iterating-dictionary) - explicit is better than implicid
# [C0330(bad-continuation), ] Wrong continued indentation.
# [C0412(ungrouped-imports)] we sort differently
# [E1103(maybe-no-member), shop_link] Instance of 'list' has no 'nachfolger_ist' member (but some types could not be inferred)
# [E1120(no-value-for-parameter)] Fails with ndb decorators
# [R0201(no-self-use), ArtikelMultiStammdatenHandler.get] Method could be a function
# [R0204(redefined-variable-type)] - does not work with ndb
# [R0901(too-many-ancestors)]
# [R0903(too-few-public-methods), gaetk_Snippet] Too few public methods (0/2)
# [R0904(too-many-public-methods), ShowKategorie] Too many public methods (22/20)
# [R0913(too-many-arguments),
# [R0921(abstract-class-not-used), AuditLog] Abstract class not referenced
# [R0922(abstract-class-little-used)]
# [W0108(unnecessary-lambda)] üblicherweise wissen wir da, was wir tun.
# [W0142(star-args), CheckoutHandler.get] Used * or ** magic
# [W0201(attribute-defined-outside-init), wwwHandler.default_template_vars] Attribute 'title' defined outside __init__
# [W0212(protected-access)] we know what we are doing
# [W0221(arguments-differ), ShowLieferschein.get] Arguments number differs from overridden method
# [W0232(no-init), gaetk_Snippet] Class has no __init__ method
# [W0631(undefined-loop-variable)] so far ONLY false positives
# [W0703(broad-except), show_snippet] Catching too general exception Exception]
# [W1306(missing-format-attribute)] - kommt nicht mit Objekten zurecht
# [I0011(locally-disabled), ] Locally disabling unused-argument (W0613)ı
# I0013(file-ignored)

PYLINT_ARGS= "--msg-template={path}:{line}: [{msg_id}({symbol}), {obj}] {msg}" \
			 -rn --ignore=config.py,huwawi_a_models.py,lib \
             --dummy-variables-rgx="_|dummy" \
             --generated-members=request,response,data,_fields,errors \
             --ignored-classes=Struct,Model,google.appengine.api.memcache,google.appengine.api.files,google.appengine.ext.ndb \
			 --additional-builtins=_ \
			 --ignore-imports=yes \
             --no-docstring-rgx="(__.*__|get|post|head|txn)" \
             --max-line-length=$(LINT_LINE_LENGTH) \
             --max-locals=20 --max-attributes=20 --max-returns=8 \
             --good-names=application \
             --disable=C0103,C0121,C0201,C0330,C0412 \
             --disable=E1103,E1120 \
             --disable=R0201,R0204,R0901,R0903,R0904,R0913,R0921,R0922 \
             --disable=W0108,W0142,W0201,W0212,W0221,W0232,W0232,W0511,W0631,W0703,W1306 \
             --disable=I0011,I0013
# PYLINT_ARGS_ADDON?= --import-graph=import.dot -ry
LINT_FILES?= modules/ tests/*.py *.py lib/CentralServices/cs lib/appengine-toolkit/gaetk

LINT_LINE_LENGTH= 110
LINT_FLAKE8_ARGS= --max-complexity=12 --builtins=_ --exclude=appengine_config.py,lib/*.py --max-line-length=$(LINT_LINE_LENGTH) --ignore=E711,E712
MYPYTHONPATH := $(MYPYTHONPATH):lib/google_appengine:lib/google_appengine/lib/jinja2-2.6:./lib/google_appengine/lib/webob-1.2.3:./lib/google_appengine/lib/django-1.5:./lib/google_appengine/lib/webapp2-2.5.2

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
	# --disable=W0511 no TODOs
	sh -c 'PYTHONUNBUFFERED=1 LC_ALL=en_US.UTF-8 PYTHONPATH=`python config.py`:$(MYPYTHONPATH) pylint --disable=W0511 $(PYLINT_ARGS) $(PYLINT_ARGS_ADDON) $(LINT_FILES)'
	# TODOs anzeigen
	sh -c 'PYTHONUNBUFFERED=1 LC_ALL=en_US.UTF-8 PYTHONPATH=`python config.py`:$(MYPYTHONPATH) pylint $(PYLINT_ARGS) $(PYLINT_ARGS_ADDON) --disable=all --enable=W0511 $(LINT_FILES)'

check: lib/google_appengine/google/__init__.py checknodeps

deploy:
	# appcfg.py update .
	appcfg.py update -A $(APPID) -V dev-`whoami` .
	TESTHOST=dev-`whoami`-dot-$(OPENAPPID).appspot.com make resttest
	make opendev

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

fixup:
	autopep8 --global-config=/dev/null --recursive --in-place --pep8-passes 2000 --max-line-length=110 -a -a --experimental --ignore=E711,E712,E401 *.py modules/ tests/ lib/CentralServices/cs
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
	open "https://appengine.google.com/logs?app_id=$(APPID)&version_id=dev-`whoami`&severity_level_override=0&severity_level=3"

opendev:
	open https://dev-`whoami`-dot-$(OPENAPPID).appspot.com$(DEVPAGE)

test:
	TESTHOST=dev-`whoami`-dot-$(OPENAPPID).appspot.com make resttest

RESTTESTSUITE?=tests/resttest.py
resttest:
	sh -c "PYTHONPATH=lib/huTools-checkout:lib/appengine-toolkit:$(MYPYTHONPATH) python $(RESTTESTSUITE) --hostname=$(TESTHOST)"

code: ;

.PHONY: deploy pylint dependencies_for_check_target clean check dependencies resttest code

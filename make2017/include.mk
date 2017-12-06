# in the main Makefole please set `APPID`

# This file includes all kinds of default defenitions.

# see https://cloud.google.com/appengine/docs/standard/python/release-notes
GAE_VERSION=1.9.51
PRODUCTIONURL?= https://$(APPID).appspot.com/
# name of the version running public facing code and the git branch
PRODUCTIONNAME?= production
# page to use
DEVPAGE?= /
OPENAPPID?= $(APPID)
RESTTESTSUITE?= tests/resttest.py
PYCODE_FILES?= modules/ tests/*.py *.py lib/CentralServices/cs lib/appengine-toolkit/gaetk
LINT_FILES?= $(PYCODE_FILES)
JSCODE_FILES?= js_src/src/


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

LINT_LINE_LENGTH= 110
LINT_FLAKE8_ARGS= --max-complexity=12 --builtins=_ --exclude=appengine_config.py,lib/*.py --max-line-length=$(LINT_LINE_LENGTH) --ignore=E711,E712
MYPYTHONPATH?= lib/google_appengine:lib/google_appengine/lib/jinja2-2.6:./lib/google_appengine/lib/webob-1.2.3:./lib/google_appengine/lib/webapp2-2.5.2
APPCFG?=./lib/google_appengine/appcfg.py --oauth2

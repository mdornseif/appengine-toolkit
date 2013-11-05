GAE_VERSION=1.8.6

LINT_LINE_LENGTH= 110
LINT_FLAKE8_ARGS= --max-complexity=27 --builtins=_ --max-line-length=$(LINT_LINE_LENGTH) --exclude=mywebapp2.py,gaesessions.py,gaetk/__init__.py
GOOD_NAMES=_,setUp,application,fd,gaetk_replication_SQL_INSTANCE_NAME,gaetk_replication_SQL_DATABASE_NAME,gaetk_replication_SQL_QUEUE_NAME

# pyLint
#   W0142 = *args and **kwargs support
# Pointless whinging
#   W0603 = Using the global statement
#   R0201 = Method could be a function
#   W0212 = Accessing protected attribute of client class
#   W0232 = Class has no __init__ method
#   W0212 = Access to a protected member _rev of a client class
# Mistakes in Parsing the AppEngine Source
#   E1103: %s %r has no %r member (but some types could not be inferred)
# Usually makes sense for webapp.Handlers & Friends.
#   W0221 Arguments number differs from %s method
# In Python versions < 2.6 all Exceptions inherited from Exception. py2.6 introduced BaseException
# On AppEngine we do not care much about the "serious" Exception like KeyboardInterrupt etc.
#   W0703 Catch "Exception"
#   R0903 Too few public methods - pointless for db.Models
# Pylint wirft folgenden Fehler nach keinem erkennbaren System.
#   W0404: 24: Reimport 'views.wufoo' (imported line 27)
# Other
#   R0924 Badly implemented Container - wtf_forms ist da der Übeltäter
#   R0922 'Abstract class is only referenced 1 times'
# Unused Reports
#   RP0401 External dependencies
#   RP0402 Modules dependencies graph
#   RP0101 Statistics by type
#   RP0701 Raw metrics
#   RP0801 Duplication

GOOD_NAMES=app,application

# Dateien, die wir strenger checken.
STRICT_LINT_FILES= gaetk/
# Alle Projektdateien
LINT_FILES= $(STRICT_LINT_FILES)

PYLINT_ARGS= --output-format=parseable -rn --ignore=mywebapp2.py,gaesessions.py,gaetk/__init__.py \
             --deprecated-modules=regsub,string,TERMIOS,Bastion,rexec,husoftm,hujson \
             --ignored-classes=Struct,Model,google.appengine.api.memcache,google.appengine.api.files \
             --dummy-variables-rgx="_|dummy|abs_url" \
             --good-names=$(GOOD_NAMES) \
             --generated-members=request,response,data,_fields,errors \
             --additional-builtins=_ \
             --max-line-length=$(LINT_LINE_LENGTH) \
             --max-attributes=8 \
             --max-locals=25 \
             --max-public-methods=30 \
             --min-similarity-lines=6 \
             --disable=W0142 \
             --disable=W0603 \
             --disable=R0201 \
             --disable=W0212 \
             --disable=W0232 \
             --disable=W0212 \
             --disable=E1103 \
             --disable=W0221 \
             --disable=W0703 \
             --disable=R0924 \
             --disable=R0903 \
             --disable=W0404 \
             --disable=R0922 \
             --disable=I0011,W0201,W0403 \
             --disable=RP0401,RP0402,RP0101,RP0701,RP0801
#              --class-rgx=\(ab_\|audit_\|aui_\|bi_\|e_\|ent_\|fk_\|gs_\|ic_\|k_\|kui\|p_\|pr_\|sui_\)?[A-Z_][a-zA-Z0-9]+   \


check: google_appengine pythonenv
	./pythonenv/bin/flake8 $(LINT_FLAKE8_ARGS) $(LINT_FILES)
	#sh -c 'LC_ALL=en_US.UTF-8 PYTHONPATH=google_appengine ./pythonenv/bin/pylint $(PYLINT_ARGS) $(STRICT_LINT_FILES)'
	-sh -c 'LC_ALL=en_US.UTF-8 PYTHONPATH=google_appengine ./pythonenv/bin/pylint $(PYLINT_ARGS) $(LINT_FILES)'

dependencies: pythonenv google_appengine

google_appengine:
	curl -s -O http://googleappengine.googlecode.com/files/google_appengine_$(GAE_VERSION).zip
	#/google/__init__.py:
	unzip -q google_appengine_$(GAE_VERSION).zip
	rm -Rf google_appengine_$(GAE_VERSION).zip

clean:
	rm -rf google/__init__.py pythonenv
	find . -name '*.pyc' -or -name '*.pyo' -delete

TEST_ARGS=-v -s --without-sandbox --with-gae --gae-lib-root=google_appengine --gae-application=./examples
test: dependencies
	PYTHONPATH=examples nosetests $(TEST_ARGS) tests/*.py

pythonenv:
	virtualenv --python=python2.7 --no-site-packages pythonenv
	./pythonenv/bin/python pythonenv/bin/pip -q install --upgrade nose nosegae WebTest gaetestbed coverage mock fixture flake8 pylint
	./pythonenv/bin/python pythonenv/bin/pip -q install --upgrade jinja2 webapp2 simplejson
	./pythonenv/bin/python pythonenv/bin/pip -q install --upgrade huTools

.PHONY: clean check

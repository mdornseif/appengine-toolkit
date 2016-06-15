# encoding: utf-8
"""
DSL zur Beschreibung von REST-interfaces, angelehnt an https://gist.github.com/805540

Copyright (c) 2011, 2013, 2016 HUDORA. All rights reserved.
File created by Philipp Benjamin Koeppchen on 2011-02-23
"""

import logging
import optparse
import os
import sys
import time
import urlparse
import xml.dom.minidom

from collections import Counter
from functools import partial
from pprint import pprint

import concurrent.futures
import huTools.http._httplib2  # for ServerNotFoundError
import requests

from huTools import hujson2
from huTools.http import fetch
from requests.auth import HTTPBasicAuth

BLACK, RED, GREEN, YELLOW, BLUE, MAGENTA, CYAN, WHITE = range(8)
FOREGROUND = 30
RESET_SEQ = "\033[0m"
COLOR_SEQ = "\033[1;%dm"

MAX_WORKERS = 6

# save slowest access to each URL
slowstats = Counter()
alllinks = Counter()
oklinks = set()
brokenlinks = {}

if False:
    MAX_WORKERS = 1
    # these two lines enable debugging at httplib level (requests->urllib3->httplib)
    # you will see the REQUEST, including HEADERS and DATA, and RESPONSE with HEADERS but without DATA.
    # the only thing missing will be the response.body which is not logged.
    import httplib
    httplib.HTTPConnection.debuglevel = 1
    logging.getLogger().setLevel(logging.DEBUG)
    requests_log = logging.getLogger("requests.packages.urllib3")
    requests_log.setLevel(logging.DEBUG)
    requests_log.propagate = True


def colored(text, color):
    """Färbt den Text mit Terminalsequenzen ein.

    >>> colored('whatever', RED)
    '\033[1;32mwhatever\033[0m' # wuerde dann in rot erscheinen, wenn man es ausgibt
    """
    start = COLOR_SEQ % (FOREGROUND + color)
    return start + text + RESET_SEQ


class Response(object):
    """Repräsentiert das Ergebnis einer REST-Anfrage.
    Mittels responds_* koennen zusicherungen geprueft werden:

    r.responds_http_status(200)
    r.responds_html()
    """

    def __init__(self, client, method, url, status, headers, content, duration, response):  # pylint: disable=R0913
        self.client = client
        self.method = method
        self.url = url
        self.status = status
        self.headers = headers
        self.content = content
        self.errors = 0
        self.duration = duration
        self.response = response

    def fail(self, message):
        """Negatives Ergebnis einer Zusicherung."""
        self.errors += 1
        url = self.url
        if self.response.url != url:
            url = u'%r (->%r)' % (url, self.response.url)
        print u'%s %s -> %s: %s' % (self.method, url, colored("FAIL", RED), message)
        if self.response.history:
            for hres in self.response.history:
                print u'->', hres.url
        print '=' * 50
        print '<<<',
        pprint(self.headers)
        if self.client.debug:
            print '<<<',
            print self.content
        else:
            print repr(self.content[:50])
        print '=' * 50
        print

    def succeed(self, message):
        """Positives Ergebnis einer Zusicherung."""
        if self.client.debug:
            print '%s %s -> %s: %s' % (self.method, self.url, colored("SUCCESS", GREEN), message)

    def expect_condition(self, condition, message):
        """sichert eine boolsche Bedingung zu. sollte nicht direkt aufgerufen werden"""
        if not self.errors:
            if not condition:
                self.fail(message)
            else:
                self.succeed(message)
        # else: ignore

    # low-level-beschreibungen der erwartungen
    def responds_http_status(self, expected_status):
        """sichert zu, dass mit dem gegebenen HTTP-status geantwortet wurde."""
        self.expect_condition(
            self.status == expected_status,
            'expected status %s, got %s' % (expected_status, self.status))
        return self

    def responds_content_type(self, expected_type):
        """sichert zu, dass mit dem gegebenen Content-Type geantwortet wurde."""
        actual_type = self.headers.get('content-type')
        # evtl wird dem contenttype ein encoding nachgestellt, dies soll abgetrennt werden
        actual_type = actual_type.split(';')[0]
        self.expect_condition(
            actual_type == expected_type,
            'expected content type %r, got %r' % (expected_type, actual_type))
        return self

    def converter_succeeds(self, converter, message):
        """sichert zu, dass content mittels converter(self.content) ohne exception konvertiert werden kann"""
        if not self.errors:
            try:
                converter(self.content)
            except Exception:
                self.fail(message)
            else:
                self.succeed(message)

    # high-level-beschreibungen
    def responds_normal(self):
        """sichert zu, dass ein Dokument gefunden wurde."""
        self.responds_http_status(200)

    def responds_not_found(self):
        """sichert zu, dass kein Dokument gefunden wurde."""
        self.responds_http_status(404)
        return self

    def responds_access_denied(self):
        """sichert zu, dass der Zugriff verweigert wurde."""
        self.responds_http_status(401)
        return self

    def responds_forbidden(self):
        """sichert zu, dass der Zugriff verweigert wurde."""
        self.responds_http_status(403)
        return self

    def responds_with_content_location(self, expected_location):
        """sichert zu, dass die Antwort einen location-header hat."""
        content_location = self.headers.get('content-location', '')
        self.expect_condition(
            content_location.endswith(expected_location),
            'expected content-location to end with %r, got %r.' % (expected_location, content_location))
        return self

    def responds_with_valid_links(self):
        if NO_LINK_VALIDATION:
            return self
        links = extract_links(self.content, self.url)
        for link in links:
            if link in brokenlinks:
                # no need to check again
                brokenlinks.setdefault(link, set()).add(self.url)
            elif link not in oklinks:
                try:
                    r = requests.get(link, headers=dict(
                            referer=self.url, Cookie=self.headers.get('set-cookie', '')
                            )
                    )
                    status = r.status_code
                except (IOError, huTools.http._httplib2.ServerNotFoundError):
                    status = 600
                except (huTools.http._httplib2.RedirectLimit):
                    status = 700

                if status == 200:
                    oklinks.add(link)
                else:
                    brokenlinks.setdefault(link, set()).add(self.url)
                if status == 700:
                    print 'too many redirects on %s' % link
                self.expect_condition(
                    status in (200, 401, 405, 700), 'invalid (%r) link to %r' % (status, link))

    def responds_with_valid_html(self):
        if NO_HTML_VALIDATION:
            return self
        try:
            from tidylib import tidy_document
            document, errors = tidy_document(
                self.content, options={'numeric-entities':1, 'input-encoding': 'utf8'})
            if errors:
                print "### {0} see http://validator.w3.org/nu/?doc={0}".format(self.url)
                contentlines = self.content.split('\n')
                for errorline in errors.split('\n'):
                    address = errorline.split('-')[0]
                    errortext = '-'.join(errorline.split('-')[1:])
                    if address:
                        line, linenr, column, colnr = address.split()
                        if 'trimming empty <p' not in errortext and 'inserting implicit ' not in errortext:
                            print "line {0}:{1} {2}".format(linenr, colnr, errortext),
                            print repr(contentlines[int(linenr)-1])
        except (ImportError, OSError):
            pass
        return self


class TestClient(object):
    """Hilfsklasse zum Ausfuehren von HTTP-Requests im Rahmen von Tests."""
    def __init__(self, host, users, debug=False):
        self.debug = debug
        self.host = host
        self.authdict = {}
        self.responses = []
        self.protocol = 'https'
        self.sessions = {None: requests.Session()}
        self.sessions[None].trust_env = False  # avoid reading .netrc!
        self.queue = []  # contains URLs to be checked, kwargs, and checks to be done

        for user in users:
            key, creds = user.split('=', 1)
            self.add_credentials(key, creds)

    def add_credentials(self, auth, creds):
        """Stellt dem Client credentials zur Verfügung, die in GET genutzt werden können.

        auth: key der Credentials
        creds: HTTP-Credentials in der Form 'username:password'
        """
        self.authdict[auth] = creds
        self.sessions[auth] = requests.Session()

    def GET(self, path, auth=None, accept=None, headers={}, **kwargs):
        """Führt einen HTTP-GET auf den gegebenen [path] aus.
        Nutzt dabei ggf. die credentials zu [auth] und [accept]."""
        if type(auth) == type([]):
            raise ValueError("unsuitable auth %r" % auth)
        if auth and auth not in self.authdict:
            raise ValueError("Unknown auth '%s'" % auth)

        myheaders = {'User-Agent': 'resttest/%s' % requests.utils.default_user_agent()}
        if accept:
            myheaders['Accept'] = accept
        myheaders.update(headers)

        url = urlparse.urlunparse((self.protocol, self.host, path, '', '', ''))
        start = time.time()
        if self.authdict.get(auth):
            r = self.sessions[auth].get(
                url,
                headers=myheaders,
                auth=HTTPBasicAuth(*self.authdict.get(auth).split(':')),
                timeout=300,
                **kwargs)
        else:
            r = self.sessions[auth].get(
                url,
                headers=myheaders,
                timeout=300,
                **kwargs)
        duration = int((time.time() - start) * 1000)
        slowstats[url] = duration

        response = Response(self, 'GET:%s' % auth, url, r.status_code, r.headers, r.content, duration, r)
        self.responses.append(response)
        return response

    # New API

    def check(self, *args, **kwargs):
        for url in args:
            if url.endswith('.json'):
                checkers = [responds_json]
            elif url.endswith('.pdf'):
                checkers = [responds_pdf]
            elif url.endswith('.xml'):
                checkers = [responds_xml]
            elif url.endswith('.csv') or url.endswith('.xls'):
                checkers = [responds_basic]
            elif url.endswith('txt'):
                checkers = [responds_plaintext]
            else:
                checkers = [responds_html]
            self.queue.append((url, kwargs, checkers))

    def check_allowdeny(self, *args, **kwargs):
        allow = kwargs.get('allow', [])
        if 'allow' in kwargs:
            del kwargs['allow']
        deny = kwargs.get('deny', [])
        if 'deny' in kwargs:
            del kwargs['deny']

        assert len(allow) + len(deny) > 0  # IRGENDWAS muessen wir ja testen

        for auth in allow:
            self.check(*args, auth=auth, **kwargs)
        for auth in deny:
            # 40x detection is messy, because `login: admin` in app.yaml
            # results in redirects to a 200
            myargs = dict(allow_redirects=False, auth=auth)
            myargs.update(kwargs)
            for url in args:
                self.queue.append((url, myargs, [responds_4xx]))

    def check_redirect(self, *args, **kwargs):
        for urldict in args:
            fromurl = urldict.get('url')
            del urldict['url']
            tourl = urldict.get('to')
            del urldict['to']
            myargs = dict(allow_redirects=False)
            myargs.update(kwargs)
            myargs.update(urldict)
            self.queue.append((fromurl, myargs, [partial(responds_redirect, to=tourl)]))

    def check_statuscode(self, *args, **kwargs):
        statuscode = kwargs.get('statuscode')
        if 'statuscode' in kwargs:
            del kwargs['statuscode']

        def responds_closure(response):
            response.expect_condition(
                response.status == statuscode,
                'expected status statuscode, got %s' % response.status)

        for url in args:
            self.queue.append((url, kwargs, [responds_closure]))

    def run_checks(self, max_workers=MAX_WORKERS):
        """run queued checks."""
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {}
            while self.queue:
                url, kwargs, checkers = self.queue.pop()
                futures[executor.submit(self._check_helper, checkers, url, **kwargs)] = url
        for future in concurrent.futures.as_completed(futures):
            # exceptions occure here
            try:
                future.result()
                sys.stdout.flush()
            except:
                print futures[future]
                sys.stdout.flush()
                raise
        finished, not_done = concurrent.futures.wait(futures)
        if not_done:
            print "unfinished:", not_done


    def _check_helper(self, checkers, url, **kwargs):
        response = self.GET(url, **kwargs)
        for checker in checkers:
            checker(response)
        return "%s:%s" % (kwargs.get('auth'), url)

    @property
    def errors(self):
        """Anzahl der fehlgeschlagenen Zusicherungen, die für Anfragen dieses Clients gefroffen wurden."""
        return sum(r.errors for r in self.responses)


def responds_json(response):
    """sichert zu, dass die Antwort ein well-formed JSON-Dokument war."""
    response.responds_http_status(200)
    response.responds_content_type('application/json')
    response.converter_succeeds(hujson2.loads, 'expected valid json')


def responds_xml(response):
    """sichert zu, dass die Antwort ein well-formed XML-Dokument war."""
    response.responds_http_status(200)
    response.responds_content_type('application/xml')
    response.converter_succeeds(xml.dom.minidom.parseString, 'expected valid xml')


def responds_plaintext(response):
    """sichert zu, dass die Antwort plaintext war."""
    response.responds_http_status(200)
    response.responds_content_type('text/plain')


def responds_pdf(response):
    """sichert zu, dass die Antwort ein well-formed PDF-Dokument war."""
    response.responds_http_status(200)
    response.responds_content_type('application/pdf')
    # .startswith('%PDF-1')

def responds_basic(response):
    """sichert zu, dass die Antwort einen vernünftigen Statuscode hat."""
    response.responds_http_status(200)


def responds_html(response):
    """sichert zu, dass die Antwort ein HTML war."""
    response.responds_http_status(200)
    response.responds_content_type('text/html')
    # TODO: delayed HTML validation
    # response.responds_with_valid_html()
    # todo: links responds_with_valid_links


def responds_4xx(response):
    """sichert zu, dass die Antwort ein Denial war."""
    # 40x detection is messy, because `login: admin` in app.yaml
    # results in redirects to a 302
    if response.status == 302:
        # we now generally handle 302 as a form of denial
        return
        # response.expect_condition(
        #    response.headers.get('location').startswith(
        #         'https://www.google.com/accounts/ServiceLogin'),
        #    'expected status 302 redirect to google')
    else:
        response.expect_condition(
            response.status >= 400 and response.status < 500,
            'expected status 4xx, got %s' % response.status)


def responds_redirect(response, to=None):
    """sichert zu, dass die Antwort umleitet."""
    # oder location = self.response.url
    location = urlparse.urlparse(response.headers.get('location', '/')).path
    response.expect_condition(
       (300 <= response.status < 400) and location.startswith(to),
       'expected redirect to %r, got %s:%r' % (
            to,
            response.response.status_code,
            location))


def extract_links(content, url):
    import lxml.html
    links = []
    dom = lxml.html.document_fromstring(content, base_url=url)
    dom.make_links_absolute(url)
    for element, _attribute, link, _pos in dom.iterlinks():
        if link.startswith('http'):
            if element.tag == 'form' and element.get('method'):
                if element.get('method').upper() == 'POST':
                    continue
            links.append(link)
        alllinks[link] += 1
    return links


def get_app_version():
    """Ermittelt die Aktuell zu deployende Version."""
    # Der dümmste YAML parser der Welt.
    for line in open('app.yaml'):
        if line.startswith('version: '):
            version = line.split()[1]
            return version.strip()
    raise RuntimeError("Can't detect version")


def create_testclient_from_cli(default_hostname, users):
    """ Creates a Testclient with it's arguments from the Commandline.

    the CLI understands the options, --hostname, --credentials-user, --credentials-admin, their default
    values are taken from this functions args

    default_hostname: hostname, on wich to run tests, if none is provided via CLI

    returns a `TestClient`
    """
    parser = optparse.OptionParser()
    parser.add_option(
        '-H', '--hostname', dest='hostname',
        help='Hostname, on which the tests should be run',
        default=default_hostname)
    parser.add_option(
        '-u', '--credentials-user', dest='users', action='append', default=[],
        help='user credentials for HTTP Basic Auth')
    parser.add_option(
        '-d', '--debug', dest='debug', default=False, action='store_true')

    opts, args = parser.parse_args()
    if args:
        parser.error('positional arguments are not accepted')

    if os.environ.get('RESTTESTHOST'):
        default_hostname = os.environ.get('RESTTESTHOST')
    # Das `or` sorgen dafür, dass --option='' als 'nicht angegeben' gewertet wird, siehe aufruf im Makefile.

    if users is None:
        users = []
    if opts.users:
        users.extend(opts.users)

    client = TestClient(opts.hostname or default_hostname, users=users, debug=opts.debug)

    return client

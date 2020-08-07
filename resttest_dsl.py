# encoding: utf-8
"""
DSL zur beschreibung von REST-interfaces, angelehnt an https://gist.github.com/805540

Copyright (c) 2011, 2013 HUDORA. All rights reserved.
File created by Philipp Benjamin Koeppchen on 2011-02-23
"""

import optparse
import os
import sys
import time
import urlparse
import xml.dom.minidom

from collections import Counter
from pprint import pprint

import huTools.http._httplib2  # for ServerNotFoundError

from huTools import hujson2
from huTools.http import fetch

BLACK, RED, GREEN, YELLOW, BLUE, MAGENTA, CYAN, WHITE = range(8)
FOREGROUND = 30
RESET_SEQ = "\033[0m"
COLOR_SEQ = "\033[1;%dm"

DEFAULTFAST = int(os.environ.get('DEFAULTFAST_MS', 1500))
TIMEOUT = int(os.environ.get('TIMEOUT', 45))

NO_LINK_VALIDATION = False  # suppress link validation
NO_HTML_VALIDATION = False  # suppress HTML validation

# save slowest access to each URL
alllinks = Counter()


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

    def __init__(self, client, method, url, status, headers, content, duration):  # pylint: disable=R0913
        self.client = client
        self.method = method
        self.url = url
        self.status = status
        self.headers = headers
        self.content = content
        self.errors = 0
        self.duration = duration

    def fail(self, message):
        """Negatives ergebnis einer Zusicherung."""
        self.errors += 1
        print '%s %s -> %s: %s' % (self.method, self.url, colored("FAIL", RED), message)
        print '=' * 50
        print "<<<",
        pprint(self.headers)
        if self.client.debug:
            print "<<<",
            print self.content
        print '=' * 50
        print

    def succeed(self, message):
        """Positives ergebnis einer Zusicherung."""
        if self.client.debug:
            print '%s %s -> %s: %s' % (self.method, self.url, colored("SUCCESS", GREEN), message)

    def expect_condition(self, condition, message):
        """sichert eine boolsche bedingung zu. sollte nicht direkt aufgerufen werden"""
        if not condition:
            self.fail(message)
        else:
            self.succeed(message)

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
        try:
            converter(self.content)
        except Exception:
            self.fail(message)
        else:
            self.succeed(message)

    # high-level-beschreibungen
    def responds_json(self):
        """sichert zu, dass die Antwort ein well-formed JSON-Dokument war."""
        self.responds_http_status(200)
        self.responds_content_type('application/json')
        self.converter_succeeds(hujson2.loads, 'expected valid json')
        return self

    def responds_xml(self):
        """sichert zu, dass die Antwort ein well-formed XML-Dokument war."""
        self.responds_http_status(200)
        self.responds_content_type('application/xml')
        self.converter_succeeds(xml.dom.minidom.parseString, 'expected valid xml')
        return self

    def responds_rssxml(self):
        """sichert zu, dass die Antwort ein well-formed RSS+XML-Dokument war."""
        self.responds_http_status(200)
        self.responds_content_type('application/rss+xml')
        self.converter_succeeds(xml.dom.minidom.parseString, 'expected valid rss+xml')
        return self

    def responds_plaintext(self):
        """sichert zu, dass die Antwort ein Plaintext-Dokument war."""
        self.responds_http_status(200)
        self.responds_content_type('text/plain')
        return self

    def responds_html(self):
        """sichert zu, dass die Antwort ein HTML-Dokument war."""
        self.responds_http_status(200)
        self.responds_content_type('text/html')
        return self

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

    def responds_unauthorized(self):
        """sichert zu, dass der Zugriff verweigert wurde."""
        self.responds_http_status(403)

    def redirects_to(self, expected_url):
        """sichert zu, dass mit einen Redirect geantwortet wurde."""
        location = self.headers.get('location', self.headers.get('content-location', ''))
        self.expect_condition(
            location.endswith(expected_url), 'expected redirect to %s, got %s' % (expected_url, location))

    def responds_with_content_location(self, expected_location):
        """sichert zu, dass die Antwort einen location-header hat."""
        content_location = self.headers.get('content-location', '')
        self.expect_condition(
            content_location.endswith(expected_location),
            'expected content-location to end with %r, got %r.' % (expected_location, content_location))
        return self

    def responds_fast(self, maxduration=DEFAULTFAST):
        """sichert zu, dass der Zugriff schnell geht (unter maxduration ms)."""
        self.expect_condition(
            self.duration <= maxduration,
            'expected answer within %d ms, took %d ms' % (maxduration, self.duration))
        return self

    def responds_with_valid_links(self):
        if NO_LINK_VALIDATION:
            return self
        links = extract_links(self.content, self.url)
        for link in links:
            if link in self.client.brokenlinks:
                # no need to check again
                self.client.brokenlinks[link].add(self.url)
            elif link not in self.client.oklinks:
                try:
                    status, _responseheaders, _content = fetch(
                        link,
                        headers=dict(
                            referer=self.url, Cookie=self.headers.get('set-cookie', '')
                        ),
                        content='', method='GET', multipart=False, ua='', timeout=TIMEOUT)
                except (IOError, huTools.http._httplib2.ServerNotFoundError):
                    status = 600
                except (huTools.http._httplib2.RedirectLimit):
                    status = 700

                if status == 200:
                    self.client.oklinks.add(link)
                else:
                    self.client.brokenlinks.setdefault(link, set()).add(self.url)
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
                self.content, options={'numeric-entities': 1, 'input-encoding': 'utf8'})
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
                            print repr(contentlines[int(linenr) - 1])
        except (ImportError, OSError):
            pass
        return self

    def responds_normal(self, maxduration=DEFAULTFAST, links=True):
        """Normale Seite: Status 200, HTML, schnelle Antwort, keine kaputten Links"""
        self.responds_html()
        # self.responds_with_valid_html()
        self.responds_fast(maxduration)
        if links:
            self.responds_with_valid_links()
        return self

    def responds_with_html_to_valid_auth(self):
        """
        Stellt sicher, dass der Request nur mit gueltiger Authentifizierung
        funktioniert und ansonsten der Zugriff verweigert wird.
        """
        self.responds_http_status(401)
        path = urlparse.urlparse(self.url).path
        self.client.GET(path, auth='user').responds_html()

    def responds_with_json_to_valid_auth(self):
        """stellt sicher, das der Request nur mit gueltiger Authentifizierung
        funktioniert und ansonsten der Zugriff verweigert wird."""
        self.responds_http_status(401)
        path = urlparse.urlparse(self.url).path
        self.client.GET(path, auth='user').responds_json()


class TestClient(object):
    """Hilfsklasse zum Ausfuehren von HTTP-Requests im Rahmen von Tests."""

    def __init__(self, host, users, debug=False):
        self.debug = debug
        self.host = host
        self.authdict = {}
        self.responses = []
        self.protocol = 'http'

        self.oklinks = set()
        self.brokenlinks = {}
        self.slowstats = Counter()

        for user in users:
            key, creds = user.split('=', 1)
            self.add_credentials(key, creds)

    def add_credentials(self, auth, creds):
        """Stellt dem Client credentials zur Verfügung, die in GET genutzt werden können.

        auth: key der Credentials
        creds: HTTP-Credentials in der Form 'username:password'
        """
        self.authdict[auth] = creds

    def GET(self, path, auth=None, accept=None, headers={}):
        """Führt einen HTTP-GET auf den gegebenen [path] aus.
        Nutzt dabei ggf. die credentials zu [auth] und [accept]."""
        if auth and auth not in self.authdict:
            raise ValueError("Unknown auth '%s'" % auth)

        myheaders = {}
        if accept:
            myheaders['Accept'] = accept
        myheaders.update(headers)

        url = urlparse.urlunparse((self.protocol, self.host, path, '', '', ''))

        # try request several times if it is slow to get rid of network jitter
        counter = 0
        duration = 100001
        while counter < 5 and duration >= DEFAULTFAST:
            if counter > 1:
                if duration > 10:
                    break  # solw API pages etc we test only once
                if self.debug:
                    print "retry request because of %d ms duration" % duration
                else:
                    sys.stdout.write('.')
                    sys.stdout.flush()
                time.sleep(1.5)
            start = time.time()
            status, responseheaders, content = fetch(
                url, content='', method='GET',
                credentials=self.authdict.get(auth),
                headers=myheaders, multipart=False, ua='resttest', timeout=TIMEOUT)
            duration = int((time.time() - start) * 1000)
            self.slowstats[url] = duration
            counter += 1
        response = Response(self, 'GET', url, status, responseheaders, content, duration)
        self.responses.append(response)
        return response

    def POST(self, path, content, auth=None, headers={}):
        """Führt einen HTTP-GET auf den gegebenen [path] aus.
        Nutzt dabei ggf. die credentials zu [auth] und [accept]."""
        if auth and auth not in self.authdict:
            raise ValueError("Unknown auth '%s'" % auth)
        url = urlparse.urlunparse((self.protocol, self.host, path, '', '', ''))

        start = time.time()
        status, responseheaders, content = fetch(
            url, content=content, method='GET',
            credentials=self.authdict.get(auth),
            headers=headers, multipart=False, ua='resttest', timeout=TIMEOUT)
        duration = int((time.time() - start) * 1000)

        response = Response(self, 'GET', url, status, responseheaders, content, duration)
        self.responses.append(response)
        return response

    @property
    def errors(self):
        """Anzahl der fehlgeschlagenen Zusicherungen, die für Anfragen dieses Clients gefroffen wurden."""
        return sum(r.errors for r in self.responses)


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

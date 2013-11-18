# encoding: utf-8
"""
DSL zur beschreibung von REST-interfaces, angelehnt an https://gist.github.com/805540

Copyright (c) 2011, 2013 HUDORA. All rights reserved.
File created by Philipp Benjamin Koeppchen on 2011-02-23
"""

from collections import Counter
import optparse
import os
import sys
import time
import urlparse
import xml.dom.minidom
from pprint import pprint

from huTools.http import fetch
from huTools import hujson2
import huTools.http._httplib2  # for ServerNotFoundError

BLACK, RED, GREEN, YELLOW, BLUE, MAGENTA, CYAN, WHITE = range(8)
FOREGROUND = 30
RESET_SEQ = "\033[0m"
COLOR_SEQ = "\033[1;%dm"
# print success messages
DEBUG = False

DEFAULTFAST = int(os.environ.get('DEFAULTFAST_MS', 1000))

# save slowest access to each URL
slowstats = Counter()
alllinks = Counter()
oklinks = set()
brokenlinks = {}

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

    def __init__(self, method, url, status, headers, content, duration):  # pylint: disable=R0913
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
        if DEBUG:
            print "<<<",
            print self.content
        print '=' * 50
        print

    def succeed(self, message):
        """Positives ergebnis einer Zusicherung."""
        if DEBUG:
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
        self.expect_condition(self.status == expected_status,
                        'expected status %s, got %s' % (expected_status, self.status))
        return self

    def responds_content_type(self, expected_type):
        """sichert zu, dass mit dem gegebenen Content-Type geantwortet wurde."""
        actual_type = self.headers.get('content-type')
        # evtl wird dem contenttype ein encoding nachgestellt, dies soll abgetrennt werden
        actual_type = actual_type.split(';')[0]
        self.expect_condition(actual_type == expected_type,
                        'expected content type %r, got %r' % (expected_type, actual_type))
        return self

    def redirects_to(self, expected_url):
        """sichert zu, dass mit einen Redirect geantwortet wurde."""
        location = self.headers.get('location')
        self.expect_condition(location == expected_url,
                        'expected redirect to %s, got %s' % (expected_url, location))

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

    def responds_with_content_location(self, expected_location):
        """sichert zu, dass die Antwort einen location-header hat."""
        content_location = self.headers.get('content-location', '')
        self.expect_condition(content_location.endswith(expected_location),
              'expected content-location to end with %r, got %r.' % (expected_location, content_location))
        return self

    def responds_fast(self, maxduration=DEFAULTFAST):
        """sichert zu, dass der Zugriff schnell geht (unter maxduration ms)."""
        self.expect_condition(self.duration <= maxduration,
                        'expected answer within %d ms, took %d ms' % (maxduration, self.duration))
        return self

    def responds_with_valid_links(self):
        links = extract_links(self.content, self.url)
        for link in links:
            if link in brokenlinks:
                # no need to check again
                brokenlinks.setdefault(link, set()).add(self.url)
            elif link not in oklinks:
                try:
                    status, _responseheaders, _content = fetch(
                        link,
                        headers=dict(referer=self.url),
                        content='', method='GET', multipart=False, ua='', timeout=30)
                except (IOError, huTools.http._httplib2.ServerNotFoundError):
                    status = 600

                if status == 200:
                    oklinks.add(link)
                else:
                    brokenlinks.setdefault(link, set()).add(self.url)
                #self.expect_condition(status == '200', 'invalid link to %r' % (link))

    def responds_with_valid_html(self):
        try:
            from tidylib import tidy_document
            document, errors = tidy_document(self.content, options={'numeric-entities':1, 'input-encoding': 'utf8'})
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

    def responds_normal(self, maxduration=DEFAULTFAST):
        """Normale Seite: Status 200, HTML, schnelle Antwort, keine kaputten Links"""
        self.responds_html()
        self.responds_with_valid_html()
        self.responds_with_valid_links()
        self.responds_fast(maxduration)
        return self

class TestClient(object):
    """Hilfsklasse zum Ausfuehren von HTTP-Requests im Rahmen von Tests."""
    def __init__(self, host):
        self.host = host
        self.authdict = {}
        self.responses = []

    def add_credentials(self, auth, creds):
        """Stellt dem Client credentials zur Verfügung, die in GET genutzt werden können.

        auth: key der Credentials
        creds: HTTP-Credentials in der Form 'username:password'
        """
        self.authdict[auth] = creds

    def GET(self, path, auth=None, accept=None):  # pylint: disable=C0103
        """Führt einen HTTP-GET auf den gegebenen [path] aus.
        Nutzt dabei ggf. die credentials zu [auth] und [accept]."""
        if auth and auth not in self.authdict:
            raise ValueError("Unknown auth '%s'" % auth)

        headers = {}
        if accept:
            headers['Accept'] = accept

        url = urlparse.urlunparse(('http', self.host, path, '', '', ''))

        # try request several times if it is slow to get rid of network jitter
        counter = 0
        duration = 100001
        while counter < 5 and duration >= DEFAULTFAST:
            if counter > 1:
                if DEBUG:
                    print "retry request because of %d ms duration" % duration
                else:
                    sys.stdout.write('.')
                    sys.stdout.flush()
                time.sleep(1.5)
            start = time.time()
            status, responseheaders, content = fetch(
                url, content='', method='GET',
                credentials=self.authdict.get(auth),
                headers=headers, multipart=False, ua='', timeout=30)
            duration = int((time.time() - start) * 1000)
            slowstats[url] = duration
            counter += 1
        response = Response('GET', url, status, responseheaders, content, duration)
        self.responses.append(response)
        return response

    @property
    def errors(self):
        """Anzahl der fehlgeschlagenen Zusicherungen, die für Anfragen dieses Clients gefroffen wurden."""
        return sum(r.errors for r in self.responses)


def extract_links(content, url):
    import lxml.html
    links = []
    dom =  lxml.html.document_fromstring(content, base_url=url)
    dom.make_links_absolute(url)
    for _element, _attribute, link, _pos in dom.iterlinks():
        if link.startswith('http'):
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


def create_testclient_from_cli(default_hostname, default_credentials_user, default_credentials_admin):
    """ Creates a Testclient with it's arguments from the Commandline.

    the CLI understands the options, --hostname, --credentials-user, --credentials-admin, their default
    values are taken from this functions args

    default_hostname: hostname, on wich to run tests, if none is provided via CLI
    default_credentials_user: HTTP-credetials for the user, if none are provided via CLI
    default_credentials_admin: HTTP-credetials for the admin, if none are provided via CLI

    returns a `TestClient`
    """
    global DEBUG
    parser = optparse.OptionParser()
    parser.add_option('-H', '--hostname', dest='hostname',
                                          help='Hostname, on which the tests should be run',
                                          default=default_hostname)
    parser.add_option('-u', '--credentials-user', dest='credentials_user',
                                                  help='HTTP-credentials for the non-admin-user',
                                                  default=default_credentials_user)
    parser.add_option('-a', '--credentials-admin', dest='credentials_admin',
                                                   help='HTTP-credentials for the admin-user',
                                                   default=default_credentials_admin)
    parser.add_option('-d', '--debug', dest='debug', default=False)

    opts, args = parser.parse_args()
    if args:
        parser.error('positional arguments are not accepted')
    DEBUG = opts.debug

    if os.environ.get('RESTTESTHOST'):
        default_hostname = os.environ.get('RESTTESTHOST')
    # Die or sorgen dafür, dass --option='' als 'nicht angegeben' gewertet wird, siehe aufruf im Makefile
    client = TestClient(opts.hostname or default_hostname)
    client.add_credentials('user', opts.credentials_user or default_credentials_user)
    client.add_credentials('admin', opts.credentials_admin or default_credentials_admin)

    return client

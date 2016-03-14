gaetk - Google Appengine Toolkit
================================

gaetk is a small collection of tools that tries to make programming Google AppEngine faster, more comfortable and less error prone.

It comes bundled with [gae-session][1], [webapp2][2] and [bootstrap][5]. Check the documentation of these projects for further information.

gaetk tries to stay compatible with "plain appengine" so you don't have to code specifically for gaetk. The idea is to encode patterns and best practices and allow you to use them where appropriate without making all your code gaetk specific. It is slightly slanted at company internal applications.

Features:

* Sessions via [gae-session][1], easy warping of GET, POST et. al. via [webapp2][2].
* efficient pagination with cursors
* Rendering via Jinja2
* automatic multi-format views (HTML, JSON & XML out of the box)
* hybrid Authentication via Google Apps and/or Username & Password
* Form-Based and HTTP Authentication
* transparent handling of HEAD requests
* Sequence generation
* Internal Memcache and Datastore Statistics (e.g. for graphing with munin)
* intelligent handler for `robot.txt` and auditing of which version is deployed.
* efficient caching of entities (TO BE MERGED)
* Django-Like Admin interface (TO BE MERGED)
* un-deletion of deleted entities (TO BE MERGED)
* Message Framework (TO BE MERGED)
* groups / access controls (TO BE MERGED)
* mini CMS like [Django flatpages][6] (TO BE MERGED)
* in place editing (TO BE MERGED)
* Generic Configuration objects
* simple testing for REST APIs

### Now distributed seperately
* Handling of Long running tasks with minimal effort via [`gaetk_longtask`](https://github.com/mdornseif/gaetk_longtask)
* Profiling with [`gae_mini_profiler`](https://github.com/kamens/gae_mini_profiler)
* Nice Error-Reports with [`my_ereporter`](https://github.com/mdornseif/my_ereporter)
* Syncronisation with MySQL via [`approcket_industrial`](https://github.com/mdornseif/approcket_industrial)


Creating a Project / getting started
------------------------------------

Create a appengine Project, then:

    mkdir lib
    echo "import site, os.path" > lib/__init__.py
    echo "site.addsitedir(os.path.dirname(__file__))" >> lib/__init__.py
    git submodule add git@github.com:mdornseif/appengine-toolkit.git lib/appengine-toolkit
    cp lib/appengine-toolkit/examples/Makefile .
    cp lib/appengine-toolkit/examples/config.py .
    cp lib/appengine-toolkit/examples/appengine_config.py .
    sed -i -e "s/%%PUT_RANDOM_VALUE_HERE%%/`(date;md5 /etc/* 2&>/dev/null)|md5`-5a17/" appengine_config.py
    # You might also want to install https://github.com/hudora/huTools for some additional functionality.
    git submodule add git@github.com:hudora/huTools.git lib/huTools
    git submodule foreach 'echo ./`basename ${path}` >> ../submodules.pth'

You might also want to install https://github.com/hudora/huTools for some additional functionality.


General structure
-----------------

`config.py` is assumed to be imported everywhere to set up paths. It should contain as little code as possible. `lib/` contains 3rd party modules.


Functionality
=============

gaetk.handler.BasicHandler
--------------------------

`BasicHandler` is the suggested base class for your WSGI handlers. It tries to encapsulate some best practices and can work with your models to provide automatic generation of HTML/XML/JSON/PDF from the same code, efficient pagination, usage of the jinja2 template engine, messages and authentication.

BasicHandler handles HTTP `HEAD` requests by doing an internal `GET` request.

### Helpers & Conventions

#### Sessions

All HTTP methods (`GET`, `POST`, etc.) have access to a session dictionary at `self.session`. See [gae-session][1] for further documentation.

#### Entity representation & absolute URLs

All models are expected to implement something like this:

    def get_url(self, abs_url=lambda x: x):
        return abs_url("/artnr/%s/" % self.id)

`abs_url` should be provided by the caller (view) to change the relative into an absolute URL. gaetk assumes a Entity knows where it it's canonical representation is located on a local URL path and does not support "routes" or any abstracting away the url knowledge out of the models.

`BasicHandler` provides a `abs_url()` method to change a relative into a absolute URL. usual calling convention is like this in a handler:

    def get(self, keyid):
        entity = Entity.get(keyid)
        url = entity.get_url(abs_url=self.abs_url)
        ...

Also entities are expected to have an `as_dict(abs_url=lambda x: x)` method which should return a dictionary representation of an object.

#### Errors and Redirections

BasicHandler currently provides an `error()` method to send error codes to the client. Users are encouraged to use raising of HTTP-Status codes instead. This results in much easier program flow and clearly documents a function ending wit e.g. a redirect.

Typical usage is like this:

    raise gaetk.handler.HTTP301_Moved(location='http://example.com/')

`error()` might be removed in future releases.


### Pagination

`paginate()` implements pagination of a query using offset and cursors. See the `paginate()` docstring for further information.

    query = Rechnungsliste.all().filter('kundennr = ', kundennr).order('-monat')
    values = self.paginate(query, 15)
    # values is now something like:
    # {more_objects=True, prev_objects=True, prev_start=10, next_start=30,
    #  objects: [...], cursor='ABCDQWERY'}
    self.render(values, 'page.html')

A template implementing pagination looks like this:

    <div class="pagination">
      <ul>
        <li class="prev {% if not prev_objects %}disabled{% endif %}"><a href="?{{ prev_qs }}">&larr; Zurück</a></li>
        <li class="next {% if not more_objects %}disabled{% endif %}"><a href="?{{ next_qs }}">Vor &rarr;</a></li>
      </ul>
    </div>


### Rendering

gaetk uses [Jinja2][3] for rendering templates. Jinja2 is imported on demand so you can use gaetk without having jinja2 available. `create_jinja2env()` sets up the Jinja2 Environment, you might have to overwrite it in a subclass, if you use Jinja2 extensions.

`default_template_vars()` sets up values to be available to every template. You might want to overwrite it to get an effect like Django's context processors.

`render()` returns a rendered template. `render()` does the same but also sends the template to the client.
IT provides every template with the `uri` and `credential`, the values from `default_template_vars()` and the values passed to the method.

`multirender()` is a somewhat involved function to render some values in different ways. The usecase is that you want to present the same data in a variety of formats without code dupliction or large if/then/else cascades. We use it to provide the same data as HTML-Page, XML, JSON, PDF, CSV and EDIFACT/EANCOM.

The basic calling convention is:

    def get(customerid, format='JSON'):
        query = Incoice.all().filter('customerid = ', customerid).order('-date')
        values = self.paginate(query, 15)
        self.render(format, values, html_template='page.html')

For HTML you can provide a template name in `html_template`, all other formats are directly created from the data via [huTools.structured][4] or user supplied formatter functions.
Often the HTML needs additional data (e.g. currently logged in user) which can be provided via `html_addon`.
`multirender()` can generate HTML, XML and JSON out of the box, if you want to provide other formats you must supply a dict of "mappers" which are given the input-data and reformat it for output. e.g.

    from functools import partial
    multirender(fmt, values,
                mappers=dict(xml=partial(dict2xml, roottag='response',
                                         listnames={'rechnungen': 'rechnung', 'odlines': 'odline'},
                                          pretty=True),
                             html=lambda x: '<body><head><title>%s</title></head></body>' % x))

This renders HTML without Jinja2 and uses `huTools.structured.dict2xml` to force a certain XML structure.

See the `multirender()` Docstring for further Information.

Per default templates have access to four additional jinja2 filters.

* `ljustify(width)` and `rjustify(width)` Pr- Postefix the given string with spaces until it is width characters long
* `nicenum` formats number with non breaking spaces between thousands. E.g. `<span class="currency">1&#8239;000</span>`.
* `eurocent` is like nicenum but divides by 100 and uses only two decimal places. E.g. `<span class="currency">9&#8239;999.99</span>`

See jinja_filters.py Docstrings for further documentation.


### Authentication

gaetk has some authentication functionality which is described in a chapter below. `BasicHandler` supports this via the `is_admin` and the `login_required` methods.

`authchecker` is called on every request and can be overwritten by subclasses. A simple way of always forcing authentication is like this:

    class AuthenitcatedHandler(gaetk.handler.BasicHandler):
        def authcecker(self, method, *args, **kwargs):
            self.login_required()

TBD: ALLOWED_PERMISSIONS

### Messages

The Message Framework is not documented for now.

    add_message(self, typ, html, ttl=15):


JSONviews
---------

`gaetk.handler.JsonResponseHandler` helps to generate nice JSON and JSONP responses. A valid view will look like this:

    class VersandauslastungHandler(gaetk.handler.JsonResponseHandler):
        def get(self):
            entity = BiStatistikZeile.get_by_key_name('versandauslastung_aktuell')
            ret = dict(werte=hujson.loads(entity.jsonValue),
                       ...)
            return (ret, 200, 60)

This will generate a JSON reply with 60 Second caching and a 200 status code. The reply will support [JSONP](http://en.wikipedia.org/wiki/JSONP#JSONP) via an optional `callback` parameter in the URL.


Sequence generation
===================

Generation of sequential numbers ('autoincrement') on Google appengine is hard. See [Stackoverflow](http://stackoverflow.com/questions/3985812) for some discussion of the issues. `gaetk` implements a sequence number generation based on transactions. This will yield only a preformance of half a dozen or so requests per second but at least allows to alocate more than one number in a single request.

    >>> from gaeth.sequences import *
    >>> init_sequence('invoce_number', start=1, end=0xffffffff)
    >>> get_numbers('invoce_number', 2)
    [1, 2]


To use it you need a `index.yaml` like this:

```
indexes:
- kind: gaetkSequence
  ancestor: yes
  properties:
  - name: type
  - name: start
- kind: gaetkSequence
  ancestor: yes
  properties:
  - name: type
  - name: end
- kind: gaetkSequence
  properties:
  - name: active
  - name: type
  - name: start
```


Pre-Made Views and static files
-------------------------------

Add the following lines to your `app.yaml`:

    - url: /gaetk/static
      static_dir: lib/gaetk/static

    - url: /gaetk/.*
      script: lib/gaetk/gaetk/defaulthandlers.py

    - url: /robots.txt
      script: lib/gaetk/gaetk/defaulthandlers.py

    - url: /version.txt
      script: lib/gaetk/gaetk/defaulthandlers.py



This will make [bootstrap][5] available at `/gaetk/static/bootstrap/1.4.x/`


It will also allow you to get JSON encoded statistics at `/gaetk/stats.json`:

    curl http://localhost:8080/gaetk/stats.json
    {"datastore": {"count": 149608,
                   "kinds": 16,
                   "bytes": 95853319},
     "memcache": {"hits": 1665726,
                  "items": 1171,
                  "bytes": 4588130,
                  "oldest_item_age": 2916,
                  "misses": 50674,
                  "byte_hits": 833839440}}

You might want to use Munin to graph these values. In addition the statistics are stored in the Datastore as `gaetk_Stats for later inspection.

`RobotTxtHandler` allows serving a robots.txt file that disables crawler access to all app versions except the default version.

`VersionHandler` allows clients to read the git revision. When deploying we do something like `git show-ref --hash=7 HEAD > version.txt` just before `appcfg.py update` and `VersionHandler lets you retive that information.


LoggedModel
------------

In models.py you find a superclass `LoggedModel` for implementing audit logs for a model:
All create, update and delete operations are logged via the `AuditLog` model.

Example:

    import gaetk.models
    from google.appengine.ext import db

    class MyModel(gaetk.models.LoggedModel):
        name = db.StringProperty()

    obj = MyModel(name=u'Alex')
    print obj.logentries()


Please note: Changes in (subclasses of) UnindexedProperty (hence TextProperty and BlobProperty) are not logged.


Tools
-----

Tools contians general helpers. It is independent of the rest of gaetk.

`tools.split(s)` "Splits a string at space characters while respecting quoting.

    >>> split('''A "B and C" D 'E or F' G " "''')
    ['A',
     'B and C',
     'D',
     'E or F',
     'G',
     '']

Infrastructure
--------------

Infrastructure contains helpers for accessing the GAE infrastructure. It is independent of the rest of gaetk.


`taskqueue_add_multi` batch adds jobs to a Taskqueue:

    tasks = []
    for kdnnr in kunden.get_changed():
        tasks.append(dict(kundennr=kdnnr))
    taskqueue_add_multi('softmq', '/some/path', tasks)


Generic Configuration objects
-----------------------------

The appengine toolkit provides a method for generic configuration objects.
These configuration objects are stored in Datastore and can hold any string value.
There are two convenience functions for getting and setting values, `get_config` and `set_config`.

    >>> from gaetk import configuration
    >>> configuration.get_config('MY-KEY-NAME')
    None
    >>> configuration.set_config('MY-KEY-NAME', u'5711')
    >>> configuration.get_config('MY-KEY-NAME')
    u'5711'

Configuration values are cached infinitely. The module provides a HTTP handler
as a mean to flush all cached values.

RESTtest
========

gaetk comes with a simple frameworks to do simle minded acceptance tests againgst
an installed version of your app. The testing harness is installed in `resttest_dsl`.

A possible test script would look like this:

  import sys
  from resttest_dsl import create_testclient_from_cli, get_app_version


  def main():
      """Main Entry Point"""

      # init with app id and some credentials
      client = create_testclient_from_cli(default_hostname='%s.<myappid>.appspot.com' % get_app_version(),
                                          default_credentials_user='someregular:6BTUKW5TQ',
                                          default_credentials_admin='someadmin:EEGE2OGZ7')

      client.GET('/').responds_http_status(200)
      client.GET('/').responds_content_type('text/html')
      # the two lines above can be written as
      client.GET('/').responds_http_status(200).responds_content_type('text/html')
      # or even shorter
      client.GET('/').responds_html()

      # checks for valid XML or JSON
      client.GET('/feed.atom').responds_xml()
      client.GET('/api.json').responds_json()

      # checks that there is a response within 1000 ms
      client.GET('/').responds_fast()
      # or 500 msa
      client.GET('/').responds_fast(500)
      # combines responds_html and respondes fast
      client.GET('/').responds_normal()

      # checks if there is an redirect
      client.GET('/artnr/1400/03').redirects_to('/artnr/14600/03.trailer/')

      # Internal Pages only available to logged in users
      client.GET('/backend/').responds_access_denied()
      client.GET('/backend/', auth='user').responds_html()
      client.GET('/backend/', auth='admin').responds_html()

      # Admin pages available only to admin users
      client.GET('/admin/').responds_access_denied()
      client.GET('/admin/', auth='user').responds_access_denied()
      client.GET('/admin/', auth='admin').responds_html()

      sys.exit(client.errors)

  if __name__ == "__main__":
      main()

It comes also with preformance and Broken-Link monitoring support.
So add before `sys.exit()`:


    # `responds_normal()` checks for HTML, speed and broken links
    client.GET('/').responds_normal()
    client.GET('/wir/outlet.html').responds_normal()

    # slowstats and brokenlinks contain statistics gathered during the run
    from resttest_dsl slowstats, brokenlinks

    print "## slowest Pages "
    for url, speed in slowstats.most_common(10):
        print "{0} ms {1}".format(speed, url)

    if brokenlinks:
        print "## broken links"
        print brokenlinks.values()
        for link in brokenlinks:
            for source in brokenlinks[link]:
                print (u"{0} via {1}".format(link, source)).encode('utf-8')

If `tidylib` is installed, it will also output HTML-Errors.


Thanks
======

Axel Schlüter for suggestions on abstracting login and JsonResponseHandler.

Contains [gaesession.py][1] by David Underhill - http://github.com/dound/gae-sessions
Updated 2010-10-02 (v1.05), Licensed under the Apache License Version 2.0.

Contains code from [webapp2][2], Copyright 2010 Rodrigo Moraes.
Licensed under the Apache License, Version 2.0

Contains code from [bootstrap][5], Copyright 2011 Twitter, Inc.
Licensed under the Apache License, Version 2.0

Contains code from [gae_mini_profiler][7], Copyright 2011 Ben Kamens.
Licensed under the MIT license

Contains code from [itsdangerous][8], Copyright (c) 2011 by Armin Ronacher and the Django Software Foundation.
Licensed under a Berkeley-style License

gaetk code is Copyright 2010, 2011 Dr. Maximillian Dornseif & Hudora GmbH and dual licensed under GPLv3 and the Apache License Version 2.0.


[1]: https://github.com/dound/gae-sessions
[2]: http://code.google.com/p/webapp-improved/
[3]: http://jinja.pocoo.org/docs/
[4]: https://github.com/hudora/huTools/blob/master/huTools/structured.py
[5]: http://twitter.github.com/bootstrap/
[6]: https://docs.djangoproject.com/en/dev/ref/contrib/flatpages/
[7]: https://github.com/kamens/gae_mini_profiler
[8]: https://github.com/mitsuhiko/itsdangerous

[![Bitdeli Badge](https://d2weczhvl823v0.cloudfront.net/mdornseif/appengine-toolkit/trend.png)](https://bitdeli.com/free "Bitdeli Badge")

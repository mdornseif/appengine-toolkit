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
* Handling of Long running tasks  with minimal effort
* efficient caching of entities (TO BE MERGED)
* profiler based on `gae_mini_profiler` (TO BE MERGED)
* Django-Like Admin interface (TO BE MERGED)
* un-deletion of deleted entities (TO BE MERGED)
* Message Framework (TO BE MERGED)
* groups / access controls (TO BE MERGED)
* mini CMS like [Django flatpages][6] (TO BE MERGED)
* in place editing (TO BE MERGED)


Creating a Project / getting started
------------------------------------

Create a appengine Project, then:

    mkdir lib
    git submodule add git@github.com:mdornseif/appengine-toolkit.git lib/gaetk
    git submodule update --init lib/gaetk
    cp lib/gaetk/examples/Makefile .
    cp lib/gaetk/examples/config.py .
    cp lib/gaetk/examples/appengine_config.py .
    sed -i -e "s/%%PUT_RANDOM_VALUE_HERE%%/`(date;md5 /etc/* 2&>/dev/null)|md5`-5a17/" appengine_config.py
    # If you want to use jinja2
    git submodule add https://github.com/mitsuhiko/jinja2.git lib/jinja2
    git submodule update --init lib/jinja2


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

BasicHandler currently provides an `error()` method to send error codes to the client. USers are encouraged to use raising of HTTP-Status codes instead. This results in much easier program flow and clearly documents a function ending wit e.g. a redirect.

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


### Authentication

gaetk has some authentication functionality which is described in a chapter below. `BasicHandler` supports this via the `is_admin` and the `login_required` methods.

`authchecker` is called on every request and can be overwritten by subclasses. A simple way of always forcing authentication is like this:

    class AuthenitcatedHandler(gaetk.handler.BasicHandler):
        def authcecker(self, method, *args, **kwargs):
            self.login_required()


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


Login / Authentication
======================

gaetk offers a hybrid Google Apps / Credential based authentication via session Cookies and HTTP Auth. This approach tries to accommodate command-line/API clients like `curl` and browser based clients. If a client does provide an `Accept`-Header containing `text/html` (all Browsers do) the client is redirected to `/_ah/login_required` where the user can Enter `uid` and `secret` (Session-Based Authentication) or login via OpenID/Google Apps. If there is no `Accept: text/html` the client is presented with a 401 status code, inviting the client to offer HTTP-Basic-Auth.

To use OpenID with Google Apps configure your Application to use "Federated Login":

![Federated Login](http://static.23.nu/md/Pictures/ZZ77D022D0.png)

For us this allows our Staff to do Single Sign-On via Google Apps, while external users with credentials can can access the application by entering their credentials in the browser. Automated scrips can access the system via HTTP-Auth. 

Users are represented by `gaetk.handler.Credential` objects. For OpenID users a uid ("Username") and secret ("Password") are auto generated. For Session or HTTP-Auth based users uid and secret should also be auto generated but can also be given. I *strongly* advise against user  selectable passwords and suggest you might also consider avoiding user  selectable usernames. Use `Credential.create()` to create new Crdentials including auto-generated uid and secret. If you want to set the `uid` mannually, give the `uid` parameter.

    gaetk.handler.Credential.create(text='API Auth for Schulze Server', email='ops@example.com')
    gaetk.handler.Credential.create(uid='user5711', text='...', email='ops@example.com')



To use it add the following to `app.yaml`:

    handlers:
    - url: /_ah/login_required
      script: lib/gaetk/gaetk/login.py

    - url: /logout
      script: lib/gaetk/gaetk/login.py


Now in your views/handlers you can easyly force authentication like this:

    from gaetk.handler import BasicHandler

    class HomepageHandler(BasicHandler):
        def get(self):
            user = self.login_required() # results in 401/403 if can't login
            ...


Unless you call `login_required(deny_localhost=False)` access from localhost is always considered authenticated.


Long running tasks
==================

Many things take longer than a user is willing to wait. AppEngine with it's request deadline of 10s (later liftet to 30s and then to 60s) is also not willing to wait very long. `longtask.py` encapsulates a pattern to do the actual work in a taskqueue while providing users with updates (and finally the results) via self reloading webpages.
It is currently experimental and limited to tasks running not more than 10 minutes.

    class myTask(gaetk.longtask.LongRunningTaskHandler):
        def execute_task(self, parameters):
            self.log_progress("Starting", step=0, 5):
            time.sleep(15)
            for x in range(5):
                self.log_progress("Step %d" % (x + 1), step=(x + 1), 5)
                time.sleep(15)
            return "<html><body>Done!</body></html>"

Thats basically all you need.


Sequence generation
===================

Generation of sequential numbers ('autoincrement') on Google appengine is hard. See [Stackoverflow](http://stackoverflow.com/questions/3985812) for some discussion of the issues. `gaetk` implements a sequence number generation based on transactions. This will yield only a preformance of half a dozen or so requests per second but at least allows to alocate more than one number in a single request.

    >>> from gaeth.sequences import *
    >>> init_sequence('invoce_number', start=1, end=0xffffffff)
    >>> get_numbers('invoce_number', 2)
    [1, 2]



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



This will make [bootstrap][5] available at `/gaetk/static/bootstrap/1.3.0/`


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

You might want to use Munin to graph these values.

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


client side functionality
=========================

ExtJS tools
-----------

In addition to the server side functionality gaetk also includes various javascript helper methods. They must be used in combination with ExtJS and provide methods for easy handling of often-used tasks. To use the javascript helpers you will have to link the `web` directory into the directory declared the `static_dir` directory in your `app.yaml`. Then include the `gaetk-extjs-helpers.js` and `gaetk-extjs-helpers.css` files into your HTML page template.

Currently the helpers include two methods:

 * `Hudora.Helpers.spinnerMessageBox(message)`: display a non-closable messagebox with a spinner indicating progress
 * `Hudora.Helpers.errorMessageBox(title, message)`: display a error message box without having to write five lines of code every time you need an error messagebox.


Thanks
======

Axel Schlüter for suggestions on abstracting login and JsonResponseHandler.

Contains [gaesession.py][1] by David Underhill - http://github.com/dound/gae-sessions
Updated 2010-10-02 (v1.05), Licensed under the Apache License Version 2.0.

Contains code from [webapp2][2], Copyright 2010 Rodrigo Moraes.
Licensed under the Apache License, Version 2.0

Contains code from [bootstrap][5], Copyright 2011 Twitter, Inc.
Licensed under the Apache License, Version 2.0

gaetk code is Copyright 2010, 2011 Dr. Maximillian Dornseif & Hudora GmbH and dual licensed under GPLv3 and the Apache License Version 2.0.


[1]: https://github.com/dound/gae-sessions
[2]: http://code.google.com/p/webapp-improved/
[3]: http://jinja.pocoo.org/docs/
[4]: https://github.com/hudora/huTools/blob/master/huTools/structured.py
[5]: http://twitter.github.com/bootstrap/
[6]: https://docs.djangoproject.com/en/dev/ref/contrib/flatpages/
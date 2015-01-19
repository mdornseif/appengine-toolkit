Login / Authentication
======================

[gaetk](https://github.com/mdornseif/appengine-toolkit) offers a hybrid Google Apps / Credential based authentication via session Cookies and HTTP Auth. This approach tries to accommodate command-line/API clients like `curl` and browser based clients.

Design goals where:

* allow login via HTTP-Auth for API Access
* allow form based Authentication via sessions
* allow Authentication against Google Apps via OAuth2 and sessions
* no user settable passwords. Passwords are auto generated.
* no requirement to store E-Mail adresses.

Keep in mind, that gaetk does not provide rate limiting against attempts to brute force passwords. This is mitigated by using high-entropy passwords not controlled by the user.


Basic Usage
-----------

To use it add the following to `app.yaml`:

    handlers:
    - url: (/_ah/login_required|/gaetk/auth/.*)
      script: gaetk.login.application

Now in your views/handlers you can easyly force authentication like this:

    from gaetk.handler import BasicHandler

    class HomepageHandler(BasicHandler):
        def get(self):
            self.login_required()  # results in 401/403 if can't login
            ...


`login_required()` will never return if the user is not authenticated. After calling it there will be `self.credential` available.

To always force authentication overwrite `authcecker`:

    class AuthenitcatedHandler(gaetk.handler.BasicHandler):
        def authcecker(self, method, *args, **kwargs):
            self.login_required()


You have to generate the first Credential by programmatic access (or OAuth2, see below).

    credential1 = gaetk.handler.NdbCredential.create(
        text='Aamin for Schulze Server', email='ops@example.com', admin=True)
    credential2 = gaetk.handler.Credential.create(
        uid='user5711', text='...', email='ops@example.com', admin=True)
    print credential1.uid, credential1.secret
    print credential2.uid, credential2.secret


Algernative login via the browser and via Google Apps (See below) and then check the "Credentials" Model in the App Engine Admin Console to get `$uid:$secret`. Once this is done you can use a HTTP-API to generate Credentials.


    curl -u $uid:$secret -X POST admin=False \
        -F text='fuer das Einspeisen von SoftM Daten' -F email='edv@hudore.de' \
        http://example.appspot.com/gaetk/auth/credentials
    {
     "secret": "aJNKCDUZW5PIBT23LYX7XXVFENA",
     "uid": "u66666o26ec4b"
    }

If you want to disable this functionality set `GAETK_AUTH_API_DISABLED = True` in `config.py`. TBD

`CredentialsHandler` at `/gaetk/auth/credentials` allows you to create new access credentials.

    $ curl -u $uid:$secret -X POST -F admin=True \
        -F text='new user for API access' -F email='edv@ShPuAdMora.de' -F tenant='hudora.de' \
        -F permissions='einkaufspreise,wertschoepfung' http://example.com/gaetk/auth/credentials
    {
        "admin": true,
        "created_at": "2011-10-26 13:00:28.024000",
        "email": "x.dornseif@hudora.de",
        "permissions": [
         "einkaufspreise",
         "wertschoepfung"
        ],
        "secret": "GIFBOQC123GAD",
        "tenant": "hudora.de",
        "text": "",
        "uid": "edv@ShPuAdMora.de"
    }

This generates a new user. UserID and Password are choosen by the system and are not user settable.


Authenticationg against Google Apps
-----------------------------------

Original gaetk used [OpenID with Google Apps](https://cloud.google.com/appengine/articles/openid) in "Federated Login" mode to authenticate users against one or more Google Apps domains. The general thinking is, that Clients are Authenticated via HTTP-Form-Auth and Staff is authenticated via Google Apps allowing staff to have a single-sign-on (SSO) experience.

Since Google stopped supporting OpenID gaetk moved to [OAuth2 Connect](https://developers.google.com/accounts/docs/OpenIDConnect) for authentication. See this article for a general Overview of [OAuth2 Connect](http://www.heise.de/developer/artikel/OpenID-Connect-Login-mit-OAuth-Teil-1-Grundlagen-2218446.html). The move to OAauth2 Connect resulted in a major rewrite of authentication functionality in 2015.

To [get OAuth2 Credentials](https://developers.google.com/accounts/docs/OpenIDConnect#getcredentials) from Google:

1. Go to the [Google Developers Console](https://console.developers.google.com/).
2. Select a project, or create a new one.
3. In the sidebar on the left, expand APIs & auth. Next, click APIs. In the list of APIs, make sure all of the APIs you are using show a status of ON.
4. In the sidebar on the left, select Credentials.
5. If you haven't done so already, create your project's OAuth 2.0 credentials by clicking Create new Client ID, and providing the information needed to create the credentials.
6. Set "Authorized Redirect URLs" to something like this:
    ```
    https://example.appspot.com/gaetk/auth/oauth2callback
    https://www.example.de/gaetk/auth/oauth2callback
    https://dev-md-dot-example.appspot.com/gaetk/auth/oauth2callback```
7. Click on "Download JSON" to get something to put into your `config.py`

Your config.py should now contain something like this:

    OAUTH = {"web": {
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "client_secret": "...",
        "token_uri": "https://accounts.google.com/o/oauth2/token",
        "client_id": "...",
        ...
        "redirect_uris": [...],
    }

LOGIN_ALLOWED_DOMAINS - TBD


Upgrading from pre-2015
-----------------------

* logout URL has changed
* self.credential is now an `ndb` entity, not an `db` entity.
* create_credential_from_federated_login() is gone. See "Customizing" below.
* You should not need to overwrite Credential.create() anymore. See "Customizing" below.


Customizing
-----------

Copy `lib/appengine-toolkit/templates/login.html` to `templates/login.html` to custumize the Login-Screen.

Apps usually want to extend credential creation. This is done by overwriting `get_verified_credential` in `gaetk.login.LoginHandler`. The method `get_verified_credential()` has to check if a User does exist and if the correct secret is supplied.

Let's assume we want to check the password against an other webapp.

    class myLoginHandler(gaetk.login.LoginHandler):
        def get_verified_credential(self, username, secret, session=None):
            credential = gaetk.handler._get_credential(username)
                if not credential:
                    # check against an other app
                    status, headers, _body = huTools.http.fetch(
                        'http://edihub.example.de/',
                        credentials="%s:%s" % (username, secret))
                    if status == 200:
                        # credentials where correct. extract additional data
                        # and add to credential entity
                        cusomerno = headers.get('Location', headers.get('X-huTools-final_url', '')).split('/')[-2]
                        credential = Credential.create(
                            cusomerno=cusomerno,
                            text="Automatically created via EDIhub")
                            credential.secret = secret
                            credential.put()

                if credential and credential.secret == secret:
                    return credential
                return None

    application = gaetk.webapp2.WSGIApplication([
        ('/gaetk/auth/logout', gaetk.login.LogoutHandler),
        ('/gaetk/auth/oauth2callback', gaetk.login.OAuth2Callback),
        ('/gaetk/auth/debug', gaetk.login.Debug)
        ('/gaetk/auth/credentials', gaetk.login.CredentialsHandler),
        ('.*', myLoginHandler)], debug=False)


There is a second place credentials might be created if login comes via OAuth2 Connect. To change this, overwrite `create_credential_oauth2()`. E.g. to set some additional fields on newly created users:

    class myOAuth2Callback(gaetk.login.OAuth2Callback):
        def create_credential_oauth2(self, jwt):
            credential = super(myOAuth2Callback, self).create_credential_oauth2(jwt)
            credential.kundennr = 'SC66666'
            credential.put()
            return credential


Details of Operation
--------------------

TBD

If a client does provide an `Accept`-Header containing `text/html` (all Browsers do) the client is redirected to `/_ah/login_required` where the user can Enter `uid` and `secret` (Session-Based Authentication) or login via OpenID/Google Apps. If there is no `Accept: text/html` the client is presented with a 401 status code, inviting the client to offer HTTP-Basic-Auth.

Users are represented by `gaetk.handler.Credential` objects. For OpenID users a uid ("Username") and secret ("Password") are auto generated. For Session or HTTP-Auth based users uid and secret should also be auto generated but can also be given. I *strongly* advise against user  selectable passwords and suggest you might also consider avoiding user  selectable usernames. Use `Credential.create()` to create new Crdentials including auto-generated uid and secret. If you want to set the `uid` mannually, give the `uid` parameter.



Authorisation & Acesscontrol
============================

TBD






gaetk - Google Appengine Toolkit
================================

gaetk is a small collection of tools that tries to make programming Google AppEngine faster, more comfortable and less error prone. It is pre-alpha quality software.

It comes bundled with [gaesession][1] and [webapp2][2]. Check the documentation of these projects for further information.

Creating a Project
------------------

Create a appengine Project, then:

    mkdir lib
    git submodule add git@github.com:mdornseif/appengine-toolkit.git lib/gaetk
    git submodule update --init lib/gaetk
    cp libs/gaetk/example/Makefile .
    cp libs/gaetk/example/config.py .
    cp libs/gaetk/example/appengine_config.py .
    sed -i -e "s/%%PUT_RANDOM_VALUE_HERE%%/`(date;md5 /etc/* 2&>/dev/null)|md5`/" appengine_config.py


Functionality
=============

Sequence generation
-------------------

Generation of sequential numbers ('autoincrement') on Google appengine is hard. See [Stackoverflow](http://stackoverflow.com/questions/3985812) for some discussion of the issues. `gaetk` implements a sequence number generation based on transactions. This will yield only a preformance of half a dozen or so requests per second but at least allows to alocate more than one number in a single request.

    >>> from gaeth.sequences import * 
    >>> init_sequence('invoce_number', start=1, end=0xffffffff)
    >>> get_numbers('invoce_number', 1)
    [1, 2]
    

Login / Authentication
----------------------

gaetk offers a hybrid Google Apps / Credential based authentication via Session Coockies and HTTP Auth. Currently to much of this functionality hardcoded.

In app.yaml add:

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


Thanks
======

Contains [gaesession.py][1] by David Underhill - http://github.com/dound/gae-sessions
Updated 2010-10-02 (v1.05), Licensed under the Apache License Version 2.0.

Contains code from [webapp2][2], Copyright 2010 Rodrigo Moraes.
Licensed under the Apache License, Version 2.0

gaetk code is Copyright 2010 Hudora GmbH and licensed under the Apache License Version 2.0.


[1]: https://github.com/dound/gae-sessions
[2]: http://code.google.com/p/webapp-improved/
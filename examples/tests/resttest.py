#!/usr/bin/env python
# encoding: utf-8
"""
Test für www.hudira.de

Created by Christian Klein on 2014-12-17.
Copyright (c) 2014-2015 HUDORA. All rights reserved.
"""

import sys
from resttest_dsl import create_testclient_from_cli, slowstats


def main():
    """Main Entry Point"""

    client = create_testclient_from_cli(default_hostname='www.hudora.de ',
                                        default_credentials_user='u10001:ein1ooSh',
                                        default_credentials_admin='u20001:ein1ooSh')
    client.protocol = 'http'

    client.GET('/some/random/path/').responds_not_found()
    # Startseite
    client.GET('/gaetk/auth/logout').responds_normal()
    client.GET('/').responds_normal()

    print
    print "Die langsamsten Seiten"
    for url, speed in slowstats.most_common(10):
        print "{0} ms {1}".format(speed, url)

    sys.exit(client.errors)


if __name__ == "__main__":
    main()

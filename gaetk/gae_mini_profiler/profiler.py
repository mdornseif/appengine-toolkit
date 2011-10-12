import os
try:
    import json
    json  # workaround for pyflakes issue #13
except ImportError:
    import simplejson as json


from google.appengine.ext.webapp import RequestHandler

from gaetk.gae_mini_profiler.middleware import RequestStats


class SharedStatsHandler(RequestHandler):

    def get(self):
        from google.appengine.ext.webapp import template
        path = os.path.join(os.path.dirname(__file__), "templates/shared.html")

        request_id = self.request.get("request_id")
        if not RequestStats.get(request_id):
            self.response.out.write("Profiler stats no longer exist for this request.")
            return

        self.response.out.write(
            template.render(path, {
                "request_id": request_id
            })
        )


class RequestStatsHandler(RequestHandler):

    def get(self):

        self.response.headers["Content-Type"] = "application/json"

        list_request_ids = []

        request_ids = self.request.get("request_ids")
        if request_ids:
            list_request_ids = request_ids.split(",")

        list_request_stats = []

        for request_id in list_request_ids:

            request_stats = RequestStats.get(request_id)

            if request_stats and not request_stats.disabled:

                dict_request_stats = {}
                for property in RequestStats.serialized_properties:
                    dict_request_stats[property] = request_stats.__getattribute__(property)

                list_request_stats.append(dict_request_stats)

                # Don't show temporary redirect profiles more than once automatically, as they are
                # tied to URL params and may be copied around easily.
                if request_stats.temporary_redirect:
                    request_stats.disabled = True
                    request_stats.store()

        self.response.out.write(json.dumps(list_request_stats))

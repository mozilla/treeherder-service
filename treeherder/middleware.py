import re

import newrelic.agent
from django.urls import reverse
from django.utils.deprecation import MiddlewareMixin
from whitenoise.middleware import WhiteNoiseMiddleware

# https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Content-Security-Policy
# NB: The quotes inside the strings must be single quotes. Also any requests that
# redirect need to have both the original and redirected domains whitelisted.
CSP_DIRECTIVES = [
    "default-src 'none'",
    # The unsafe-eval is required for Custom Action's use of `ajv`. See bug 1530607.
    # 'report-sample' instructs the browser to include a sample of the violating JS to assist with debugging.
    "script-src 'self' 'unsafe-eval' 'report-sample'",
    # The unsafe-inline is required for react-select's use of emotion (CSS in JS). See bug 1507903.
    # The Google entries are required for IFV's use of the Open Sans font from their CDN.
    "style-src 'self' 'unsafe-inline' 'report-sample' https://fonts.googleapis.com https://stackpath.bootstrapcdn.com/bootstrap/4.4.1/css/bootstrap.min.css",
    "font-src 'self' https://fonts.gstatic.com",
    # The `data:` is required for images that were inlined by webpack's url-loader (as an optimisation).
    "img-src 'self' data:",
    "connect-src 'self' https://community-tc.services.mozilla.com https://firefox-ci-tc.services.mozilla.com https://*.taskcluster-artifacts.net https://taskcluster-artifacts.net https://treestatus.mozilla-releng.net https://bugzilla.mozilla.org https://auth.mozilla.auth0.com https://stage.taskcluster.nonprod.cloudops.mozgcp.net https://artifacts.tcstage.mozaws.net https://*.artifacts.tcstage.mozaws.net https://insights-api.newrelic.com https://prototype.treeherder.nonprod.cloudops.mozgcp.net https://treeherder.allizom.org",
    # Required since auth0-js performs session renewals in an iframe.
    "frame-src 'self' https://auth.mozilla.auth0.com",
    "report-uri {}".format(reverse('csp-report')),
]
CSP_HEADER = '; '.join(CSP_DIRECTIVES)


class CustomWhiteNoise(WhiteNoiseMiddleware):
    """
    Extends WhiteNoiseMiddleware with two additional features:
    1) Adds a `Content-Security-Policy` header to all static file responses.
    2) Allows WhiteNoise to recognise Neutrino-generated hashed filenames as "immutable",
       so that WhiteNoise will then set long Cache-Control max-age headers for them.

    For the stock functionality provided by WhiteNoiseMiddleware see:
    http://whitenoise.evans.io/
    """

    # Matches Neutrino's style of hashed filename URLs, eg:
    #   /assets/index.1d85033a.js
    #   /assets/2.379789df.css.map
    #   /assets/fontawesome-webfont.af7ae505.woff2
    IMMUTABLE_FILE_RE = re.compile(r'^/assets/.*\.[a-f0-9]{8}\..*')

    def add_headers_function(self, headers, path, url):
        """
        This allows custom headers be be added to static assets responses.
        NB: It does not affect dynamically generated Django views/templates,
        such as API responses, or the browse-able API/auto-generated docs,
        since they are not served by the WhiteNoise middleware.
        """
        headers['Content-Security-Policy'] = CSP_HEADER

    def immutable_file_test(self, path, url):
        """
        Determines whether the given URL represents an immutable file (i.e. a file with a
        hash of its contents as part of its name) which can therefore be cached forever.
        """
        if self.IMMUTABLE_FILE_RE.match(url):
            return True
        # Otherwise fall back to the default method, so we catch filenames in the
        # style output by GzipManifestStaticFilesStorage during collectstatic. eg:
        #   bootstrap.min.abda843684d0.js
        return super().immutable_file_test(path, url)


class NewRelicMiddleware(MiddlewareMixin):
    """Adds custom annotations to New Relic web transactions."""

    def process_request(self, request):
        # The New Relic Python agent only submits the User Agent to APM (for exceptions and
        # slow transactions), so for use in Insights we have to add it as a customer parameter.
        if 'HTTP_USER_AGENT' in request.META:
            newrelic.agent.add_custom_parameter('user_agent', request.META['HTTP_USER_AGENT'])

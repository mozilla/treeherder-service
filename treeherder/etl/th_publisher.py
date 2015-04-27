import logging

from django.utils.encoding import python_2_unicode_compatible
from django.conf import settings

from thclient import TreeherderRequest

from treeherder.etl.oauth_utils import OAuthCredentials


logger = logging.getLogger(__name__)


def post_treeherder_collections(th_collections):
    errors = []
    for project in th_collections:

        credentials = OAuthCredentials.get_credentials(project)

        th_request = TreeherderRequest(
            protocol=settings.TREEHERDER_REQUEST_PROTOCOL,
            host=settings.TREEHERDER_REQUEST_HOST,
            project=project,
            oauth_key=credentials.get('consumer_key', None),
            oauth_secret=credentials.get('consumer_secret', None)
        )

        logger.info(
            "collection loading request: {0}".format(
                th_request.get_uri(th_collections[project].endpoint_base)))
        response = th_request.post(th_collections[project])

        # th_client uses ``httplib`` which has the ``status`` param as an int.
        # WebTest in our unit tests expects responses to have ``status`` as a
        # string and ``status_int`` is the int.  But if I mocked out ``status``
        # as an int in WebTest, then it failed internally on the response
        # within WebTest.
        # So I had to check for both values of ``status`` for the tests to pass.

        # a better fix would be to use ``requests`` in th_client: Bug 1144417
        # when that gets fixed, we can just check the in value here directly:
        #
        #     if not response or response.status == 200:
        if not response or response.status not in [200, "200 OK"]:
            errors.append({
                "project": project,
                "url": th_collections[project].endpoint_base,
                "message": response.read()
            })
    if errors:
        raise CollectionNotLoadedException(errors)


@python_2_unicode_compatible
class CollectionNotLoadedException(Exception):

    def __init__(self, error_list, *args, **kwargs):
        """
        error_list contains dictionaries, each containing
        project, url and message
        """
        super(CollectionNotLoadedException, self).__init__(args, kwargs)
        self.error_list = error_list

    def __str__(self):
        return "\n".join(
            ["[{project}] Error posting data to {url}: {message}".format(
                **error) for error in self.error_list]
        )

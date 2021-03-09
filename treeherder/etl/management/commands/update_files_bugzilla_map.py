from django.core.management.base import BaseCommand

from treeherder.etl.files_bugzilla_map import FilesBugzillaMapProcess


class Command(BaseCommand):
    """Management command to manually update bugscache from bugzilla"""

    def handle(self, *args, **options):
        process = FilesBugzillaMapProcess()
        process.run()

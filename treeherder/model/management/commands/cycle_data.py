import logging

from django.core.management.base import BaseCommand

from treeherder.model.data_cycling import TreeherderCycler, PerfherderCycler, TREEHERDER, PERFHERDER

logging.basicConfig(format='%(levelname)s:%(message)s')

TREEHERDER_SUBCOMMAND = 'from:treeherder'
PERFHERDER_SUBCOMMAND = 'from:perfherder'

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = """Cycle data that exceeds the time constraint limit"""
    CYCLER_CLASSES = {
        TREEHERDER: TreeherderCycler,
        PERFHERDER: PerfherderCycler,
    }

    def add_arguments(self, parser):
        parser.add_argument(
            '--debug',
            action='store_true',
            dest='is_debug',
            default=False,
            help='Write debug messages to stdout',
        )
        parser.add_argument(
            '--days',
            action='store',
            dest='days',
            type=int,
            help=("Data cycle interval expressed in days. This only applies to Treeherder"),
        )
        parser.add_argument(
            '--chunk-size',
            action='store',
            dest='chunk_size',
            default=100,
            type=int,
            help=(
                'Define the size of the chunks ' 'Split the job deletes into chunks of this size'
            ),
        )
        parser.add_argument(
            '--sleep-time',
            action='store',
            dest='sleep_time',
            default=0,
            type=int,
            help='How many seconds to pause between each query. Ignored when cycling performance data.',
        )
        subparsers = parser.add_subparsers(
            description='Data producers from which to expire data', dest='data_source'
        )
        subparsers.add_parser(TREEHERDER_SUBCOMMAND)  # default subcommand even if not provided

        # Perfherder will have its own specifics
        subparsers.add_parser(PERFHERDER_SUBCOMMAND)

    def handle(self, *args, **options):
        data_cycler = self.fabricate_data_cycler(options)
        data_cycler.cycle()

    def fabricate_data_cycler(self, options):
        data_source = options.pop('data_source') or TREEHERDER_SUBCOMMAND
        data_source = data_source.split(':')[1]

        cls = self.CYCLER_CLASSES[data_source]
        return cls(**options)

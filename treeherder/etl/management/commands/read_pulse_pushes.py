from django.conf import settings
from django.core.management.base import (BaseCommand,
                                         CommandError)
from kombu import (Connection,
                   Exchange)

from treeherder.etl.pulse_consumer import PushConsumer


class Command(BaseCommand):

    """
    Management command to read pushes from a set of pulse exchanges

    This adds the pushes to a celery queue called ``store_pulse_resultsets`` which
    does the actual storing of the pushes in the database.
    """

    help = "Read pushes from a set of pulse exchanges and queue for ingestion"

    def handle(self, *args, **options):
        config = settings.PULSE_DATA_INGESTION_CONFIG
        if not config:
            raise CommandError("PULSE_DATA_INGESTION_CONFIG must be set")
        sources = settings.PULSE_PUSH_SOURCES
        if not sources:
            raise CommandError("PULSE_PUSH_SOURCES must be set")

        new_bindings = []

        with Connection(config.geturl()) as connection:
            consumer = PushConsumer(connection, "resultsets")

            for source in sources:
                # When creating this exchange object, it is important that it
                # be set to ``passive=True``.  This will prevent any attempt by
                # Kombu to actually create the exchange.
                exchange = Exchange(source["exchange"], type="topic",
                                    passive=True)
                # ensure the exchange exists.  Throw an error if it doesn't
                exchange(connection).declare()

                for routing_key in source["routing_keys"]:
                    consumer.bind_to(exchange, routing_key)
                    new_binding_str = consumer.get_binding_str(
                        exchange.name,
                        routing_key)
                    new_bindings.append(new_binding_str)

                    self.stdout.write(
                        "Pulse queue {} bound to: {}".format(
                            consumer.queue_name,
                            new_binding_str
                        ))

            consumer.prune_bindings(new_bindings)

            try:
                consumer.run()
            except KeyboardInterrupt:
                self.stdout.write("Pulse Push listening stopped...")

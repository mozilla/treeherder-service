from furl import furl


def connection_should_use_tls(url):
    # Services such as RabbitMQ/MySQL running on Travis do not yet have TLS
    # certificates set up. We could try using TLS locally using self-signed certs,
    # but until Travis has support it's not overly useful.
    host = furl(url).host or url  # The url passed is already just the hostname.
    return host not in ('127.0.0.1', 'localhost', 'mysql', 'redis', 'rabbitmq')


def get_tls_redis_url(redis_url):
    """
    Returns the TLS version of a Heroku REDIS_URL string.

    Whilst Redis server (like memcached) doesn't natively support TLS, Heroku runs an stunnel
    daemon on their Redis instances, which can be connected to directly by Redis clients that
    support TLS (avoiding the need for stunnel on the client). The stunnel port is one higher
    than the Redis server port, and the informal `rediss://` scheme used to instruct clients
    to wrap the connection with TLS.

    Will convert 'redis://h:PASSWORD@INSTANCE.compute-1.amazonaws.com:8409'
          ...to: 'rediss://h:PASSWORD@INSTANCE.compute-1.amazonaws.com:8410?ssl_cert_reqs=none'

    """
    url = furl(redis_url)
    url.port += 1
    url.scheme += 's'
    # Disable TLS certificate validation (restoring the behaviour of the older redis-py 2.x),
    # since for now Heroku Redis uses self-signed certificates:
    # https://bugzilla.mozilla.org/show_bug.cgi?id=1510000
    url.args['ssl_cert_reqs'] = 'none'
    return str(url)

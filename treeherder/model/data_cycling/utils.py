def has_valid_explicit_days(func):
    def wrapper(*args, **kwargs):
        days = kwargs.get('days')
        if days is not None:
            raise ValueError('Cannot override performance data retention parameters.')
        func(*args, **kwargs)

    return wrapper

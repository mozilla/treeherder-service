import copy
import functools


def analyze(revision_data, weight_fn=None):
    """Returns the average and sample variance (s**2) of a list of floats.

    `weight_fn` is a function that takes a list index and a window width, and
    returns a weight that is used to calculate a weighted average.  For example,
    see `default_weights` or `linear_weights` below.  If no function is passed,
    `default_weights` is used and the average will be uniformly weighted.
    """
    if weight_fn is None:
        weight_fn = default_weights

    # get a weighted average for the full set of data -- this is complicated
    # by the fact that we might have multiple data points from each revision
    # which we would want to weight equally -- do this by creating a set of
    # weights only for each bucket containing (potentially) multiple results
    # for each value
    num_revisions = len(revision_data)
    weights = [weight_fn(i, num_revisions) for i in range(num_revisions)]
    weighted_sum = 0
    sum_of_weights = 0
    for i in range(num_revisions):
        weighted_sum += sum(value * weights[i] for value in revision_data[i].values)
        sum_of_weights += weights[i] * len(revision_data[i].values)
    weighted_avg = weighted_sum / sum_of_weights if num_revisions > 0 else 0.0

    # now that we have a weighted average, we can calculate the variance of the
    # whole series
    all_data = [v for datum in revision_data for v in datum.values]
    variance = (
        (sum(pow(d - weighted_avg, 2) for d in all_data) / (len(all_data) - 1))
        if len(all_data) > 1
        else 0.0
    )

    return {"avg": weighted_avg, "n": len(all_data), "variance": variance}


def default_weights(i, n):
    """A window function that weights all points uniformly."""
    return 1.0


def linear_weights(i, n):
    """A window function that falls off arithmetically.

    This is used to calculate a weighted moving average (WMA) that gives higher
    weight to changes near the point being analyzed, and smooth out changes at
    the opposite edge of the moving window.  See bug 879903 for details.
    """
    if i >= n:
        return 0.0
    return float(n - i) / float(n)


def calc_t(w1, w2, weight_fn=None):
    """Perform a Students t-test on the two sets of revision data.

    See the analyze() function for a description of the `weight_fn` argument.
    """
    if not w1 or not w2:
        return 0

    s1 = analyze(w1, weight_fn)
    s2 = analyze(w2, weight_fn)
    delta_s = s2['avg'] - s1['avg']

    if delta_s == 0:
        return 0
    if s1['variance'] == 0 and s2['variance'] == 0:
        return float('inf')

    return delta_s / (((s1['variance'] / s1['n']) + (s2['variance'] / s2['n'])) ** 0.5)


@functools.total_ordering
class RevisionDatum:
    """
    This class represents a specific revision and the set of values for it
    """

    def __init__(self, push_timestamp, push_id, values):

        # Date code was pushed
        self.push_timestamp = push_timestamp

        # What revision this data is for (usually, but not guaranteed
        # to be increasing with push_timestamp)
        self.push_id = push_id

        # data values associated with this revision
        self.values = copy.copy(values)

        # t-test score
        self.t = 0

        # Whether a perf regression or improvement was found
        self.change_detected = False

    def __eq__(self, o):
        return self.push_timestamp == o.push_timestamp

    def __lt__(self, o):
        return self.push_timestamp < o.push_timestamp

    def __repr__(self):
        values_str = '[ %s ]' % ', '.join(['%.3f' % value for value in self.values])
        return "<%s: %s, %s, %.3f, %s>" % (
            self.push_timestamp,
            self.push_id,
            values_str,
            self.t,
            self.change_detected,
        )


def detect_changes(data, min_back_window=12, max_back_window=24, fore_window=12, t_threshold=7):
    # Use T-Tests
    # Analyze test data using T-Tests, comparing data[i-j:i] to data[i:i+k]
    data = sorted(data)
    print(data)
    import time
    # time.sleep(10)

    values = [
        sum(data[i].values)/len(data[i].values)
        for i in range(1, len(data))
    ]

    print("sparky data")
    print(values)

    last_seen_regression = 0
    for i in range(1, len(data)):
        di = data[i]

        # keep on getting previous data until we've either got at least 12
        # data points *or* we've hit the maximum back window
        jw = []
        di.amount_prev_data = 0
        prev_indice = i - 1
        while (
            di.amount_prev_data < max_back_window
            and prev_indice >= 0
            and (
                (i - prev_indice)
                <= min(max(last_seen_regression, min_back_window), max_back_window)
            )
        ):
            jw.append(data[prev_indice])
            di.amount_prev_data += len(jw[-1].values)
            prev_indice -= 1

        # accumulate present + future data until we've got at least 12 values
        kw = []
        di.amount_next_data = 0
        next_indice = i
        while di.amount_next_data < fore_window and next_indice < len(data):
            kw.append(data[next_indice])
            di.amount_next_data += len(kw[-1].values)
            next_indice += 1

        di.historical_stats = analyze(jw)
        di.forward_stats = analyze(kw)

        di.t = abs(calc_t(jw, kw, linear_weights))
        # add additional historical data points next time if we
        # haven't detected a likely regression
        if di.t > t_threshold:
            last_seen_regression = 0
        else:
            last_seen_regression += 1

    # Now that the t-test scores are calculated, go back through the data to
    # find where changes most likely happened.
    for i in range(1, len(data)):
        di = data[i]

        # if we don't have enough data yet, skip for now (until more comes
        # in)
        if di.amount_prev_data < min_back_window or di.amount_next_data < fore_window:
            continue

        if di.t <= t_threshold:
            continue

        # Check the adjacent points
        prev = data[i - 1]
        if prev.t > di.t:
            continue
        # next may or may not exist if it's the last in the series
        if (i + 1) < len(data):
            next = data[i + 1]
            if next.t > di.t:
                continue

        # This datapoint has a t value higher than the threshold and higher
        # than either neighbor.  Mark it as the cause of a regression.
        di.change_detected = True

    return data

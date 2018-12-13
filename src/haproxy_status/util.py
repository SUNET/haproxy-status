def time_to_str(value):
    """
    Format number of seconds to short readable string.

    @type value: float or int

    @rtype: string
    """
    if value < 1:
        # milliseconds
        return '{!s}ms'.format(int(value * 1000))
    if value < 60:
        return '{!s}s'.format(int(value))
    if value < 3600:
        return '{!s}m'.format(int(value / 60))
    if value < 86400:
        return '{!s}h'.format(int(value / 3600))
    days = int(value / 86400)
    return '{!s}d{!s}h'.format(days, int((value % 86400) / 3600))

# -*- coding: utf-8 -*-
from __future__ import absolute_import

import socket
import csv

from collections import namedtuple


class HAProxyStatusError(Exception):
    pass


class Site(object):
    """ Wrapper object for parsed haproxy status data """
    def __init__(self):
        self._raw_fe = None
        self._raw_be = None
        self._raw_servers = []
        self.name = None

    def add_parsed(self, parsed):
        """
        :param parsed: ParsedLine
        :type parsed: namedtuple
        """
        if parsed.svname == 'FRONTEND':
            self._raw_fe = parsed
        elif parsed.svname == 'BACKEND':
            self._raw_be = parsed
        else:
            self._raw_servers += [parsed]
        if not self.name: self.name = parsed.pxname

    @property
    def frontend(self):
        return self._raw_fe

    @property
    def backend(self):
        return self._raw_be

    @property
    def servers(self):
        return self._raw_servers

    @property
    def backends_up(self):
        """
        Return backends with status UP.
        :rtype: list
        """
        return [x for x in self._raw_be if x.status == 'UP']

    @property
    def backends_down(self):
        """
        Return backends that are not UP.
        :rtype: list
        """
        return [x for x in self._raw_be if x.status != 'UP']

    @property
    def backend_uptime_min(self):
        """ Return the shortest backend uptime
            aka. how long all backends many seconds ago the last backend went down
        """
        downtime = [int(x.lastchg) for x in self.backends_up]
        return min(downtime)

    @property
    def backend_downtime_min(self):
        """ Return the shortest backend downtime
            aka. how many seconds ago the last backend went down
        """
        downtime = [int(x.lastchg) for x in self.backends_down]
        return min(downtime)


def haproxy_execute(cmd, stats_url, logger):
    if stats_url.startswith('http'):
        import requests

        logger.debug('Fetching haproxy stats from {}'.format(stats_url))
        try:
            data = requests.get(stats_url).text
        except requests.exceptions.ConnectionError as exc:
            raise HAProxyStatusError('Failed fetching status from {}: {}'.format(stats_url, exc))
    else:
        socket_fn = stats_url
        if socket_fn.startswith('file://'):
            socket_fn = socket_fn[len('file://'):]
        logger.debug('opening AF_UNIX socket {} for command "{}"'.format(socket_fn, cmd))
        try:
            client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            client.connect(socket_fn)
            cmd = cmd + '\n'
            client.send(cmd.encode('utf-8'))
        except Exception as exc:
            logger.error('Failed sending command {!r} to socket {}: {}'.format(cmd, socket_fn, exc))
            logger.exception(exc)
            return None

        data = ''
        while True:
            this = client.recv(1)
            if not this:
                break
            data += this.decode('utf-8')

    #logger.debug('haproxy result: {}'.format(data))
    logger.debug('haproxy command {!r} result: {} bytes'.format(cmd, len(data)))
    return data


def get_status(stats_url, logger):
    """
    haproxy 'show stat' returns _a lot_ of different metrics for each frontend and backend
    in the system. Parse the returned CSV data and return the 'status' value for
    frontends and backends, example:

    {'app.example.org': Site(frontend='OPEN',
                             backend='UP',
                             groups={'default': {
                                       'dash-fre-1.eduid.se_v4': 'UP',
                                       'dash-tug-1.eduid.se_v4': 'UP'
                                       'failpage': 'no check'},
                                     'new': {
                                        'apps-tug-1.eduid.se_v4': 'UP',
                                        'apps-fre-1.eduid.se_v4': 'UP',
                                        'failpage': 'no check'}}
                            ),
    ...
    Example haproxy stats URL: 'http://127.0.0.1:9000/haproxy_stats;csv'

    :param stats_url: Path to haproxy socket, or a HTTP(S) URL to fetch from.
    :return: Status dict as detailed above
    :rtype: dict
    """
    data = haproxy_execute('show stat', stats_url, logger)
    if not data:
        return None
    if not data.startswith('# '):
        logger.error('Unknown status response from haproxy: {}'.format(data))
    lines = []
    for this in data.split('\n'):
        # remove extra comma at the end of all lines, and remove empty lines
        if this:
            if this[-1:] == ',':
                this = this[:-1]
            lines += [this]
    if len(lines) < 2:
        logger.warning('haproxy did not return status for any backends: {}'.format(data))
        return None
    # The first line is the legend, e.g.
    # # pxname,svname,qcur,qmax,scur,smax,slim,stot,bin,bout,dreq,...,status,...
    ParsedLine = namedtuple('ParsedLine', lines[0][2:])
    # parse all the lines with real data
    res = {}
    for values in csv.reader(lines[1:]):
        try:
            this = ParsedLine(*values)
        except Exception as exc:
            logger.warning('Bad CSV data: {!r}: {!s}'.format(values, exc))
            continue
        #logger.debug('processing site {!r}'.format(this.pxname))
        sitename = this.pxname.split('__')[0]

        site = res.get(sitename, Site())
        site.add_parsed(this)
        res[sitename] = site

    #logger.debug('Parsed status: {}'.format(res))

    return res.values()
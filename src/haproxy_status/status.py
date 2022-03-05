# -*- coding: utf-8 -*-
import csv
import logging
import socket
from dataclasses import dataclass
from typing import Dict, List, NamedTuple, Optional, cast


class HAProxyStatusError(Exception):
    pass


@dataclass
class SiteInfo(object):
    """
    haproxy CSV record as a namedtuple.

    The dynamic NamedTuple ParsedLine is casted to this class to help typing.
    Fields from the CSV not listed below are still present, but access to them
    will of course produce typing errors.
    """

    pxname: str
    svname: str
    status: str
    lastchg: str
    # properties known to be used by other scripts, such as Särimner's haproxy-status
    act: str
    addr: str
    check_desc: str
    last_chk: str


class Site(object):
    """
    Wrapper object for parsed haproxy status data.

    name is haproxy pxname, which in särimner is ${site_name}__${group}
    """

    def __init__(self, name: str):
        self._raw_fe: List[SiteInfo] = []
        self._raw_be: List[SiteInfo] = []
        self._raw_servers: List[SiteInfo] = []
        self.name = name
        name_parts = name.split('__')
        self.site_name = name_parts[0]
        self.group = name_parts[1] if len(name_parts) > 1 else None

    def __str__(self):
        return '<Site {}: group={}, fe={}, be={}>'.format(
            self.site_name, self.group, len(self._raw_fe), len(self._raw_be)
        )

    def add_parsed(self, parsed: SiteInfo):
        """
        :param parsed: ParsedLine
        :type parsed: namedtuple
        """
        if parsed.svname == 'FRONTEND':  # type: ignore
            self._raw_fe += [parsed]
        elif parsed.svname == 'BACKEND':  # type: ignore
            self._raw_be += [parsed]
        else:
            self._raw_servers += [parsed]

    @property
    def frontend(self) -> List[SiteInfo]:
        return self._raw_fe

    @property
    def backend(self) -> List[SiteInfo]:
        return self._raw_be

    @property
    def servers(self) -> List[SiteInfo]:
        return self._raw_servers

    @property
    def backends_up(self) -> List[SiteInfo]:
        """
        Return backends with status UP.
        """
        return [x for x in self._raw_be if x.status == 'UP']

    @property
    def backends_down(self) -> List[SiteInfo]:
        """
        Return backends that are not UP.
        """
        return [x for x in self._raw_be if x.status != 'UP']

    @property
    def backend_uptime_min(self) -> int:
        """ Return the shortest backend uptime
            aka. how long all backends many seconds ago the last backend went down
        """
        downtime = [int(x.lastchg) for x in self.backends_up]
        return min(downtime)

    @property
    def backend_downtime_min(self) -> int:
        """ Return the shortest backend downtime
            aka. how many seconds ago the last backend went down
        """
        downtime = [int(x.lastchg) for x in self.backends_down]
        return min(downtime)


def haproxy_execute(cmd: str, stats_url: str, logger: logging.Logger) -> Optional[str]:
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
            socket_fn = socket_fn[len('file://') :]
        logger.debug('opening AF_UNIX socket {} for command "{}"'.format(socket_fn, cmd))
        try:
            client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            client.connect(socket_fn)
            cmd = cmd + '\n'
            client.send(cmd.encode('utf-8'))
        except ConnectionRefusedError:
            logger.info('haproxy refused the connection on socket {}, maybe it is not running?'.format(socket_fn))
            return None
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

    # logger.debug('haproxy result: {}'.format(data))
    logger.debug('haproxy command {!r} result: {} bytes'.format(cmd, len(data)))
    return data


def get_status(stats_url: str, logger: logging.Logger) -> Optional[List[Site]]:
    """
    haproxy 'show stat' returns _a lot_ of different metrics for each frontend and backend
    in the system. Parse the returned CSV data and return a Site instance per haproxy pxname (site name + group).

    Example:

        [Site(frontend='OPEN',
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
    """
    data = haproxy_execute('show stat', stats_url, logger)
    logger.debug(f'haproxy show stat result: {data}')
    if not data:
        return None
    if not data.startswith('# '):
        logger.error('Unknown status response from haproxy: {}'.format(data))
    lines = []  # type: List[str]
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
    fields = []
    unknown_index = 0
    for field_name in lines[0][2:].split(','):
        if field_name == '-':
            # haproxy 2.4 suddenly has a field named '-' which isn't accepted by NamedTuple
            field_name = f'unknown{unknown_index}'
            unknown_index += 1
        fields += [(field_name, str,)]
    # Create a NamedTuple dynamically based on the legend we got from haproxy.
    # Unfortunately, this is not accepted by mypy, so the result is casted to SiteInfo
    # to not end up with countless type ignores.
    #
    # An alternative would be to use a dataclass instead, but then we would have to
    # update it when haproxy changes and risk script breakage on updates of haproxy.
    class ParsedLine(NamedTuple('ParsedLine', fields)):  # type: ignore
        """
        Subclass a namedtuple to not clutter string representation with empty values from haproxy.
        """

        def __str__(self):
            values = []
            empty = []
            for k, v in self._asdict().items():
                if v and v != '0':
                    values += ['{}={}'.format(k, v)]
                else:
                    empty += [k]
            return '<{} non-empty values:\n  {}\nempty: {}>'.format(
                self.__class__.__name__, ',\n  '.join(sorted(values)), ','.join(empty)
            )

    # parse all the lines with real data
    res: Dict[str, Site] = {}
    for values in csv.reader(lines[1:]):
        try:
            _this = ParsedLine(*values)  # type: ignore
            info = cast(SiteInfo, _this)
        except Exception as exc:
            logger.warning('Bad CSV data: {!r}: {!s}'.format(values, exc))
            continue
        # logger.debug('processing site {!r}'.format(this.pxname))
        site = res.get(info.pxname, Site(name=info.pxname))
        site.add_parsed(info)
        res[info.pxname] = site

    # logger.debug('Parsed status: {}'.format(res))

    return list(res.values())

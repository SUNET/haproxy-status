# -*- coding: utf-8 -*-
import logging
import os
import random
import time
from typing import Any, Dict, List, Mapping, Optional

import yaml
from flask import Flask, has_request_context, request
from werkzeug.middleware.proxy_fix import ProxyFix

from haproxy_status.status import Site, SiteInfo
from haproxy_status.util import time_to_str

__author__ = 'ft'


class MyState(object):
    def __init__(self, config: Mapping[str, Any], logger: logging.Logger):
        self.config = config
        self.logger = logger
        self._update_time: Optional[int] = None
        self._hap_status: Dict[str, Dict[str, Any]] = {}
        self._next_fetch_hap_status = 0
        self._last_status = ''

    def register_hap_status(self, hap_status: List[Site]):
        self._update_time = int(time.time())

        for this in hap_status:
            for be in this.servers:
                self._register_server_state(this.name, be)
            for be in this.backend:
                self._register_server_state(this.name, be)

        self.logger.debug('State: {!r}'.format(self._hap_status))

    def is_admin_down(self) -> bool:
        """
        Check for a file signalling that we should set the status to ADMIN_DOWN.

        Built in a way to support further enhancements such as automatic expiry
        etc.
        """

        def load_control_file(fn: str) -> Optional[Dict]:
            path = os.path.join(self.config['SIGNAL_DIRECTORY'], fn)
            try:
                with open(path, 'r') as fd:
                    try:
                        res = yaml.safe_load(fd)
                        if res is None:
                            return {}
                        return res
                    except yaml.YAMLError:
                        # file exists, so err on the safe side and say ADMIN DOWN
                        return {}
            except FileNotFoundError:
                return None

        if self.config['SERVICE_NAME']:
            data = load_control_file(self.config['SERVICE_NAME'])
            if data is not None:
                return True

        data = load_control_file('common')
        if data is not None:
            return True

        return False

    def get_status(self):
        age = 0
        if self._update_time is not None:
            age = time.time() - self._update_time
        res = {
            'status': 'STATUS_UNKNOWN',
            'reason': 'No backend data received from haproxy',
            'ttl': int(self.config['FETCH_HAPROXY_STATUS_INTERVAL'] - age),
        }
        count = 0
        down_count = 0
        msg = []
        for this, data in self._hap_status.items():
            if 'BACKEND' not in data:
                continue
            count += 1
            be = data['BACKEND']
            status = be['status']
            if status == 'UP':
                uptime = int(time.time()) - be['change_ts']
                if uptime >= self.config['HEALTHY_BACKEND_UPTIME']:
                    continue
                status = '(RE)STARTING'
            down_count += 1
            downtime = time_to_str(int(time.time()) - be['change_ts'])
            msg += ['{} is {} ({})'.format(this, status, downtime)]

        plural = '' if count == 1 else 's'
        if down_count:
            res['status'] = 'STATUS_DOWN'
            res['reason'] = '{}/{} backend{} not UP: {}'.format(down_count, count, plural, ', '.join(msg))
        elif count:
            res['status'] = 'STATUS_UP'
            res['reason'] = '{} backend{} UP'.format(count, plural)

        if self.is_admin_down():
            res['status'] = 'STATUS_ADMIN_DOWN'

        if res['status'] != self._last_status:
            self._last_status = res['status']
            self.logger.info('Status changed to {} {}'.format(res['status'], res['reason']))
            if self.config['STATUS_OUTPUT_FILENAME']:
                # export to docker health check
                with open(self.config['STATUS_OUTPUT_FILENAME'], 'w') as fd:
                    fd.write('{} {}\n'.format(res['status'], res['reason']))

        return res

    def should_fetch_hap_status(self) -> bool:
        if time.time() >= self._next_fetch_hap_status:
            # move the next-fetch timestamp forward in time, and add a tiny bit of fuzzing
            self._next_fetch_hap_status = time.time() + self.config['FETCH_HAPROXY_STATUS_INTERVAL'] + random.random()
            return True
        return False

    def _register_server_state(self, name: str, server: SiteInfo) -> None:
        """
        :param name: Site name
        :param server: Parsed site info
        """
        srv_name = server.svname
        srv_status = server.status
        if name not in self._hap_status:
            self._hap_status[name] = {}
        if srv_name not in self._hap_status[name]:
            self._hap_status[name][srv_name] = {}
        old_status = self._hap_status[name][srv_name].get('status')
        if old_status != srv_status:
            if srv_name != 'BACKEND':
                if old_status is None:
                    self.logger.info('Backend {} server {} initial status is {}'.format(name, srv_name, srv_status))
                else:
                    self.logger.info('Backend {} server {} changed status to {}'.format(name, srv_name, srv_status))
                # Debug log all the info we got on server changes. We once saw haproxy end up with
                # the wrong IP for a backend and had no way to know when or how it changed.
                self.logger.debug('All server data: {}'.format(server))
                if srv_status == 'DOWN':
                    self._hap_status[name][srv_name]['next_log_down'] = (
                        int(time.time()) + self.config['LOG_DOWN_INTERVAL']
                    )
            self._hap_status[name][srv_name]['status'] = srv_status
            self._hap_status[name][srv_name]['change_ts'] = int(time.time()) - int(server.lastchg)
        else:
            if (
                srv_name != 'BACKEND'
                and srv_status == 'DOWN'
                and int(time.time()) >= self._hap_status[name][srv_name]['next_log_down']
            ):
                downtime = time_to_str(int(time.time() - self._hap_status[name][srv_name]['change_ts']))
                self.logger.info('Site {} server {} is still DOWN ({})'.format(name, srv_name, downtime))


# from http://stackoverflow.com/questions/27775026/provide-extra-information-to-flasks-app-logger
class CustomFormatter(logging.Formatter):
    def format(self, record):
        record.path = '(no path)'
        record.endpoint = '(no endpoint)'
        record.remote_addr = 'None'
        if has_request_context():
            record.path = request.path
            record.endpoint = request.endpoint
            record.remote_addr = request.remote_addr
        return super(CustomFormatter, self).format(record)


def init_app(name, config=None):
    """
    :param name: The name of the instance, it will affect the configuration loaded.
    :param config: any additional configuration settings. Specially useful
                   in test cases

    :type name: str
    :type config: dict

    :return: the flask app
    :rtype: flask.Flask
    """
    app = Flask(name)
    app.wsgi_app = ProxyFix(app.wsgi_app)

    # Load configuration
    app.config.from_object('haproxy_status.settings.common')
    app.config.from_envvar('haproxy_status_SETTINGS', silent=True)

    # Load optional init time settings
    if config is not None:
        app.config.update(config)

    # load SERVICE_NAME from environment variable 'haproxy_status_name' to
    # make it easy to set it from docker compose files.
    if 'SERVICE_NAME' in os.environ:
        app.config.update({'SERVICE_NAME': os.environ['SERVICE_NAME']})

    # Register views. Import here to avoid a Flask circular dependency.
    from haproxy_status.views import haproxy_status_views

    app.register_blueprint(haproxy_status_views)

    # set up logging
    custom_format = '%(asctime)s - %(levelname)s ; %(message)s'
    for handler in app.logger.handlers:
        handler.setFormatter(CustomFormatter(fmt=custom_format))
    app.logger.setLevel(app.config['LOG_LEVEL'])

    app.mystate = MyState(app.config, app.logger)

    # Get status to trigger writing the STATUS_OUTPUT_FILENAME file
    _status = app.mystate.get_status()

    app.logger.info(f'Application {name} initialised with initial status: {_status}')
    return app

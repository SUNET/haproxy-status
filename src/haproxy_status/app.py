# -*- coding: utf-8 -*-

from __future__ import absolute_import

import time
import random
import logging

from flask import Flask, request, has_request_context, current_app
from werkzeug.contrib.fixers import ProxyFix

import haproxy_status
from haproxy_status.util import time_to_str

__author__ = 'ft'


class MyState(object):

    def __init__(self):
        self._update_time = None
        self._hap_status = {}
        self._next_fetch_hap_status = 0

    def register_hap_status(self, hap_status):
        self._update_time = int(time.time())

        for this in hap_status:
            for be in this.servers:
                self._register_server_state(this.name, be)
            if this.backend:
                self._register_server_state(this.name, this.backend)

        current_app.logger.debug('State: {!r}'.format(self._hap_status))

    def get_status(self):
        age = time.time() - self._update_time
        res = {'status': 'STATUS_UNKNOWN',
               'reason': 'No backend data received from haproxy',
               'ttl': int(current_app.config['FETCH_HAPROXY_STATUS_INTERVAL'] - age),
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
                if uptime >= current_app.config['HEALTHY_BACKEND_UPTIME']:
                    continue
                status = '(RE)STARTING'
            down_count += 1
            downtime = time_to_str(int(time.time()) - be['change_ts'])
            msg += ['{} is {} ({})'.format(this, status, downtime)]

        plural = '' if count is 1 else 's'
        if down_count:
            res['status'] = 'STATUS_DOWN'
            res['reason'] = '{}/{} backend{} not UP: {}'.format(down_count, count, plural, ', '.join(msg))
        elif count:
            res['status'] = 'STATUS_UP'
            res['reason'] = '{} backend{} UP'.format(count, plural)

        return res

    def should_fetch_hap_status(self):
        if time.time() >= self._next_fetch_hap_status:
            # move the next-fetch timestamp forward in time, and add a tiny bit of fuzzing
            self._next_fetch_hap_status = time.time() +\
                                          current_app.config['FETCH_HAPROXY_STATUS_INTERVAL'] +\
                                          random.random()
            return True
        return False

    def _register_server_state(self, name, server):
        """
        :param name: Site name
        :param server: ParsedLine
        :type server: namedtuple
        :return:
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
                    current_app.logger.info('Backend {} server {} initial status is {}'.format(
                        name, srv_name, srv_status))
                else:
                    current_app.logger.info('Backend {} server {} changed status to {}'.format(
                        name, srv_name, srv_status))
                # Debug log all the info we got on server changes. We once saw haproxy end up with
                # the wrong IP for a backend and had no way to know when or how it changed.
                current_app.logger.debug('All server data: {}'.format(server))
                if srv_status == 'DOWN':
                    self._hap_status[name][srv_name]['next_log_down'] = int(time.time()) + \
                                                                        current_app.config['LOG_DOWN_INTERVAL']
            self._hap_status[name][srv_name]['status'] = srv_status
            self._hap_status[name][srv_name]['change_ts'] = int(time.time()) - int(server.lastchg)
        else:
            if srv_name != 'BACKEND' and srv_status == 'DOWN' and \
                    int(time.time()) >= self._hap_status[name][srv_name]['next_log_down']:
                downtime = time_to_str(int(time.time() - self._hap_status[name][srv_name]['change_ts']))
                current_app.logger.info('Site {} server {} is still DOWN ({})'.format(
                    name, srv_name, downtime))


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

    # Register views. Import here to avoid a Flask circular dependency.
    from haproxy_status.views import haproxy_status_views
    app.register_blueprint(haproxy_status_views)

    # set up logging
    custom_format = '%(asctime)s %(remote_addr)s - %(levelname)s %(name)s "%(path)s" "%(endpoint)s" ; %(message)s'
    for handler in app.logger.handlers:
        handler.setFormatter(CustomFormatter(fmt = custom_format))

    app.mystate = MyState()

    app.logger.info('Application {!r} initialized'.format(name))
    return app

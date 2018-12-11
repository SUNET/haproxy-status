# -*- coding: utf-8 -*-

from __future__ import absolute_import

import haproxystatus
import logging

from flask import Flask, request, has_request_context
from werkzeug.contrib.fixers import ProxyFix


__author__ = 'ft'


class MyState(object):

    def __init__(self, app):
        pass


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
    app.config.from_object('haproxystatus.settings.common')
    app.config.from_envvar('haproxystatus_SETTINGS', silent=True)

    # Load optional init time settings
    if config is not None:
        app.config.update(config)

    # Register views. Import here to avoid a Flask circular dependency.
    from haproxystatus.views import haproxystatus_views
    app.register_blueprint(haproxystatus_views)

    app.mystate = MyState(app)

    # set up logging
    custom_format = '%(asctime)s %(remote_addr)s - %(levelname)s %(name)s "%(path)s" "%(endpoint)s" ; %(message)s'
    for handler in app.logger.handlers:
        handler.setFormatter(CustomFormatter(fmt = custom_format))

    app.logger.info('Application {!r} initialized'.format(name))
    return app

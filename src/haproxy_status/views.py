# -*- coding: utf-8 -*-
from __future__ import absolute_import

from flask import Blueprint, abort, current_app, jsonify

from haproxy_status.status import get_status

__author__ = 'ft'

haproxy_status_views = Blueprint('haproxy_status', __name__, url_prefix='')


@haproxy_status_views.route('/status', methods=['GET'])
def status():
    if current_app.mystate.should_fetch_hap_status():
        hap_status = get_status(current_app.config['STATS_URL'], current_app.logger)
        if hap_status is None:
            return jsonify({'status': 'FAIL'})

        current_app.mystate.register_hap_status(hap_status)

    res = current_app.mystate.get_status()
    current_app.logger.debug('Response: {}'.format(res))

    if res['status'] == 'STATUS_ADMIN_DOWN' and current_app.config['RETURN_404_ON_ADMIN_DOWN']:
        abort(404)

    return jsonify(res)


@haproxy_status_views.route('/ping', methods=['GET', 'POST'])
def ping():
    return 'pong\n'

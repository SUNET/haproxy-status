# -*- coding: utf-8 -*-
from __future__ import absolute_import

import os
import re

from flask import Blueprint, current_app, request, abort, jsonify


__author__ = 'ft'

haproxy_status_views = Blueprint('haproxy_status', __name__, url_prefix='')


@haproxy_status_views.route('/status', methods=['GET'])
def status():
    return jsonify({'success': True})

@haproxy_status_views.route('/ping', methods=['GET', 'POST'])
def ping():
    return 'pong\n'

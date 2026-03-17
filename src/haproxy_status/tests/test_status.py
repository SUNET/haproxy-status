#!/usr/bin/python
#
# Copyright (c) 2018 NORDUnet A/S
# All rights reserved.
#
#   Redistribution and use in source and binary forms, with or
#   without modification, are permitted provided that the following
#   conditions are met:
#
#     1. Redistributions of source code must retain the above copyright
#        notice, this list of conditions and the following disclaimer.
#     2. Redistributions in binary form must reproduce the above
#        copyright notice, this list of conditions and the following
#        disclaimer in the documentation and/or other materials provided
#        with the distribution.
#     3. Neither the name of the NORDUnet nor the names of its
#        contributors may be used to endorse or promote products derived
#        from this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
# "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
# LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS
# FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE
# COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT,
# INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING,
# BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
# LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
# CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT
# LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN
# ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.
#
# Author : Fredrik Thulin <fredrik@thulin.net>
#

"""
Test the API backend.
"""

import time
import unittest
from dataclasses import dataclass
from unittest.mock import patch

from werkzeug.exceptions import NotFound

import haproxy_status

TEST_CONFIG = {
    "DEBUG": True,
    "TESTING": True,
    "PROPAGATE_EXCEPTIONS": True,
    "PRESERVE_CONTEXT_ON_EXCEPTION": True,
    "TRAP_HTTP_EXCEPTIONS": True,
    "TRAP_BAD_REQUEST_ERRORS": True,
}


@dataclass
class MockSiteInfo:
    """Mock SiteInfo for testing. Mimics the fields accessed by _register_server_state."""

    pxname: str = "test_backend"
    svname: str = "server1"
    status: str = "UP"
    lastchg: str = "100"
    chkfail: str = "0"
    chkdown: str = "0"
    downtime: str = "0"
    act: str = "1"
    addr: str = "127.0.0.1:8080"
    check_desc: str = "Layer4 check passed"
    last_chk: str = ""


class AppTests(unittest.TestCase):
    """Base TestCase for those tests that need a full environment setup"""

    def setUp(self, config=TEST_CONFIG):
        super(AppTests, self).setUp()
        self.app = haproxy_status.app.init_app("unittest_app", config)
        self.client = self.app.test_client()


class BaseAppTests(AppTests):
    def test_bad_request(self):
        """
        Verify bad requests are rejected
        """
        with self.assertRaises(NotFound):
            self.client.get("/nosuchendpoint")


class FlappingDetectionTests(AppTests):
    """Tests for server flapping detection."""

    def _register_server(
        self, svname="server1", status="UP", lastchg="100", chkdown="0"
    ):
        """Helper to register a server state update."""
        server = MockSiteInfo(
            svname=svname, status=status, lastchg=lastchg, chkdown=chkdown
        )
        self.app.mystate._register_server_state("test_backend", server)

    def _register_backend(self, status="UP", lastchg="100", chkdown="0"):
        """Helper to register a BACKEND row."""
        server = MockSiteInfo(
            svname="BACKEND", status=status, lastchg=lastchg, chkdown=chkdown
        )
        self.app.mystate._register_server_state("test_backend", server)

    def test_stable_server_not_flapping(self):
        """A server with stable chkdown and growing lastchg should not be flagged as flapping."""
        self._register_server(lastchg="100", chkdown="0")
        self._register_server(lastchg="115", chkdown="0")
        self._register_server(lastchg="130", chkdown="0")

        self.assertFalse(
            self.app.mystate._is_server_flapping("test_backend", "server1")
        )

    def test_chkdown_increase_records_transition(self):
        """When chkdown increases between polls, transitions should be recorded."""
        self._register_server(lastchg="100", chkdown="0")
        self._register_server(lastchg="5", chkdown="1")

        srv_data = self.app.mystate._hap_status["test_backend"]["server1"]
        self.assertEqual(len(srv_data["transitions"]), 1)

    def test_chkdown_multiple_increases_records_all(self):
        """When chkdown increases by more than 1, all transitions should be recorded."""
        self._register_server(lastchg="100", chkdown="0")
        # Server went down 3 times between polls
        self._register_server(lastchg="5", chkdown="3")

        srv_data = self.app.mystate._hap_status["test_backend"]["server1"]
        self.assertEqual(len(srv_data["transitions"]), 3)

    def test_lastchg_regression_records_transition(self):
        """When lastchg gets smaller without chkdown change, a transition should be recorded."""
        self._register_server(lastchg="100", chkdown="0")
        # lastchg went from 100 to 5, but chkdown didn't change (e.g., MAINT transition)
        self._register_server(lastchg="5", chkdown="0")

        srv_data = self.app.mystate._hap_status["test_backend"]["server1"]
        self.assertEqual(len(srv_data["transitions"]), 1)

    def test_lastchg_regression_not_double_counted_with_chkdown(self):
        """When both chkdown and lastchg indicate a transition, don't double-count."""
        self._register_server(lastchg="100", chkdown="0")
        # Both signals fire: chkdown increased and lastchg regressed
        self._register_server(lastchg="5", chkdown="1")

        srv_data = self.app.mystate._hap_status["test_backend"]["server1"]
        # Should be 1, not 2 (chkdown takes precedence)
        self.assertEqual(len(srv_data["transitions"]), 1)

    def test_flapping_threshold_triggers(self):
        """Server should be flagged as flapping after reaching the threshold."""
        # Default threshold is 3 transitions in 300s window
        self._register_server(lastchg="100", chkdown="0")
        self._register_server(lastchg="5", chkdown="1")
        self._register_server(lastchg="20", chkdown="2")
        self._register_server(lastchg="5", chkdown="3")

        self.assertTrue(self.app.mystate._is_server_flapping("test_backend", "server1"))

    def test_flapping_below_threshold(self):
        """Server should not be flagged as flapping below the threshold."""
        self._register_server(lastchg="100", chkdown="0")
        self._register_server(lastchg="5", chkdown="1")
        self._register_server(lastchg="20", chkdown="2")

        self.assertFalse(
            self.app.mystate._is_server_flapping("test_backend", "server1")
        )

    def test_flapping_transitions_expire(self):
        """Old transitions outside the window should be pruned and not count."""
        now = int(time.time())
        self._register_server(lastchg="100", chkdown="0")

        # Manually inject old transitions that are outside the window
        srv_data = self.app.mystate._hap_status["test_backend"]["server1"]
        srv_data["transitions"] = [now - 400, now - 350, now - 310]

        # Register again to trigger pruning (within window, no new transition)
        self._register_server(lastchg="115", chkdown="0")

        # Old transitions should have been pruned
        self.assertFalse(
            self.app.mystate._is_server_flapping("test_backend", "server1")
        )

    def test_get_status_reports_flapping_as_down(self):
        """get_status should report STATUS_DOWN when a server is flapping."""
        # Register server and backend
        self._register_server(lastchg="100", chkdown="0")
        self._register_backend(lastchg="100", chkdown="0")
        self.app.mystate._update_time = int(time.time())

        # Trigger enough transitions to be flapping
        self._register_server(lastchg="5", chkdown="1")
        self._register_server(lastchg="20", chkdown="2")
        self._register_server(lastchg="5", chkdown="3")

        status = self.app.mystate.get_status()
        self.assertEqual(status["status"], "STATUS_DOWN")
        self.assertIn("FLAPPING", status["reason"])

    def test_get_status_up_when_not_flapping(self):
        """get_status should report STATUS_UP when server is stable and UP."""
        self._register_server(lastchg="100", chkdown="0")
        self._register_backend(lastchg="100", chkdown="0")
        self.app.mystate._update_time = int(time.time())

        status = self.app.mystate.get_status()
        self.assertEqual(status["status"], "STATUS_UP")

    def test_backend_row_not_checked_for_flapping(self):
        """The BACKEND row itself should not be checked for flapping, only servers."""
        self._register_server(lastchg="100", chkdown="0")
        self._register_backend(lastchg="100", chkdown="0")

        # Cause BACKEND row to have lastchg regression (shouldn't trigger flapping)
        self._register_backend(lastchg="5", chkdown="0")

        # BACKEND rows are skipped in _register_server_state for flapping detection
        self.assertNotIn(
            "transitions",
            self.app.mystate._hap_status["test_backend"].get("BACKEND", {}),
        )

"""
Tests for the pydantic-settings based Settings class.
"""

import os
import unittest
import warnings
from unittest.mock import patch

from haproxy_status.config import Settings


class SettingsDefaultsTests(unittest.TestCase):
    """Test that Settings has the correct default values matching settings/common.py."""

    def test_log_level_default(self):
        settings = Settings()
        self.assertEqual(settings.log_level, "INFO")

    def test_backend_dir_default(self):
        settings = Settings()
        self.assertEqual(settings.backend_dir, "/backends")

    def test_stats_url_default(self):
        settings = Settings()
        self.assertEqual(settings.stats_url, "/var/run/haproxy-control/stats")

    def test_log_down_interval_default(self):
        settings = Settings()
        self.assertEqual(settings.log_down_interval, 180)

    def test_fetch_haproxy_status_interval_default(self):
        settings = Settings()
        self.assertEqual(settings.fetch_haproxy_status_interval, 15)

    def test_status_output_filename_default(self):
        settings = Settings()
        self.assertEqual(settings.status_output_filename, "/dev/shm/haproxy-status.txt")

    def test_signal_directory_default(self):
        settings = Settings()
        self.assertEqual(settings.signal_directory, "/var/haproxy-status")

    def test_service_name_default(self):
        settings = Settings()
        self.assertIsNone(settings.service_name)

    def test_return_404_on_admin_down_default(self):
        settings = Settings()
        self.assertTrue(settings.return_404_on_admin_down)

    def test_flapping_threshold_default(self):
        settings = Settings()
        self.assertEqual(settings.flapping_threshold, 3)

    def test_flapping_window_default(self):
        settings = Settings()
        self.assertEqual(settings.flapping_window, 300)


class SettingsEnvVarOverrideTests(unittest.TestCase):
    """Test that settings can be overridden via environment variables."""

    def test_override_log_level(self):
        with patch.dict(os.environ, {"LOG_LEVEL": "DEBUG"}):
            settings = Settings()
            self.assertEqual(settings.log_level, "DEBUG")

    def test_override_stats_url(self):
        with patch.dict(os.environ, {"STATS_URL": "http://localhost:9000/stats"}):
            settings = Settings()
            self.assertEqual(settings.stats_url, "http://localhost:9000/stats")

    def test_override_int_from_string(self):
        """Env vars are strings; pydantic should coerce to int."""
        with patch.dict(os.environ, {"LOG_DOWN_INTERVAL": "300"}):
            settings = Settings()
            self.assertEqual(settings.log_down_interval, 300)
            self.assertIsInstance(settings.log_down_interval, int)

    def test_override_bool_from_string(self):
        """Env vars are strings; pydantic should coerce to bool."""
        with patch.dict(os.environ, {"RETURN_404_ON_ADMIN_DOWN": "false"}):
            settings = Settings()
            self.assertFalse(settings.return_404_on_admin_down)

    def test_override_service_name(self):
        """SERVICE_NAME env var should set service_name (case-insensitive)."""
        with patch.dict(os.environ, {"SERVICE_NAME": "my-service"}):
            settings = Settings()
            self.assertEqual(settings.service_name, "my-service")

    def test_override_fetch_interval(self):
        with patch.dict(os.environ, {"FETCH_HAPROXY_STATUS_INTERVAL": "30"}):
            settings = Settings()
            self.assertEqual(settings.fetch_haproxy_status_interval, 30)


class SettingsComputedHealthyBackendUptimeTests(unittest.TestCase):
    """Test that healthy_backend_uptime is computed from fetch_haproxy_status_interval."""

    def test_default_computed_value(self):
        """Default: 15 * 2 + 2 = 32."""
        settings = Settings()
        self.assertEqual(settings.healthy_backend_uptime, 32)

    def test_computed_from_custom_fetch_interval(self):
        """When fetch interval is overridden, healthy_backend_uptime should recompute."""
        with patch.dict(os.environ, {"FETCH_HAPROXY_STATUS_INTERVAL": "30"}):
            settings = Settings()
            self.assertEqual(settings.healthy_backend_uptime, 62)  # 30 * 2 + 2

    def test_explicit_override(self):
        """When explicitly set via env var, the computed value should be ignored."""
        with patch.dict(os.environ, {"HEALTHY_BACKEND_UPTIME": "100"}):
            settings = Settings()
            self.assertEqual(settings.healthy_backend_uptime, 100)

    def test_explicit_override_with_custom_fetch_interval(self):
        """Explicit HEALTHY_BACKEND_UPTIME takes precedence over computation."""
        with patch.dict(
            os.environ,
            {"FETCH_HAPROXY_STATUS_INTERVAL": "30", "HEALTHY_BACKEND_UPTIME": "50"},
        ):
            settings = Settings()
            self.assertEqual(settings.healthy_backend_uptime, 50)


class DeprecatedEnvVarTests(unittest.TestCase):
    """Test that haproxy_status_SETTINGS env var triggers a deprecation warning."""

    def test_deprecated_env_var_emits_warning(self):
        """Setting haproxy_status_SETTINGS should emit a DeprecationWarning."""
        with patch.dict(os.environ, {"haproxy_status_SETTINGS": "/some/path.py"}):
            import haproxy_status

            with warnings.catch_warnings(record=True) as w:
                warnings.simplefilter("always")
                app = haproxy_status.app.init_app("test_deprecation")
                deprecation_warnings = [
                    x for x in w if issubclass(x.category, DeprecationWarning)
                ]
                self.assertEqual(len(deprecation_warnings), 1)
                self.assertIn(
                    "haproxy_status_SETTINGS", str(deprecation_warnings[0].message)
                )

    def test_no_warning_without_deprecated_env_var(self):
        """No DeprecationWarning when haproxy_status_SETTINGS is not set."""
        # Ensure the env var is NOT set
        env = os.environ.copy()
        env.pop("haproxy_status_SETTINGS", None)
        with patch.dict(os.environ, env, clear=True):
            import haproxy_status

            with warnings.catch_warnings(record=True) as w:
                warnings.simplefilter("always")
                app = haproxy_status.app.init_app("test_no_deprecation")
                deprecation_warnings = [
                    x for x in w if issubclass(x.category, DeprecationWarning)
                ]
                self.assertEqual(len(deprecation_warnings), 0)


class FlaskConfigIntegrationTests(unittest.TestCase):
    """Test that Settings are properly wired into Flask app.config."""

    def test_flask_config_has_uppercase_keys(self):
        """Flask app.config should have UPPERCASE versions of all settings."""
        import haproxy_status

        app = haproxy_status.app.init_app("test_flask_config")
        self.assertEqual(app.config["LOG_LEVEL"], "INFO")
        self.assertEqual(app.config["STATS_URL"], "/var/run/haproxy-control/stats")
        self.assertEqual(app.config["LOG_DOWN_INTERVAL"], 180)
        self.assertEqual(app.config["FETCH_HAPROXY_STATUS_INTERVAL"], 15)
        self.assertEqual(app.config["HEALTHY_BACKEND_UPTIME"], 32)
        self.assertIsNone(app.config["SERVICE_NAME"])
        self.assertTrue(app.config["RETURN_404_ON_ADMIN_DOWN"])
        self.assertEqual(app.config["FLAPPING_THRESHOLD"], 3)
        self.assertEqual(app.config["FLAPPING_WINDOW"], 300)

    def test_flask_config_reflects_env_overrides(self):
        """Flask app.config should reflect env var overrides via Settings."""
        with patch.dict(os.environ, {"LOG_LEVEL": "DEBUG", "LOG_DOWN_INTERVAL": "500"}):
            import haproxy_status

            app = haproxy_status.app.init_app("test_flask_env")
            self.assertEqual(app.config["LOG_LEVEL"], "DEBUG")
            self.assertEqual(app.config["LOG_DOWN_INTERVAL"], 500)

    def test_flask_config_init_overrides(self):
        """Config dict passed to init_app should override Settings values."""
        import haproxy_status

        app = haproxy_status.app.init_app(
            "test_flask_override", config={"LOG_LEVEL": "WARNING"}
        )
        self.assertEqual(app.config["LOG_LEVEL"], "WARNING")

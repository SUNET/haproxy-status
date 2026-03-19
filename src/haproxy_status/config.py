# -*- coding: utf-8 -*-
"""Pydantic-settings based configuration for haproxy-status."""

from typing import Optional

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    log_level: str = "INFO"
    backend_dir: str = "/backends"
    stats_url: str = "/var/run/haproxy-control/stats"
    log_down_interval: int = 180
    fetch_haproxy_status_interval: int = 15
    healthy_backend_uptime: Optional[int] = None
    status_output_filename: str = "/dev/shm/haproxy-status.txt"
    signal_directory: str = "/var/haproxy-status"
    service_name: Optional[str] = None
    return_404_on_admin_down: bool = True
    # Flapping detection: flag a server as FLAPPING if it transitions DOWN
    # more than FLAPPING_THRESHOLD times within FLAPPING_WINDOW seconds
    flapping_threshold: int = 3
    flapping_window: int = 300

    def model_post_init(self, __context) -> None:
        if self.healthy_backend_uptime is None:
            self.healthy_backend_uptime = self.fetch_haproxy_status_interval * 2 + 2

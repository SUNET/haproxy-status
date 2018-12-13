DEBUG = True
BACKEND_DIR = '/backends'
STATS_URL = '/var/run/haproxy-control/stats'
LOG_DOWN_INTERVAL = 60
FETCH_HAPROXY_STATUS_INTERVAL = 15
# HEALTHY_BACKEND_UPTIME needs to be 2x FETCH_HAPROXY_STATUS_INTERVAL
# to avoid flapping if a service really is restarting (also account for random fuzzing)
HEALTHY_BACKEND_UPTIME = FETCH_HAPROXY_STATUS_INTERVAL * 2 + 2

LOG_LEVEL = 'INFO'
BACKEND_DIR = '/backends'
STATS_URL = '/var/run/haproxy-control/stats'
LOG_DOWN_INTERVAL = 180
FETCH_HAPROXY_STATUS_INTERVAL = 15
# HEALTHY_BACKEND_UPTIME needs to be 2x FETCH_HAPROXY_STATUS_INTERVAL
# to avoid flapping if a service really is restarting (also account for random fuzzing)
HEALTHY_BACKEND_UPTIME = FETCH_HAPROXY_STATUS_INTERVAL * 2 + 2
STATUS_OUTPUT_FILENAME = '/dev/shm/haproxy-status.txt'
SIGNAL_DIRECTORY = '/var/haproxy-status'
SERVICE_NAME = None
RETURN_404_ON_ADMIN_DOWN = True

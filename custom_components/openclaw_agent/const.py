"""Constants for the OpenClaw Agent integration."""

DOMAIN = "openclaw_agent"

CONF_HOST = "host"
CONF_PORT = "port"
CONF_TOKEN = "token"
CONF_USE_SSL = "use_ssl"
CONF_VERIFY_SSL = "verify_ssl"
CONF_AGENT_NAME = "agent_name"

DEFAULT_PORT = 18789
DEFAULT_AGENT_NAME = "Jarvis"
DEFAULT_TIMEOUT = 30

ATTR_MESSAGE = "message"
ATTR_SESSION_ID = "session_id"
ATTR_MODEL = "model"
ATTR_RESPONSE = "response"

# Services
SERVICE_SEND_MESSAGE = "send_message"
SERVICE_CLEAR_HISTORY = "clear_history"
SERVICE_RESTART_HA = "restart_homeassistant"
SERVICE_EDIT_CONFIG = "edit_configuration"
SERVICE_RELOAD_INTEGRATION = "reload_integration"
SERVICE_RUN_COMMAND = "run_command"
SERVICE_BACKUP_CONFIG = "backup_configuration"
SERVICE_CHECK_CONFIG = "check_configuration"

# Events
EVENT_MESSAGE_RECEIVED = "openclaw_agent_message_received"
EVENT_TOOL_INVOKED = "openclaw_agent_tool_invoked"
EVENT_COMMAND_RESULT = "openclaw_agent_command_result"

# Sensor types
SENSOR_GATEWAY_STATUS = "gateway_status"
SENSOR_MODEL = "model"
SENSOR_UPTIME = "uptime"
SENSOR_LAST_MESSAGE = "last_message"
SENSOR_LAST_TOOL = "last_tool"

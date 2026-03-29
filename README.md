# 🤖 OpenClaw Agent — Home Assistant Integration (HACS)

**Full-control integration** that connects your Home Assistant instance to an [OpenClaw](https://github.com/openclaw/openclaw) gateway.

> **⚠️ Alpha — v0.1.0**
> Under active development. Breaking changes possible.

---

## ✨ Features

| Feature | Description |
|---|---|
| 🧠 **Conversation Agent** | Jarvis appears as an Assist provider — talk to your AI agent natively |
| 💬 **Chat Card** | Lovelace card with message history, typing indicator |
| ✏️ **Edit configuration.yaml** | Read, write, patch YAML files with automatic backups |
| 🔄 **Restart HA** | `openclaw_agent.restart_homeassistant` service |
| 🔁 **Reload Integrations** | `openclaw_agent.reload_integration` — reload any HA integration |
| 🖥️ **Run Commands** | `openclaw_agent.run_command` — execute shell commands on HA host |
| 💾 **Backup Config** | Automatic backup before any config change |
| ✅ **Check Config** | Validate configuration before applying |
| 📡 **Events** | `openclaw_agent_message_received`, `openclaw_agent_tool_invoked` |
| 📊 **Sensors** | Gateway status, model, uptime, last message |

---

## 📋 Requirements

- **Home Assistant** 2024.1.0+
- **OpenClaw** gateway reachable over the network
- Gateway `chatCompletions` endpoint enabled:
  ```json
  "gateway": {
    "http": {
      "endpoints": {
        "chatCompletions": {
          "enabled": true
        }
      }
    }
  }
  ```

---

## 🚀 Installation

### Via HACS (Recommended)

1. Open HACS → Integrations
2. Click ⋮ menu → **Custom repositories**
3. Add: `https://github.com/Liionboy/openclaw-ha-integration` — Category: **Integration**
4. Search for **OpenClaw Agent** → Install
5. Restart Home Assistant
6. Go to **Settings → Devices & Services → Add Integration → OpenClaw Agent**

### Manual

1. Copy `custom_components/openclaw_agent/` into your HA config directory:
   ```
   config/custom_components/openclaw_agent/
   ```
2. Restart Home Assistant
3. Add the integration from Settings → Devices & Services

---

## ⚙️ Configuration

### Config Flow (UI)

| Field | Description | Default |
|---|---|---|
| Gateway Host | IP or hostname of OpenClaw gateway | — |
| Gateway Port | Gateway port | `18789` |
| Gateway Token | Auth token from `openclaw.json` | — |
| Use SSL | Connect via HTTPS | `false` |
| Verify SSL | Validate SSL certificate | `true` |
| Agent Name | Display name | `Jarvis` |

Get your token:
```bash
openclaw config get gateway.auth.token
```

---

## 🔧 Services

### `openclaw_agent.send_message`
Send a message to OpenClaw and receive a response.

```yaml
service: openclaw_agent.send_message
data:
  message: "What's the weather like?"
  session_id: "living-room"
  model: "openrouter/xiaomi/mimo-v2-pro"  # optional
```

### `openclaw_agent.edit_configuration`
Edit any YAML file in the config directory. Automatic backup before write.

**Patch a single section:**
```yaml
service: openclaw_agent.edit_configuration
data:
  filename: "configuration.yaml"
  section: "automation"
  content: |
    - alias: "New Automation"
      trigger:
        platform: state
        entity_id: light.bec_living
      action:
        service: light.turn_off
```

**Replace entire file:**
```yaml
service: openclaw_agent.edit_configuration
data:
  filename: "automations.yaml"
  content: |
    - alias: Test
      trigger: []
      action: []
```

### `openclaw_agent.restart_homeassistant`
Restart HA. No parameters needed.
```yaml
service: openclaw_agent.restart_homeassistant
```

### `openclaw_agent.reload_integration`
Reload a specific integration without restarting HA.
```yaml
service: openclaw_agent.reload_integration
data:
  integration: "mqtt"
```

### `openclaw_agent.run_command`
Execute a shell command on the HA host.
```yaml
service: openclaw_agent.run_command
data:
  command: "ls -la /config"
  timeout: 10
```

### `openclaw_agent.backup_configuration`
Backup a specific file or the entire config.
```yaml
# Single file
service: openclaw_agent.backup_configuration
data:
  filename: "configuration.yaml"

# Full backup
service: openclaw_agent.backup_configuration
```

### `openclaw_agent.check_configuration`
Validate HA configuration.
```yaml
service: openclaw_agent.check_configuration
```

---

## 📡 Events

### `openclaw_agent_message_received`
Fired when a message is received from OpenClaw.

```yaml
data:
  user_message: "Turn off the lights"
  response: "Done! Lights are off."
  conversation_id: "ha-123"
```

### `openclaw_agent_command_result`
Fired when a command finishes executing.

```yaml
data:
  command: "df -h"
  return_code: 0
  success: true
```

---

## 📊 Sensors

| Sensor | Description |
|---|---|
| `sensor.openclaw_status` | Gateway connection (online/offline) |
| `sensor.openclaw_model` | Current AI model + provider |
| `sensor.openclaw_uptime` | Gateway uptime in minutes |
| `sensor.openclaw_last_message` | Last processed message |

---

## 🔒 Security

- **Config backup**: Automatic before every write
- **Path traversal protection**: Cannot edit files outside config dir
- **Command timeout**: Default 30s, configurable up to 300s
- **SSL support**: Full HTTPS with optional certificate verification

---

## 🛠️ Development

```bash
# Clone
git clone https://github.com/Liionboy/openclaw-ha-integration.git
cd openclaw-ha-integration

# Copy to HA for testing
cp -r custom_components/openclaw_agent /path/to/ha/config/custom_components/

# Restart HA and add integration
```

---

## 📄 License

MIT

---

## 🙏 Credits

Built by [Liionboy](https://github.com/Liionboy) — powered by [OpenClaw](https://github.com/openclaw/openclaw).

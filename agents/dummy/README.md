# fence_dummy - Testing and Simulation Fence Agent

## Overview

`fence_dummy` is a fence agent for development, testing, and simulation. It supports three operating modes:

1. **file** - Status stored in a file (default)
2. **fail** - Simulated failure scenarios
3. **recorder** - Request/response coordination with external systems

---

---

## File Mode (Default)

The **file mode** (default) stores power status in a simple text file, making it useful for basic testing without complex infrastructure.

### How It Works

- Reads/writes node power state from/to a status file
- `on` action: Writes "on" to the file
- `off` action: Writes "off" to the file  
- `status` action: Reads current state from file (returns "off" if file missing)
- File persists across invocations for state tracking

### Use Cases

- **Basic fence agent testing** in development
- **Simple state tracking** without external dependencies
- **Unit testing** fence workflows
- **Learning fence agent behavior** in isolation

### Configuration

```bash
# Direct CLI usage
fence_dummy --plug node1 --action off --status-file /tmp/node1.status
fence_dummy --plug node1 --action status --status-file /tmp/node1.status

# Create STONITH resource
pcs stonith create file-fence fence_dummy \
    plug=compute-node-1 \
    status_file=/tmp/compute-node-1.status
```

### Options (File Mode)

| Option | Default | Description |
| ------ | ------- | ----------- |
| `--type` | `file` | Mode (default, can be omitted) |
| `--plug` | (optional) | Node identifier (not used for file operations) |
| `--status-file` | `/tmp/fence_dummy.status` | File storing power state |

### Example

```bash
# Turn off node
$ fence_dummy --plug node1 --action off --status-file /tmp/node1.status
$ cat /tmp/node1.status
off

# Check status
$ fence_dummy --plug node1 --action status --status-file /tmp/node1.status
Status: OFF

# Turn on node
$ fence_dummy --plug node1 --action on --status-file /tmp/node1.status
$ cat /tmp/node1.status
on
```

---

## Fail Mode

The **fail mode** (`--type=fail`) simulates fence device failures and unexpected behaviors for testing error handling.

### How It Works

- Returns power state **opposite** of what's expected
- `status` returns random on/off state for specified plug
- `list` returns a predefined list of fake outlets
- Useful for testing Pacemaker error recovery and retry logic

### Use Cases

- **Testing error handling** in cluster configurations
- **Validating retry logic** in Pacemaker
- **Simulating unreliable fence devices** during development
- **Chaos engineering** for HA clusters

### Configuration

```bash
# Direct CLI usage
fence_dummy --plug node1 --type=fail --action status

# Create STONITH resource (NOT recommended for production!)
pcs stonith create fail-fence fence_dummy \
    type=fail \
    plug=compute-node-1
```

### Options (Fail Mode)

| Option | Default | Description |
| ------ | ------- | ----------- |
| `--type` | `file` | Set to `fail` for failure simulation |
| `--plug` | (required) | Target outlet/node |

### Behavior

- **`list` action**: Returns fake outlet list `["1", "2"]`
- **`status` action**: Returns random state (inconsistent results)
- **`on`/`off` actions**: Succeed but state queries will be inconsistent
- **`monitor` action**: Returns success (agent is "working")

### Example

```bash
$ fence_dummy --plug 1 --type=fail --action list
1,2

$ fence_dummy --plug 1 --type=fail --action status
Status: ON

$ fence_dummy --plug 1 --type=fail --action status
Status: OFF  # Inconsistent!
```

---

## Recorder Mode

The **recorder mode** (`--type=recorder`) implements the fence_recorder request/response pattern for coordinating fencing with external systems via files.

### How It Works

```text
Pacemaker → fence_dummy (recorder mode)
              ↓
         Write request file
              ↓
         Wait for response
              ↓
         External system writes response
              ↓
         Read response & exit
```

### Use Cases

- **Testing fence_recorder protocol** without external system dependencies
- **Simulating external fence coordination** in development
- **CI/CD testing** of fence request/response workflows
- **Validating external fence responders** before production

### Configuration

```bash
# Create directories
sudo mkdir -p /var/run/fence_dummy/{requests,responses}
sudo mkdir -p /var/log/cluster

# Create STONITH resource
pcs stonith create test-fence fence_dummy \
    type=recorder \
    plug=compute-node-1 \
    request_path=/var/run/fence_dummy/requests \
    response_path=/var/run/fence_dummy/responses \
    log_path=/var/log/cluster \
    recorder_timeout=30
```

### Options (Recorder Mode)

| Option | Default | Description |
| ------ | ------- | ----------- |
| `--type` | `file` | Set to `recorder` for request/response mode |
| `--plug` | (required) | Target node to fence |
| `--request-path` | `/var/run/fence_dummy/requests` | Directory for fence requests |
| `--response-path` | `/var/run/fence_dummy/responses` | Directory for fence responses |
| `--recorder-timeout` | `60` | Seconds to wait for response |
| `--recorder-poll-interval` | `0.5` | Seconds between response checks |
| `--log-path` | `/var/log/cluster` | Directory for fence event logs |

### Logging (Recorder Mode)

Recorder mode enables structured logging to track fence operations:

- **Log file**: `<log-path>/fence-events.log` (also to stderr)
- **Format**: `[YYYY-MM-DD HH:MM:SS] [LEVEL] message`
- **Events logged**:
  - Fence action requested
  - Fence action completed/failed
  - Request/response file operations
  - Errors and timeouts

Example log entries:

```text
[2026-01-14 13:45:10] [INFO] Fence event: action=off, target=compute-node-1, status=requested, details=Fence action off requested
[2026-01-14 13:45:15] [INFO] Fence response received: success=True, message=Fence operation completed successfully, timestamp=2026-01-14T13:45:15-06:00
[2026-01-14 13:45:15] [INFO] Fence event: action=off, target=compute-node-1, status=completed, details=Fence action off completed successfully: Fence operation completed successfully
```

> **Note**: In recorder mode, the agent uses a synchronous pattern to wait for the external response.
>
> - `off`: Writes a request and waits for a success response.
> - `reboot`: Executed as `off` then `on`. This generates an `off` request (wait for success) followed by an `on` action (no-op).
> - `on`, `status`, `monitor`: These are no-ops that always return success/on to satisfy Pacemaker requirements, but do not generate request files.

### Request File Format

**File**: `<request-path>/<node-name>-<uuid>.json`

```json
{
  "request_id": "550e8400-e29b-41d4-a716-446655440000",
  "timestamp": "2026-01-06T14:30:00-06:00",
  "action": "off",
  "target_node": "compute-node-1",
  "recorder_node": "control-node"
}
```

### Response File Format

**File**: `<response-path>/<node-name>-<uuid>.json`

```json
{
  "request_id": "550e8400-e29b-41d4-a716-446655440000",
  "timestamp": "2026-01-06T14:30:05-06:00",
  "success": true,
  "message": "Fence operation completed successfully",
  "action_performed": "off",
  "target_node": "compute-node-1",
  "recorder_node": "responder-system"
}
```

### Example: Simulating an External Responder

```bash
#!/bin/bash
# Simple fence responder for testing

REQUEST_DIR="/var/run/fence_dummy/requests"
RESPONSE_DIR="/var/run/fence_dummy/responses"

while true; do
    for request in "$REQUEST_DIR"/*.json; do
        [ -e "$request" ] || continue

        # Extract request_id and node name from request file
        request_id=$(jq -r '.request_id' "$request")
        target_node=$(jq -r '.target_node' "$request")

        # Write response
        response_file="$RESPONSE_DIR/$(basename "$request")"
        timestamp=$(date +"%Y-%m-%dT%H:%M:%S%z" | sed 's/\([0-9][0-9]\)$/:\1/')
        cat > "$response_file" <<EOF
{
  "request_id": "$request_id",
  "timestamp": "$timestamp",
  "success": true,
  "message": "Simulated fence of $target_node",
  "action_performed": "off",
  "target_node": "$target_node",
  "recorder_node": "$(hostname)"
}
EOF

        echo "Responded to fence request for $target_node"
        rm "$request"
    done
    sleep 1
done
```

---

## Common Options (All Modes)

### Random Sleep

Simulate slow fence devices by adding random delays:

| Option | Default | Description |
| ------ | ------- | ----------- |
| `--random_sleep_range` | (disabled) | Maximum sleep time in seconds (random 1-N) |

```bash
# Sleep 1-30 seconds before taking action (any mode)
fence_dummy --plug node1 --action off --random_sleep_range=30

# Combine with recorder mode
fence_dummy --type=recorder --plug node1 --action off \
    --random_sleep_range=10 \
    --request-path=/var/run/fence_dummy/requests \
    --response-path=/var/run/fence_dummy/responses
```

### Standard Fence Actions

All modes support standard fence agent actions:

- **`on`**: Turn on the node/outlet
- **`off`**: Turn off the node/outlet (primary fence action)
- **`reboot`**: Reboot the node (implemented as off + on)
- **`status`**: Query current power state
- **`monitor`**: Check if fence agent is functioning (always succeeds)
- **`list`**: List available outlets (fail mode only)
- **`metadata`**: Output XML metadata for Pacemaker

---

## Comparison of Modes

| Feature | File Mode | Fail Mode | Recorder Mode |
| ------- | --------- | --------- | ------------- |
| **Default** | ✓ | | |
| **State Persistence** | File-based | None | External system |
| **External Dependencies** | None | None | Response writer |
| **Reliable Results** | ✓ | ✗ (intentionally) | ✓ (if responder works) |
| **Async Operation** | No | No | Yes (waits for response) |
| **Logging** | Minimal | Minimal | Structured logs |
| **Use Case** | Basic testing | Error simulation | External coordination |
| **Production Use** | Testing only | Never | Testing only |

---

## Installation

```bash
# Build from source
./autogen.sh
./configure
make
sudo make install

# Verify installation
fence_dummy -o metadata
```

## See Also

- `fence_recorder` - Production fence agent for NNF storage coordination
- [Pacemaker documentation](https://clusterlabs.org/pacemaker/)
- Fence agent development: `/usr/share/doc/fence-agents/`

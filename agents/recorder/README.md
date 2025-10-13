# fence_recorder - Request/Response Fence Agent

## Overview

`fence_recorder` is a Pacemaker fence agent that coordinates fencing with external systems using a **request/response file pattern**. Instead of directly fencing nodes, it writes fence requests to a directory and waits for an external service to process them and write a response.

This design enables integration with external storage systems, cloud providers, or custom fencing logic that needs to perform cleanup operations before fencing completes.

## How It Works

```text
┌─────────────────────┐
│  Pacemaker/Corosync │
│  (Cluster Manager)  │
└──────────┬──────────┘
           │
           │ Calls fence_recorder
           ▼
┌──────────────────────┐      ┌──────────────────────────────┐
│   fence_recorder     │─────▶│   Request File               │
│   (This Agent)       │      │   requests/<node>-<uuid>.json│
└──────────────────────┘      └──────────────────────────────┘
           │                                 │
           │ Waits for response              │ External reads request
           │                                 ▼
           │                  ┌──────────────────────────────┐
           │                  │   External Responder         │
           │                  │   (Your Implementation)      │
           │                  └──────────────────────────────┘
           │                                 │
           ▼                                 │ Writes response
┌──────────────────────────────┐             │
│   Response File              │◀────────────┘
│   responses/<node>-<uuid>.json│
└──────────────────────────────┘
           │
           │ Exit code 0 (success) or 1 (failure)
           ▼
┌──────────────────────┐
│      Pacemaker       │
└──────────────────────┘
```

## Features

- **Request/Response Pattern**: File-based coordination with external systems
- **Atomic File Writing**: Uses rename pattern to ensure file integrity
- **Configurable Directories**: Custom request/response/log paths via command-line options
- **Timeout Handling**: Configurable timeout for external responses
- **Structured Logging**: Multiple log formats for operations and auditing
- **Pacemaker Integration**: Standard fence agent interface

## Installation

```bash
# Copy agent to system
sudo cp fence_recorder /usr/sbin/fence_recorder
sudo chmod 755 /usr/sbin/fence_recorder

# Create directories
sudo mkdir -p /var/run/fence_recorder/{requests,responses}
sudo mkdir -p /var/log/cluster
sudo chmod 755 /var/run/fence_recorder/{requests,responses}
sudo chmod 755 /var/log/cluster
```

## Pacemaker Configuration

```bash
# Create STONITH resource for each compute node
pcs stonith create compute-node-2-fence fence_recorder \
    plug=compute-node-2 \
    request_dir=/var/run/fence_recorder/requests \
    response_dir=/var/run/fence_recorder/responses \
    op monitor interval=60s timeout=10s

# Enable fencing
pcs property set stonith-enabled=true
```

**Note**: Use underscores (`request_dir`) in Pacemaker resource configuration, and hyphens (`--request-dir`) on the command line.

## Command Line Options

| Option | Default | Description |
|--------|---------|-------------|
| `--plug`, `-n` | (required) | Target node to fence |
| `--action`, `-o` | `reboot` | Fence action: `off`, `on`, `reboot`, `status`, `monitor` |
| `--request-dir` | `/var/run/fence_recorder/requests` | Directory for fence request files |
| `--response-dir` | `/var/run/fence_recorder/responses` | Directory for fence response files |
| `--log-dir` | `/var/log/cluster` | Directory for log files |

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `FENCE_TIMEOUT` | `60` | Seconds to wait for external response |
| `LOG_DIR` | `/var/log/cluster` | Log directory (overridden by `--log-dir`) |
| `POLL_INTERVAL` | `0.5` | Seconds between response file checks |
| `CLEANUP_MAX_AGE` | `300` | Seconds before old request files are cleaned up |

## Request/Response Protocol

### Atomic File Writing

Both request and response files use atomic rename to ensure consumers only see complete files:

1. Write to temporary file: `.<filename>.tmp`
2. Close the file
3. Rename to final name: `<filename>`

Consumers should ignore files starting with `.` (hidden/temporary files).

### Request File Format

**Location**: `<request-dir>/<node>-<uuid>.json`

```json
{
  "request_id": "550e8400-e29b-41d4-a716-446655440000",
  "timestamp": "2025-01-10T14:30:00Z",
  "action": "reboot",
  "target_node": "compute-node-3",
  "recorder_node": "mgmt-node-1"
}
```

### Response File Format

**Location**: `<response-dir>/<node>-<uuid>.json`

```json
{
  "request_id": "550e8400-e29b-41d4-a716-446655440000",
  "success": true,
  "action_performed": "reboot",
  "target_node": "compute-node-3",
  "message": "Successfully fenced node",
  "timestamp": "2025-01-10T14:30:15Z"
}
```

## External Responder

An example external responder is provided: `external_fence_watcher.py`

### Running Manually

```bash
python3 external_fence_watcher.py
```

### Running as a Service

```bash
sudo cp external_fence_watcher.py /usr/local/bin/
sudo cp fence-watcher.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now fence-watcher.service
```

### Custom Implementation

To implement your own external responder:

1. Watch for new `.json` files in the request directory (ignore files starting with `.`)
2. Parse the request JSON
3. Perform your fence action (IPMI, cloud API, storage detach, etc.)
4. Write response using atomic rename pattern
5. Optionally delete the request file

## Log Files

Log files are written to the configured log directory (default: `/var/log/cluster/`):

| File | Format | Description |
|------|--------|-------------|
| `fence-events.log` | Timestamped text | Main operational log |
| `fence-events-readable.log` | Key=value | Grep-friendly format |
| `fence-events-detailed.jsonl` | JSON Lines | Machine-parseable format |

## Testing

```bash
# Test metadata output
fence_recorder --action metadata

# Test monitor action (checks directories are accessible)
fence_recorder --action monitor --port compute-node-2

# Test with external_fence_watcher running
fence_recorder --action reboot --port compute-node-3
```

## Troubleshooting

### Timeout Errors

```bash
# Increase fence timeout
export FENCE_TIMEOUT=120
fence_recorder --action reboot --port compute-node-3

# Check if external responder is running
systemctl status fence-watcher.service

# Check for pending requests
ls -la /var/run/fence_recorder/requests/
```

### Permission Errors

```bash
# Check directory permissions
ls -ld /var/run/fence_recorder/{requests,responses}
ls -ld /var/log/cluster

# Fix permissions
sudo chmod 755 /var/run/fence_recorder/{requests,responses}
sudo chmod 755 /var/log/cluster
```

### Response Not Found

```bash
# Check if response was written
ls -la /var/run/fence_recorder/responses/

# Check external responder logs
journalctl -u fence-watcher.service -f

# Check fence_recorder logs
tail -f /var/log/cluster/fence-events.log
```

## References

- [Request/Response Pattern Documentation](REQUEST-RESPONSE-PATTERN.md)
- [ClusterLabs fence-agents](https://github.com/ClusterLabs/fence-agents)
- [Fence Agent Development Guide](../../doc/fa-dev-guide.md)

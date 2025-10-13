# Fence Request/Response Pattern

## Overview

The `fence_recorder` uses a **request/response pattern** to decouple fence event logging from actual fencing operations. This allows you to implement custom fencing logic in a separate component while maintaining full integration with Pacemaker.

## Architecture

```text
┌─────────────────┐         ┌──────────────────────┐          ┌──────────────────────────┐
│   Pacemaker     │────────▶│  fence_recorder      │─────────▶│   Request Files          │
│   (Initiates    │◀────────│  (Records & Waits)   │          │   /var/run/fence_        │
│    Fencing)     │  exit   │                      │          │   recorder/requests/     │
└─────────────────┘  code   └──────────────────────┘          └──────────────────────────┘
                      ▲                   ▲                              │
                      │                   │ reads                        │ watches
                      │                   │ response                     ▼
                      │                   │                    ┌──────────────────────────┐
                      │                   │                    │ External Responder       │
                      │                   │                    │ (Your Implementation)    │
                      │                   │                    │ e.g. fence_watcher       │
                      │                   │                    └──────────────────────────┘
                      │                   │                              │
                      │                   │                              │ writes
                      │                   │                              ▼
                      │         ┌──────────────────────┐       ┌──────────────────────────┐
                      └─────────│   Response Files     │◀──────│  Fence Operations        │
                       0=success│   /var/run/fence_    │       │  (IPMI, cloud API,       │
                       1=failure│   recorder/responses/│       │   storage detach, etc.)  │
                                └──────────────────────┘       └──────────────────────────┘   
```

## How It Works

### 1. Pacemaker Initiates Fence

When Pacemaker decides a node needs fencing:

```bash
pcs stonith fence compute-node-3
```

### 2. fence_recorder Writes Request (Atomic)

The fence agent creates a request file using atomic rename to ensure consumers only see complete files:

1. Writes to temporary file: `.<node-name>-<uuid>.json.tmp`
2. Closes the file
3. Renames to final name: `<node-name>-<uuid>.json`

The rename operation triggers a file creation event and guarantees the file is complete.

**File**: `/var/run/fence_recorder/requests/<node-name>-<uuid>.json`

**Example**: `/var/run/fence_recorder/requests/compute-node-3-550e8400-e29b-41d4-a716-446655440000.json`

```json
{
  "request_id": "550e8400-e29b-41d4-a716-446655440000",
  "timestamp": "2025-10-20T14:30:00Z",
  "action": "reboot",
  "target_node": "compute-node-3",
  "recorder_node": "mgmt-node-1"
}
```

### 3. External Responder Processes Request

The external responder (e.g., `external_fence_watcher.py` or your custom implementation):

1. Watches the request directory for new files (ignores files starting with `.`)
2. Reads the request file and parses the target node
3. Performs the fence action
4. Writes a response file using the same atomic rename pattern

**File**: `/var/run/fence_recorder/responses/<node-name>-<uuid>.json`

**Example**: `/var/run/fence_recorder/responses/compute-node-3-550e8400-e29b-41d4-a716-446655440000.json`

```json
{
  "request_id": "550e8400-e29b-41d4-a716-446655440000",
  "success": true,
  "action_performed": "reboot",
  "target_node": "compute-node-3",
  "message": "Successfully fenced node by deleting 1 shared storage groups",
  "timestamp": "2025-10-20T14:30:15Z"
}
```

### 4. fence_recorder Returns to Pacemaker

The fence agent:

1. Reads the response file
2. Logs the final result
3. Returns success (exit 0) or failure (exit 1) to Pacemaker

## Implementation Guide

### Step 1: Update fence_recorder

The updated version is already configured with request/response support.

### Step 2: Deploy an External Responder

The external responder processes fence requests and performs the actual fencing.
An example implementation (`external_fence_watcher.py`) is provided.

The responder should:

1. Watch for fence request files in `/var/run/fence_recorder/requests/`
2. Process fence requests (e.g., call IPMI, cloud API, or custom fencing logic)
3. Write response files to `/var/run/fence_recorder/responses/`

For production use, replace `external_fence_watcher.py` with your actual fencing
mechanism (IPMI, cloud provider API, hardware management interface, etc.).

### Step 3: Configure Directory Access

Ensure the external responder has access to the fence request/response directories:

```bash
# Verify directories exist and are accessible
ls -la /var/run/fence_recorder/
ls -la /var/run/fence_recorder/requests/
ls -la /var/run/fence_recorder/responses/

# Check permissions (should be writable by external services)
stat /var/run/fence_recorder/requests/
stat /var/run/fence_recorder/responses/
```

### Step 4: Test the Integration

```bash
# Test fence operation via Pacemaker
pcs stonith fence compute-node-2

# Check request was created and processed
ls -l /var/run/fence_recorder/requests/
ls -l /var/run/fence_recorder/responses/

# Check fence logs
tail /var/log/cluster/fence-events-readable.log
```

## Configuration

The fence agent uses command-line options for directory paths and environment variables for runtime settings:

| Setting | Source | Default | Description |
|---------|--------|---------|-------------|
| `--request-dir` | Command line | `/var/run/fence_recorder/requests` | Directory for fence requests |
| `--response-dir` | Command line | `/var/run/fence_recorder/responses` | Directory for fence responses |
| `--log-dir` | Command line | `/var/log/cluster` | Directory for fence event logs |
| `FENCE_TIMEOUT` | Environment | `60` | Timeout in seconds to wait for external response |

### Directory Configuration

The request/response directories must be accessible by both the fence agent and the external responder:

```bash
# Create directories with appropriate permissions
sudo mkdir -p /var/run/fence_recorder/{requests,responses}
sudo chmod 755 /var/run/fence_recorder/{requests,responses}
```

**Important**: These paths must match between the fence agent (`--request-dir`, `--response-dir`) and the external responder (e.g., `external_fence_watcher.py` environment variables).

### Pacemaker Configuration

Configure timeout and log directory in the stonith resource:

```bash
# Using command-line options
pcs stonith create compute-node-2-fence fence_recorder \
    plug=compute-node-2 \
    request-dir="/var/run/fence_recorder/requests" \
    response-dir="/var/run/fence_recorder/responses" \
    log-dir="/var/log/cluster" \
    op monitor interval=60s
```

## Troubleshooting

### Fence Operation Times Out

```bash
# Check if external responder is running
ps aux | grep fence_watcher
systemctl status fence-watcher.service

# Check fence_recorder logs
tail -f /var/log/cluster/fence-events.log

# Check for pending requests
ls -la /var/run/fence_recorder/requests/
```

### Response Not Being Read

```bash
# Check response directory permissions
ls -ld /var/run/fence_recorder/responses/

# Check fence_recorder logs
tail -f /var/log/cluster/fence-events.log

# Check external responder logs
journalctl -u fence-watcher.service -f
```

### Increase Timeout

If external processing takes longer than 60 seconds:

```bash
pcs resource update compute-node-2-fence-recorder \
    meta env="FENCE_TIMEOUT=120"
```

## Benefits of This Pattern

1. **Separation of Concerns**: Fencing coordination separated from actual fence operations
2. **External System Integration**: Allows integration with storage systems, cloud providers, or custom fencing logic
3. **Debugging**: Request/response files provide clear audit trail for all operations
4. **Storage Safety**: Ensures proper resource detachment before node fencing
5. **Testing**: Can simulate operations without affecting actual infrastructure
6. **Flexibility**: Works with any external responder that follows the file protocol

#!@PYTHON@ -tt

#
# Fence agent that coordinates fencing with external systems via a
# request/response file pattern. Writes fence requests to a directory,
# waits for an external coordinator to write a response, and reports
# the result back to Pacemaker.
#

import sys
import os
import json
import logging
import socket
import time
import uuid
from datetime import datetime, timezone
import atexit
from collections import namedtuple

sys.path.append("@FENCEAGENTSLIBDIR@")
from fencing import *
from fencing import fail_usage, run_delay, all_opt, check_input, process_input, show_docs, atexit_handler

# Default directories for request/response files
DEFAULT_REQUEST_DIR = "/var/run/fence_recorder/requests"
DEFAULT_RESPONSE_DIR = "/var/run/fence_recorder/responses"

# Configuration defaults
LOG_DIR = os.environ.get("LOG_DIR", "/var/log/cluster")

# Default values - these will be validated and possibly overridden in main()
DEFAULT_FENCE_TIMEOUT = 60
DEFAULT_POLL_INTERVAL = 0.5
DEFAULT_CLEANUP_MAX_AGE = 300  # seconds

# Note: Directories are created in main() after options are parsed
# Note: Logging is initialized in setup_logging() after options are parsed


def setup_logging(log_dir):
    """Initialize logging with the specified log directory"""
    os.makedirs(log_dir, exist_ok=True)
    fence_log = os.path.join(log_dir, "fence-events.log")
    
    # Configure root logger
    # Clear any existing handlers for Python 3.6 compatibility (force= added in 3.8)
    root_logger = logging.getLogger()
    if root_logger.hasHandlers():
        root_logger.handlers.clear()
    
    logging.basicConfig(
        level=logging.INFO,
        format='[%(asctime)s] [%(levelname)s] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
        handlers=[
            logging.FileHandler(fence_log),
            logging.StreamHandler(sys.stderr)
        ]
    )
    
    return log_dir, fence_log


Config = namedtuple("Config", ["fence_timeout", "poll_interval", "cleanup_max_age"])

def validate_environment_config(default_timeout: int = DEFAULT_FENCE_TIMEOUT,
                                default_poll: float = DEFAULT_POLL_INTERVAL,
                                default_cleanup: int = DEFAULT_CLEANUP_MAX_AGE) -> Config:
    """Validate and parse environment variable configuration.
    Must be called after setup_logging() so warnings go to log files.
    Returns a Config namedtuple with runtime values.
    """
    # Fence timeout
    fence_timeout = default_timeout
    fence_timeout_env = os.environ.get("FENCE_TIMEOUT")
    if fence_timeout_env:
        try:
            fence_timeout = int(fence_timeout_env)
            logging.info(f"Using FENCE_TIMEOUT={fence_timeout} seconds from environment")
        except ValueError:
            logging.warning(f"Invalid FENCE_TIMEOUT value '{fence_timeout_env}', using default {fence_timeout} seconds")

    # Poll interval
    poll_interval = default_poll
    poll_interval_env = os.environ.get("POLL_INTERVAL")
    if poll_interval_env:
        try:
            poll_interval = float(poll_interval_env)
            logging.info(f"Using POLL_INTERVAL={poll_interval} seconds from environment")
        except ValueError:
            logging.warning(f"Invalid POLL_INTERVAL value '{poll_interval_env}', using default {poll_interval} seconds")

    # Cleanup age
    cleanup_max_age = default_cleanup
    cleanup_env = os.environ.get("CLEANUP_MAX_AGE")
    if cleanup_env:
        try:
            cleanup_max_age = int(cleanup_env)
            logging.info(f"Using CLEANUP_MAX_AGE={cleanup_max_age} seconds from environment")
        except ValueError:
            logging.warning(f"Invalid CLEANUP_MAX_AGE value '{cleanup_env}', using default {cleanup_max_age} seconds")

    return Config(fence_timeout, poll_interval, cleanup_max_age)


def sanitize_node_name(node_name):
    """
    Validate and sanitize node name to prevent path traversal attacks
    
    Args:
        node_name: The node name to sanitize
        
    Returns:
        Sanitized node name string, or None if invalid
    """
    if '/' in node_name or '\\' in node_name or '..' in node_name:
        logging.error(f"Invalid target node name (path traversal attempt): {node_name}")
        return None
    
    safe_node_name = os.path.basename(node_name)
    if not safe_node_name or safe_node_name in ('.', '..'):
        logging.error(f"Invalid target node name: {node_name}")
        return None
    
    return safe_node_name


def record_fence_event(action, target_node, status, details="", log_dir=None):
    """Record fencing event to structured log files"""
    
    if log_dir is None:
        log_dir = LOG_DIR
    
    # Capture once to avoid micro-drift between local and UTC timestamps
    now_utc = datetime.now(timezone.utc)
    now_local = now_utc.astimezone()
    timestamp = now_local.strftime('%Y-%m-%d %H:%M:%S')
    iso_timestamp = now_utc.strftime('%Y-%m-%dT%H:%M:%SZ')
    recorder_node = socket.gethostname()
    
    # JSON Lines format for detailed logging
    log_entry = {
        "timestamp": iso_timestamp,
        "action": action,
        "target_node": target_node,
        "status": status,
        "details": details,
        "recorder_node": recorder_node
    }
    
    # Append to JSON Lines file
    fence_events_json = os.path.join(log_dir, "fence-events-detailed.jsonl")
    try:
        with open(fence_events_json, 'a') as f:
            f.write(json.dumps(log_entry) + '\n')
    except Exception as e:
        logging.error(f"Failed to write JSON log: {e}")
    
    # Human-readable log
    readable_log = os.path.join(log_dir, "fence-events-readable.log")
    readable_entry = f"[{timestamp}] ACTION={action} TARGET={target_node} STATUS={status} DETAILS={details}"
    try:
        with open(readable_log, 'a') as f:
            f.write(readable_entry + '\n')
    except Exception as e:
        logging.error(f"Failed to write readable log: {e}")
    
    logging.info(f"Recorded fence event: action={action}, target={target_node}, status={status}")


def write_fence_request(action, target_node, request_dir=None):
    """
    Write a fence request file for external fencing component to process.
    
    Uses atomic rename pattern: write to .tmp file, then rename to final name.
    This ensures consumers only see complete files.
    
    Returns the request_id (UUID) for tracking
    """
    if request_dir is None:
        request_dir = DEFAULT_REQUEST_DIR
    
    # Sanitize target_node to prevent path traversal
    safe_target_node = sanitize_node_name(target_node)
    if not safe_target_node:
        return None
    
    request_id = str(uuid.uuid4())
    filename = f"{safe_target_node}-{request_id}.json"
    temp_file = os.path.join(request_dir, f".{filename}.tmp")
    final_file = os.path.join(request_dir, filename)
    
    request_data = {
        "request_id": request_id,
        "timestamp": datetime.now().astimezone().isoformat(),
        "action": action,
        "target_node": target_node,
        "recorder_node": socket.gethostname()
    }
    
    try:
        # Write to temp file first
        with open(temp_file, 'w') as f:
            json.dump(request_data, f, indent=2)
        # Atomic rename signals file is complete
        os.rename(temp_file, final_file)
        logging.info(f"Wrote fence request: {final_file}")
        return request_id
    except Exception as e:
        logging.error(f"Failed to write fence request: {e}")
        # Clean up temp file if it exists
        try:
            os.remove(temp_file)
        except OSError:
            pass
        return None


def wait_for_fence_response(request_id, target_node, timeout=60, response_dir=None, poll_interval=None):
    """
    Wait for external fencing component to write response file.
    
    Only processes files that don't start with '.' (atomic rename pattern).
    Files starting with '.' are incomplete and still being written.
    
    Args:
        request_id: UUID of the request
        target_node: Name of the node being fenced (for filename construction)
        timeout: Maximum seconds to wait for response
        response_dir: Directory to look for response files (defaults to DEFAULT_RESPONSE_DIR)
        poll_interval: Seconds between checks (defaults to POLL_INTERVAL)
    
    Returns: (success: bool, message: str, action: str)
    """
    if response_dir is None:
        response_dir = DEFAULT_RESPONSE_DIR
    if poll_interval is None:
        poll_interval = DEFAULT_POLL_INTERVAL
    
    # Sanitize target_node to prevent path traversal
    safe_target_node = sanitize_node_name(target_node)
    if not safe_target_node:
        return False, "Invalid target node name", "error"
    
    # Only look for final filename (not .tmp files)
    response_file = os.path.join(response_dir, f"{safe_target_node}-{request_id}.json")
    start_time = time.time()
    
    logging.info(f"Waiting for fence response: {response_file} (timeout={timeout}s)")
    
    while time.time() - start_time < timeout:
        try:
            if os.path.exists(response_file):
                # Check file size before reading (guard against malicious large files)
                file_size = os.path.getsize(response_file)
                if file_size > 1024 * 1024:  # 1MB limit
                    logging.error(f"Response file too large: {file_size} bytes")
                    return False, "Response file exceeds size limit", "error"
                
                with open(response_file, 'r') as f:
                    response_data = json.load(f)
                
                # Do NOT delete response file - external software needs it to track fenced nodes
                
                success = response_data.get("success", False)
                message = response_data.get("message", "Fence operation completed")
                actual_action = response_data.get("action_performed", "unknown")
                
                logging.info(f"Fence response received: success={success}, action={actual_action}, message={message}")
                logging.info(f"Response file preserved at: {response_file}")
                
                return success, message, actual_action
                
        except FileNotFoundError:
            # File was deleted between existence check and read - continue waiting
            pass
        except json.JSONDecodeError as e:
            logging.error(f"Failed to parse fence response JSON: {e}")
            return False, f"Failed to parse response: {e}", "error"
        except Exception as e:
            logging.error(f"Failed to read fence response: {e}")
            return False, f"Failed to read response: {e}", "error"
        
        time.sleep(poll_interval)
    
    # Timeout
    logging.error(f"Fence response timeout after {timeout}s")
    return False, f"Fence operation timed out after {timeout}s", "timeout"


def cleanup_old_requests(max_age_seconds=None, request_dir=None):
    """Clean up request files older than max_age_seconds"""
    if max_age_seconds is None:
        max_age_seconds = DEFAULT_CLEANUP_MAX_AGE
    if request_dir is None:
        request_dir = DEFAULT_REQUEST_DIR
    
    try:
        now = time.time()
        for filename in os.listdir(request_dir):
            filepath = os.path.join(request_dir, filename)
            if os.path.isfile(filepath):
                age = now - os.path.getmtime(filepath)
                if age > max_age_seconds:
                    try:
                        os.remove(filepath)
                        logging.debug(f"Cleaned up old request: {filename}")
                    except OSError as e:
                        logging.warning(f"Failed to remove old request {filename}: {e}")
    except Exception as e:
        logging.warning(f"Failed to cleanup old requests: {e}")


def do_action_monitor(options, log_dir=None, request_dir=None, response_dir=None):
    """Monitor action - check if the fence recorder can operate"""
    
    if log_dir is None:
        log_dir = LOG_DIR
    if request_dir is None:
        request_dir = DEFAULT_REQUEST_DIR
    if response_dir is None:
        response_dir = DEFAULT_RESPONSE_DIR

    target = options.get("--plug", options.get("--port", "unknown"))
    
    # Use stderr directly if logging not yet initialized
    try:
        logging.debug(f"Monitor action for {target}")
    except NameError:
        # logging module not configured yet
        print(f"[DEBUG] Monitor action for {target}", file=sys.stderr)

    # Check directories, creating them if necessary
    dirs_to_check = {
        log_dir: os.W_OK,
        request_dir: os.W_OK,
        response_dir: os.R_OK
    }

    for path, access_mode in dirs_to_check.items():
        try:
            if not os.path.exists(path):
                os.makedirs(path, exist_ok=True)
        except OSError as e:
            # Use print as logging may not be configured
            print(f"[ERROR] Cannot create directory {path}: {e}", file=sys.stderr)
            return 1
        
        if not os.access(path, access_mode):
            # Use logging here, as directory should exist
            logging.error(f"Directory {path} is not accessible (mode: {access_mode})")
            return 1
    
    logging.debug("Monitor successful - fence recorder operational")
    return 0


def define_new_opts():
    """Define additional options specific to this fence agent"""
    
    all_opt["log_dir"] = {
        "getopt": ":",
        "longopt": "log-dir",
        "help": "--log-dir=[path]              Directory for fence event logs",
        "required": "0",
        "shortdesc": "Log directory",
        "default": "/var/log/cluster",
        "order": 1
    }
    
    all_opt["request_dir"] = {
        "getopt": ":",
        "longopt": "request-dir",
        "help": "--request-dir=[path]          Directory for fence request files",
        "required": "0",
        "shortdesc": "Request directory",
        "default": DEFAULT_REQUEST_DIR,
        "order": 2
    }
    
    all_opt["response_dir"] = {
        "getopt": ":",
        "longopt": "response-dir",
        "help": "--response-dir=[path]         Directory for fence response files",
        "required": "0",
        "shortdesc": "Response directory",
        "default": DEFAULT_RESPONSE_DIR,
        "order": 3
    }


def main():
    """Main entry point"""
    
    device_opt = ["no_password", "no_login", "port", "log_dir", "request_dir", "response_dir"]
    
    atexit.register(atexit_handler)
    
    define_new_opts()
    
    options = check_input(device_opt, process_input(device_opt))
    
    # Get directory paths from options
    request_dir = options.get("--request-dir", DEFAULT_REQUEST_DIR)
    response_dir = options.get("--response-dir", DEFAULT_RESPONSE_DIR)
    log_dir = options.get("--log-dir", LOG_DIR)
    
    # Check if this is a metadata/manpage request - skip logging setup for clean XML output
    action = options.get("--action", "")
    if action in ["metadata", "manpage"]:
        # Skip logging, directory creation, and environment validation for metadata output
        pass
    else:
        # Ensure directories exist
        try:
            os.makedirs(request_dir, exist_ok=True)
            os.makedirs(response_dir, exist_ok=True)
        except Exception as e:
            print(f"[ERROR] Cannot create request/response directories: {e}", file=sys.stderr)
            sys.exit(1)
        
        log_dir, fence_log = setup_logging(log_dir)
        
        # Validate environment configuration now that logging is set up
        config = validate_environment_config()
        fence_timeout = config.fence_timeout
        poll_interval = config.poll_interval
        cleanup_max_age = config.cleanup_max_age
    
    # Metadata and documentation
    docs = {}
    docs["shortdesc"] = "Fence agent for request/response coordination"
    docs["longdesc"] = "fence_recorder is a Pacemaker fence agent that coordinates fencing \
with external systems via a request/response file pattern.\
\n.P\n\
This agent writes fence requests to a directory and waits for an external \
coordinator to process the request and write a response file. This enables \
integration with external infrastructure management systems that need to \
perform cleanup operations before fencing is considered complete.\
\n.P\n\
The agent logs comprehensive fencing information including timestamp, \
action (reboot/off/on), target node, and fencing status.\
\n.P\n\
Request files are written to {request_dir} and responses are read from \
{response_dir}.\
\n.P\n\
Log files created:\
\n.br\n\
{log_dir}/fence-events.log - Main fence event log\
\n.br\n\
{log_dir}/fence-events-readable.log - Human-readable format\
\n.br\n\
{log_dir}/fence-events-detailed.jsonl - JSON Lines format for parsing\
".format(log_dir=log_dir, request_dir=request_dir, response_dir=response_dir)
    
    docs["vendorurl"] = "https://www.hpe.com"
    
    show_docs(options, docs)
    
    run_delay(options)
    
    # Validate required options
    if "--action" not in options:
        logging.error("Missing required option: --action")
        sys.exit(1)
    
    # Handle monitor action specially
    if options["--action"] == "monitor":
        sys.exit(do_action_monitor(options, log_dir, request_dir, response_dir))
    
    # For all other actions, use request/response pattern
    target = options.get("--plug", options.get("--port", "unknown"))
    action = options["--action"]
    
    logging.info(f"Fence action requested: {action} for target: {target}")
    
    # Cleanup old requests before creating new one (using validated max age)
    cleanup_old_requests(cleanup_max_age, request_dir)
    
    # Record the fence event (initial log)
    record_fence_event(
        action,
        target,
        "requested",
        f"Fence action {action} requested by Pacemaker",
        log_dir
    )
    
    # Write fence request for external component
    request_id = write_fence_request(action, target, request_dir)
    
    if not request_id:
        logging.error("Failed to write fence request")
        record_fence_event(action, target, "failed", "Failed to create fence request file", log_dir)
        sys.exit(1)
    
    # Wait for external fencing component to respond
    success, message, actual_action = wait_for_fence_response(
        request_id, target, timeout=fence_timeout, 
        response_dir=response_dir, poll_interval=poll_interval
    )
    
    # Record the final result and respond to Pacemaker via exit code
    # Pacemaker invokes this agent as a subprocess and checks the exit code:
    #   - Exit code 0 = fencing succeeded
    #   - Exit code 1 (or any non-zero) = fencing failed
    # This is the standard STONITH/fence agent protocol
    
    if success:
        record_fence_event(
            action,
            target,
            "completed",
            f"Fence action {actual_action} completed successfully: {message}",
            log_dir
        )
        logging.info(f"Fence operation successful: {message}")
        # Exit 0 tells Pacemaker: fencing succeeded
        sys.exit(0)
    else:
        record_fence_event(
            action,
            target,
            "failed",
            f"Fence action {action} failed: {message}",
            log_dir
        )
        logging.error(f"Fence operation failed: {message}")
        # Exit 1 tells Pacemaker: fencing failed
        sys.exit(1)


if __name__ == "__main__":
    main()

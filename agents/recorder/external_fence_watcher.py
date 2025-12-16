#!/usr/bin/env python3

#
# External Fence Watcher - Example companion utility for fence_recorder
#
# This script demonstrates how to integrate with fence_recorder by watching
# for fence request files and writing response files.
#

"""
External Fence Watcher

This script watches the fence request directory for requests from fence_recorder,
performs the fence action (or simulates it), and writes a response file.

This is an example implementation using simple file polling. In production,
replace the perform_fence_action() function with your actual fencing mechanism
(e.g., IPMI, cloud provider API, hardware management interface).

Usage:
    # Using defaults:
    ./external_fence_watcher.py

    # With custom directories (must match fence_recorder options):
    REQUEST_DIR=/custom/requests RESPONSE_DIR=/custom/responses ./external_fence_watcher.py

Environment Variables:
    REQUEST_DIR   - Directory to watch for fence requests (default: /var/run/fence_recorder/requests)
    RESPONSE_DIR  - Directory to write fence responses (default: /var/run/fence_recorder/responses)
    POLL_INTERVAL - Seconds between directory checks (default: 0.5)
"""

import os
import sys
import json
import time
import logging
import glob

# Default directories - must match fence_recorder.py defaults
REQUEST_DIR = os.environ.get("REQUEST_DIR", "/var/run/fence_recorder/requests")
RESPONSE_DIR = os.environ.get("RESPONSE_DIR", "/var/run/fence_recorder/responses")
POLL_INTERVAL = float(os.environ.get("POLL_INTERVAL", "0.5"))  # Check every 500ms

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)


def perform_fence_action(action, target_node, filesystems):
    """
    Perform the actual fence action
    
    REPLACE THIS WITH YOUR ACTUAL FENCING MECHANISM
    
    Examples:
    - Call fence_ipmi or other fence agent
    - Call cloud provider API (AWS, Azure, GCP)
    - Call hardware management interface (IPMI, iLO, DRAC)
    - Send command to PDU
    - Call custom fencing script
    
    Args:
        action: "on", "off", "reboot", "status"
        target_node: hostname of node to fence
        filesystems: list of shared filesystems on this node
    
    Returns:
        tuple: (success: bool, message: str)
    """
    logging.info(f"[SIMULATED] Performing fence action: {action} on {target_node}")
    logging.info(f"[SIMULATED] shared filesystems affected: {filesystems}")
    
    # ============================================================
    # REPLACE THIS SECTION WITH YOUR ACTUAL FENCING MECHANISM
    # ============================================================
    
    # Example: Call fence_ipmi
    # import subprocess
    # try:
    #     result = subprocess.run(
    #         ["/usr/sbin/fence_ipmi", "--action", action, "--ip", target_node],
    #         capture_output=True,
    #         text=True,
    #         timeout=30
    #     )
    #     success = result.returncode == 0
    #     message = f"fence_ipmi returned: {result.returncode}"
    #     return success, message
    # except Exception as e:
    #     return False, f"Fence operation failed: {e}"
    
    # For now, simulate fence operation
    time.sleep(2)  # Simulate fence delay
    
    return True, f"Simulated fence {action} succeeded for {target_node}"
    
    # ============================================================
    # END OF SECTION TO REPLACE
    # ============================================================


def process_fence_request(request_file):
    """Process a fence request and write response using atomic rename pattern."""
    # Skip hidden/temp files (files starting with '.')
    basename = os.path.basename(request_file)
    if basename.startswith('.'):
        return False
    
    try:
        with open(request_file, 'r') as f:
            request_data = json.load(f)
        
        request_id = request_data.get("request_id")
        action = request_data.get("action")
        target_node = request_data.get("target_node")
        filesystems = request_data.get("filesystems", [])
        
        logging.info(f"Processing fence request: id={request_id}, action={action}, target={target_node}")
        
        # Perform the actual fence action
        success, message = perform_fence_action(action, target_node, filesystems)
        
        # Write response using atomic rename pattern
        filename = f"{target_node}-{request_id}.json"
        temp_file = os.path.join(RESPONSE_DIR, f".{filename}.tmp")
        final_file = os.path.join(RESPONSE_DIR, filename)
        
        response_data = {
            "request_id": request_id,
            "success": success,
            "action_performed": action,
            "target_node": target_node,
            "message": message,
            "timestamp": time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
        }
        
        # Write to temp file, then atomic rename
        with open(temp_file, 'w') as f:
            f.write(json.dumps(response_data, indent=2))
        os.rename(temp_file, final_file)
        
        logging.info(f"Wrote fence response: success={success}, file={final_file}")
        
        # Clean up request file
        try:
            os.remove(request_file)
        except OSError:
            pass
        
        return True
        
    except Exception as e:
        logging.error(f"Failed to process fence request {request_file}: {e}")
        # Clean up temp file if it exists
        try:
            if 'temp_file' in locals():
                os.remove(temp_file)
        except OSError:
            pass
        return False


def main():
    """Main entry point"""
    
    # Ensure directories exist
    os.makedirs(REQUEST_DIR, exist_ok=True)
    os.makedirs(RESPONSE_DIR, exist_ok=True)
    
    logging.info(f"Starting fence request watcher (polling mode)...")
    logging.info(f"  Request directory: {REQUEST_DIR}")
    logging.info(f"  Response directory: {RESPONSE_DIR}")
    logging.info(f"  Poll interval: {POLL_INTERVAL}s")
    
    processed_files = set()
    
    logging.info("Fence watcher started. Press Ctrl+C to stop.")
    
    try:
        while True:
            # Find all JSON files in request directory
            request_files = glob.glob(os.path.join(REQUEST_DIR, "*.json"))
            
            for request_file in request_files:
                # Skip if already processed
                if request_file in processed_files:
                    continue
                
                # Process the request
                if process_fence_request(request_file):
                    processed_files.add(request_file)
                
                # Cleanup processed set if it gets too large
                if len(processed_files) > 1000:
                    processed_files.clear()
            
            time.sleep(POLL_INTERVAL)
            
    except KeyboardInterrupt:
        logging.info("Stopping fence watcher...")
        sys.exit(0)


if __name__ == "__main__":
    main()

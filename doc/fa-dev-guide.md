# Fence Agent Developer's Guide

## Base on current agent
The easiest way to get started is by starting with an existing agent and remove most of the code in set set_power_status(), get_power_status(), and get_list() and then update the connection and main() code.

Good choices for existing agents to use as base for new agents:
- fence_vmware_rest for REST API
- fence_ilo for other HTTP(S) APIs
- fence_ilo_ssh for SSH
- fence_ipmilan for command tools
- fence_aws/fence_azure (does imports in separate library)/fence_gce for external libraries


## git
### General
- Commit messages should start with "fence_<name>: ", "fencing: " (or other library name), "build: ".\
  If in doubt run `git log` to find examples.
- PRs without correct prefix will get squashed to correct it as part of the merge process.
- If any parameters or descriptions has been updated you'll have to run `./autogen.sh && ./configure` followed by `make xml-upload`.
- Build requirements can be easily installed on Fedora by running `sudo dnf builddep fence-agents-all`.


### Add agent
- Go to <https://github.com/ClusterLabs/fence-agents> and click Fork to create your own Fork.

```
git clone https://github.com/<your-username>/fence-agents
git remote add upstream https://github.com/ClusterLabs/fence-agents
git checkout -b fence_<name>-new-fence-agent

mkdir agents/<name>
vim agents/<name>/fence_<name>.py

# add %package/%description/%files sections for agent in spec-file
vim fence-agents.spec.in

./autogen.sh && ./configure
make xml-upload
make xml-check
# make check                  # optional - runs delay-check (verifies that the agents work correctly with the delay parameter) and xml-check

git add agents/<name>/fence_<name>.py
git commit -a -c "fence_<name>: new fence agent"
git push
```

- Click link and create Pull Request.


### Improve code/add feature/fix bugs in agent or library
- Run `git log` to see examples of comments to use with -c (or skip -c to enter it in an editor).

```
git checkout main
git fetch --all
git rebase upstream/main
git checkout -b fence_<name>-fix-<issue-description>

vim agents/<name>/fence_<name>.py

git commit -a -c "fence_<name>: fix <issue-description>"
git push
```

- Click link and create Pull Request.


## Development
### Import libraries/add state dictionary
To develop you need to import the fencing library and some generic libraries, and define expected values for power states that will be translated translated to "on", "off", or "error".

The state dictionary contains translations from expected values from the fence device and their corresponding value in fencing (on/off/error).

Example:
```
import sys
import atexit
import logging
sys.path.append("@FENCEAGENTSLIBDIR@")
from fencing import *
from fencing import fail, run_delay, EC_LOGIN_DENIED, EC_STATUS

state = {"POWERED_ON": "on", 'POWERED_OFF': "off", 'SUSPENDED': "off"}
```

***only import used functions/return values from the fencing library in the 2nd `from fencing import` line***

### Logging and failing
Use logging.error(), logging.warn(), logging.debug(), and logging.info() to log output.
- logging.info() should only be used when needed to avoid spamming the logs.
- logging.debug() is good for debugging (shown when you use -v or set verbose=1).
- `if options["--verbose-level"] > 1:` can be used to only print additional logging.debug() messages when -vv (or more v's) or verbose=2 or higher.

Use `fail(<error-code>)` or `fail_usage("Failed: <error message>")` to exit with error code message or log Failed: <error message> with generic error code.
- fail() logs the specified error message from <https://github.com/ClusterLabs/fence-agents/blob/main/lib/fencing.py.py#L574> and exit with generic error code.
- EC_* error codes can be imported from the fencing library:\
  <https://github.com/ClusterLabs/fence-agents/blob/main/lib/fencing.py.py#L20>
- To exit with specific error codes either use logging.error() followed by sys.exit(<error-code>) or fail(<error-code>, stop=False), which allows you to return or sys.exit() with other error codes.

### get_power_status() / set_power_status() / get_list()
- These functions defines the code to get or set status, and get list of nodes, which are run by the fencing library to turn off/on nodes or get a list of nodes available.

```
def get_power_status(conn, options):
    # code to get power status
    result = ...
    return state[result]

def set_power_status(conn, options):
	action = {
		"on" : "start",
		"off" : "stop"
	}[options["--action"]]

	try:
		# code to set power status. use "action" variable, which translates on and off to the equivalent command that the device expects
	except Exception as e:
		logging.debug("Failed: {}".format(e))
		fail(EC_STATUS)

def get_list(conn, options):
	outlets = {}

	# code to get node list

	for r in res["value"]:
		outlets[r["name"]] = ("", state[r["power_state"]])

	return outlets
```

### reboot_cycle()
***The reboot cycle method is not recommended as it might report success before the node is powered off.***
- fence_ipmilan contains a minimal reboot_cycle() approach.
- Add "method" to the device_opt list.
- Update all_opt["method"]["help"] with a warning that it might report success before the node is powered off.
- Add reboot_cycle function to fence_action() call in main().

Example:
```
def reboot_cycle(_, options):
        output = _run_command(options, "cycle")
        return bool(re.search('chassis power control: cycle', str(output).lower()))
...

def main():
...
        device_opt = [ ..., "method" ]
...
        all_opt["method"]["help"] = "-m, --method=[method]          Method to fence (onoff|cycle) (Default: onoff)\n" \
                                    "WARNING! This fence agent might report success before the node is powered off, when cycle method is used. " \
                                    "You should use -m/method onoff if your fence device works correctly with that option."
...
        result = fence_action(None, options, set_power_status, get_power_status, None, reboot_cycle)
```

### define_new_opts()
Specifies device specific parameters with defaults.
- getopt is ":" for parameters that require a value and "" for parameters that get set without a value (e.g. -v)
- do not use short short opts (e.g. "a:" or "a") as they are reserved for the fencing library
- set required to 1 if the parameter is required (except for -o metadata or -h/--help)
- Use `if "--<parameter>" in options:` to check value-less parameters like --verbose and `if options.get("--<parameter>") == "<expected-value>":` to check the value of parameters.

```
def define_new_opts():
	all_opt["api_path"] = {
		"getopt" : ":",
		"longopt" : "api-path",
		"help" : "--api-path=[path]              The path part of the API URL",
		"default" : "/rest",
		"required" : "0",
		"shortdesc" : "The path part of the API URL",
		"order" : 2}
	all_opt["filter"] = {
		"getopt" : ":",
		"longopt" : "filter",
		"help" : "--filter=[filter]              Filter to only return relevant VMs"
			 " (e.g. \"filter.names=node1&filter.names=node2\").",
		"required" : "0",
		"shortdesc" : "Filter to only return relevant VMs. It can be used to avoid "
			      "the agent failing when more than 1000 VMs should be returned.",
		"order" : 2}
```

### main()
Defines parameters and general logic to show docs (when requested), or run specific fence action.
- device_opt[] is a list of parameters to be used from the fencing library
- define_new_opts() adds the device specific parameters defined above
- all_opt["parameter"]["default"] allows you to override the default value for
  parameters from the fencing library
- options = check_input(device_opt, process_input(device_opt)) processes all the parameters
  and checks that they are of the expected type
- docs["shortdesc"] / docs["longdesc"] allows settings short and long description for metadata/help text (-h)
- show_docs(options, docs) prints metadata or help text depending on whether you specify -o metadata or -h
- run_delay(options) delays the fencing agent --delay=/delay= seconds when set
- conn = connect(options) specifies function to call, and registers the connection as conn
- atexit.register(disconnect, conn) tells the agent to run disconnect(conn) when it exits (e.g. timeouts or fails)
- result = fence_action(conn, options, set_power_status, get_power_status, get_list) run set_power_status(),
  get_power_status(), or get_list() depending on which action (-o) was specified
- sys.exit(result) return return code from function run by fence_action()

```
def main():
	device_opt = [
		"ipaddr",
		"api_path",
		"login",
		"passwd",
		"ssl",
		"notls",
		"web",
		"port",
		"filter",
	]

	atexit.register(atexit_handler)
	define_new_opts()

	all_opt["shell_timeout"]["default"] = "5"
	all_opt["power_wait"]["default"] = "1"

	options = check_input(device_opt, process_input(device_opt))

	docs = {}
	docs["shortdesc"] = "Fence agent for VMware REST API"
	docs["longdesc"] = """fence_vmware_rest is an I/O Fencing agent which can be \
used with VMware API to fence virtual machines.

NOTE: If there's more than 1000 VMs there is a filter parameter to work around \
the API limit. See https://code.vmware.com/apis/62/vcenter-management#/VM%20/get_vcenter_vm \
for full list of filters."""
	docs["vendorurl"] = "https://www.vmware.com"
	show_docs(options, docs)

	####
	## Fence operations
	####
	run_delay(options)

	conn = connect(options)
	atexit.register(disconnect, conn)

	result = fence_action(conn, options, set_power_status, get_power_status, get_list)

	sys.exit(result)

if __name__ == "__main__":
	main()
```

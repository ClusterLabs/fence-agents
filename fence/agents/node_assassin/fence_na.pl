#!/usr/bin/perl
#
# Node Assassin - Fence Agent
# Digimer; digimer@alteeve.com
# Jun. 27, 2010
# Version: 1.1.5
#
# Bugs;
# - None known, many expected
# 

# Play safe!
use strict;
use warnings;

# Load our library.
require '/etc/fence_na/fence_na.lib';

# IO::Handle is used for logging and Net::Telnet is used for communicating with
# the Node Assassin(s).
use IO::Handle;
use Net::Telnet;

# These are the default values and will be over-written by the config file's
# variables which in turn can, in some cases, be over-written by command line
# arguments.
# Please see '@NACONFFILE@' for details on each option.
my $conf={
	'system'	=>	{
		max_valid_state	=>	3,
		conf_file	=>	"@NACONFFILE@",
		quiet		=>	"",
		version		=>	0,
		list		=>	"",
		monitor		=>	"",
		na_id		=>	0,
		got_cla		=>	0,	# This is set if command line arguments are read.
		debug		=>	0,
	},
	na		=>	{
		ipaddr		=>	"",
		tcp_port	=>	"238",
		port		=>	"",
		login		=>	"",
		passwd		=>	"",
		port		=>	"",
		set_state	=>	"",
		passwd_script	=>	"",
		action		=>	"",
		agent		=>	"",	# This is only used by 'fenced'
		na_name		=>	"",	# This is used for the 'list' function.
		handle		=>	"",
		max_node	=>	0,
		set_state	=>	[],	# This array will store the states to set based on the action passed for the proper ports.
	}
};

# This method can't pass in the '$log' handle, obviously, as it does not yet
# exist.
read_conf($conf);

# Log file for output.
my $log=IO::Handle->new();
print "Opening: [$conf->{'system'}{'log'}] for logging.\n"  if $conf->{'system'}{debug};
open ($log, ">$conf->{'system'}{'log'}") || die "Failed to open: [$conf->{'system'}{'log'}] for writing; Error: $!\n";

# Set STDOUT and $log to hot (unbuffered) output.
if (1)
{
	select $log;
	$|=1;
	select STDOUT;
	$|=1;
}

# If this gets set in the next two function, the agent will exit.
my $bad=0;

# Read in arguments from the command line.
($bad)=read_cla($conf, $log, $bad);

# Now read in arguments from STDIN, which is how 'fenced' passes arguments.
($bad)=read_stdin($conf, $log, $bad);

# This makes sure the node ID is either zero-padded or '00'.
$conf->{na}{port}=$conf->{na}{port} ? $conf->{na}{port}=sprintf("%02d", $conf->{na}{port}) : "00";
record($conf, $log, "Will use port: [$conf->{na}{port}]\n") if $conf->{'system'}{debug};

# Find the TCP port from the config file.
foreach my $i (1..$conf->{'system'}{na_num})
{
	if ((lc($conf->{na}{$i}{ipaddr}) eq lc($conf->{na}{ipaddr})))
	{
		$conf->{'system'}{na_id}=$i;
		record($conf, $log, __LINE__."; system::na_id: [$conf->{'system'}{na_id}]\n") if $conf->{'system'}{debug};
		$conf->{na}{tcp_port}=$conf->{na}{$i}{tcp_port};
		record($conf, $log, __LINE__."; na::tcp_port: [$conf->{na}{tcp_port}]\n") if $conf->{'system'}{debug};
		$conf->{na}{na_name}=$conf->{na}{$i}{na_name} ? $conf->{na}{$i}{na_name} : "Node Assassin #$i";
		record($conf, $log, __LINE__."; na::na_name: [$conf->{na}{na_name}]\n") if $conf->{'system'}{debug};
		$conf->{na}{max_nodes}=$conf->{na}{$i}{max_nodes};
		record($conf, $log, __LINE__."; na::max_nodes: [$conf->{na}{max_nodes}]\n") if $conf->{'system'}{debug};
	}
}

die "Exiting on errors.\n" if $bad;
my @ny=("no", "yes");
record($conf, $log, "Node Assassin: . [$conf->{na}{ipaddr}].\n");
record($conf, $log, "TCP Port: ...... [$conf->{na}{tcp_port}].\n");
record($conf, $log, "Node: .......... [$conf->{na}{port}].\n");
record($conf, $log, "Login: ......... [$conf->{na}{login}].\n");
record($conf, $log, "Password: ...... [$conf->{na}{passwd}].\n");
record($conf, $log, "Action: ........ [$conf->{na}{action}].\n");
record($conf, $log, "Version Request: [".$ny[$conf->{'system'}{version}]."].\n");
record($conf, $log, "Done reading args.\n");

# If I've been asked to show the version information, do so and then exit.
record($conf, $log, "Version: ..... [$conf->{'system'}{version}].\n") if $conf->{'system'}{debug};
if ($conf->{'system'}{version})
{
	version($conf, $log);
	do_exit($conf, $log, 0);
}

# Connect to the Node Assassin.
connect_to_na($conf, $log);

# Validate credentials.
# NOTE: Checking before the telnet fails on the exit. Also, this will be moved
# into the Node Assassin soon anyway.
if (($conf->{na}{login} ne $conf->{'system'}{username}) or ($conf->{na}{passwd} ne $conf->{'system'}{password}))
{
	record($conf, $log, "Username and/or password invalid. Did you use the command line switches properly?\n");
	do_exit($conf, $log, 8);
}

###############################################################################
# What do?                                                                    #
###############################################################################

# When asked to 'monitor' or 'list'. being multi-port, this will return a CSV
# of nodes and their aliases where found in the config file.
record($conf, $log, "Action: ........ [$conf->{na}{action}].\n") if $conf->{'system'}{debug};
if (($conf->{na}{action} eq "monitor") or ($conf->{na}{action} eq "list"))
{
	record($conf, $log, "Calling the 'show_list' function.\n") if $conf->{'system'}{debug};
	show_list($conf, $log);
	do_exit($conf, $log, 0);
}

# If I made it this far, I am setting a state. Sort out what state from the
# values in my conf->{na} hash.
record($conf, $log, "Setting node: [$conf->{na}{port}] to action: [$conf->{na}{action}] using the Node Assassin: [$conf->{na}{ipaddr}] using the login: [$conf->{na}{login}]\n") if $conf->{'system'}{debug};

# Convert the action into Node Assassin protocol arguments.
process_action($conf, $log);

# Now execute the action plan.
my $exit_code=do_actions($conf, $log);
record($conf, $log, "All calls complete, exiting.\n") if $conf->{'system'}{debug};

# Cleanup and exit.
do_exit($conf, $log, $exit_code);

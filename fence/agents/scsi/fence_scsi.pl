#!/usr/bin/perl

use File::Basename;
use Getopt::Std;
use POSIX;

#BEGIN_VERSION_GENERATION
$RELEASE_VERSION="";
$REDHAT_COPYRIGHT="";
$BUILD_DATE="";
#END_VERSION_GENERATION

my $ME = fileparse ($0, ".pl");

################################################################################

sub log_debug ($)
{
    my $time = strftime "%b %e %T", localtime;
    my ($msg) = @_;

    print STDOUT "$time $ME: [debug] $msg\n" unless defined ($opt_q);

    return;
}

sub log_error ($)
{
    my $time = strftime "%b %e %T", localtime;
    my ($msg) = @_;

    print STDERR "$time $ME: [error] $msg\n" unless defined ($opt_q);

    exit (1);
}

sub do_action_on ($@)
{
    my $self = (caller(0))[3];
    my ($node_key, @devices) = @_;

    key_write ($node_key);

    foreach $dev (@devices) {
	log_error ("device $dev does not exist") if (! -e $dev);
	log_error ("device $dev is not a block device") if (! -b $dev);

	do_register_ignore ($node_key, $dev);

	if (!get_reservation_key ($dev)) {
	    do_reserve ($node_key, $dev);
	}
    }

    return;
}

sub do_action_off ($@)
{
    my $self = (caller(0))[3];
    my ($node_key, @devices) = @_;

    my $host_key = key_read ();

    if ($host_key eq $node_key) {
	log_error ($self);
    }

    foreach $dev (@devices) {
	log_error ("device $dev does not exist") if (! -e $dev);
	log_error ("device $dev is not a block device") if (! -b $dev);

	my @keys = grep { /$node_key/ } get_registration_keys ($dev);

	if (scalar (@keys) != 0) {
	    do_preempt_abort ($host_key, $node_key, $dev);
	}
    }

    return;
}

sub do_action_status ($@)
{
    my $self = (caller(0))[3];
    my ($node_key, @devices) = @_;

    my $dev_count = 0;
    my $key_count = 0;

    foreach $dev (@devices) {
	log_error ("device $dev does not exist") if (! -e $dev);
	log_error ("device $dev is not a block device") if (! -b $dev);

	my @keys = grep { /$node_key/ } get_registration_keys ($dev);

	if (scalar (@keys) != 0) {
	    $dev_count++;
	}
    }

    if ($dev_count != 0) {
	exit (0);
    }
    else {
	exit (2);
    }
}

sub do_register ($$$)
{
    my $self = (caller(0))[3];
    my ($host_key, $node_key, $dev) = @_;

    if (substr ($dev, 5) =~ /^dm/) {
	my @slaves = get_mpath_slaves ($dev);
	foreach (@slaves) {
	    do_register ($node_key, $_);
	}
	return;
    }

    log_debug ("$self (host_key=$host_key, node_key=$node_key, dev=$dev)");

    my $cmd;
    my $out;

    $cmd = "sg_persist -n -o -G -K $host_key -S $node_key -d $dev";
    $cmd .= " -Z" if (defined $opt_a);
    $out = qx { $cmd };

    die "[error]: $self\n" if ($?>>8);

    return;
}

sub do_register_ignore ($$)
{
    my $self = (caller(0))[3];
    my ($node_key, $dev) = @_;

    if (substr ($dev, 5) =~ /^dm/) {
	my @slaves = get_mpath_slaves ($dev);
	foreach (@slaves) {
	    do_register_ignore ($node_key, $_);
	}
	return;
    }

    log_debug ("$self (node_key=$node_key, dev=$dev)");

    my $cmd;
    my $out;

    $cmd = "sg_persist -n -o -I -S $node_key -d $dev";
    $cmd .= " -Z" if (defined $opt_a);
    $out = qx { $cmd };

    die "[error]: $self\n" if ($?>>8);

    return;
}

sub do_reserve ($$)
{
    my $self = (caller(0))[3];
    my ($host_key, $dev) = @_;

    log_debug ("$self (host_key=$host_key, dev=$dev)");

    my $cmd = "sg_persist -n -o -R -T 5 -K $host_key -d $dev";
    my $out = qx { $cmd };

    die "[error]: $self\n" if ($?>>8);

    return;
}

sub do_release ($$)
{
    my $self = (caller(0))[3];
    my ($host_key, $dev) = @_;

    log_debug ("$self (host_key=$host_key, dev=$dev)");

    my $cmd = "sg_persist -n -o -L -T 5 -K $host_key -d $dev";
    my $out = qx { $cmd };

    die "[error]: $self\n" if ($?>>8);

    return;
}

sub do_preempt ($$$)
{
    my $self = (caller(0))[3];
    my ($host_key, $node_key, $dev) = @_;

    log_debug ("$self (host_key=$host_key, node_key=$node_key, dev=$dev)");

    my $cmd = "sg_persist -n -o -P -T 5 -K $host_key -S $node_key -d $dev";
    my $out = qx { $cmd };

    die "[error]: $self\n" if ($?>>8);

    return;
}

sub do_preempt_abort ($$$)
{
    my $self = (caller(0))[3];
    my ($host_key, $node_key, $dev) = @_;

    log_debug ("$self (host_key=$host_key, node_key=$node_key, dev=$dev)");

    my $cmd = "sg_persist -n -o -A -T 5 -K $host_key -S $node_key -d $dev";
    my $out = qx { $cmd };

    die "[error]: $self\n" if ($?>>8);

    return;
}

sub key_read ()
{
    my $self = (caller(0))[3];
    my $key;

    open (\*FILE, "</var/lib/cluster/fence_scsi.key") or die "$!\n";
    chomp ($key = <FILE>);
    close (FILE);

    return ($key);
}

sub key_write ($)
{
    my $self = (caller(0))[3];

    open (\*FILE, ">/var/lib/cluster/fence_scsi.key") or die "$!\n";
    print FILE "$_[0]\n";
    close (FILE);

    return;
}

sub get_key ($)
{
    my $self = (caller(0))[3];

    my $key = sprintf ("%.4x%.4x", get_cluster_id (), get_node_id ($_[0]));

    return ($key);
}

sub get_node_id ($)
{
    my $self = (caller(0))[3];
    my $node_id;

    my $cmd = "cman_tool nodes -n $_[0] -F id";
    my $out = qx { $cmd };

    die "[error]: $self\n" if ($?>>8);

    chomp ($out);

    $node_id = $out;

    return ($node_id);
}

sub get_cluster_id ()
{
    my $self = (caller(0))[3];
    my $cluster_id;

    my $cmd = "cman_tool status";
    my @out = qx { $cmd };

    die "[error]: $self\n" if ($?>>8);

    foreach (@out) {
	chomp;
	my ($param, $value) = split (/\s*:\s*/, $_);
	if ($param =~ /^cluster\s+id/i) {
	    $cluster_id = $value;
	}
    }

    return ($cluster_id);
}

sub get_devices_clvm ()
{
    my $self = (caller(0))[3];
    my @devices;

    my $cmd = "vgs --noheadings " .
	"    --separator : " .
	"    --sort pv_uuid " .
	"    --options vg_attr,pv_name " .
	"    --config 'global { locking_type = 0 } " .
	"              devices { preferred_names = [ \"^/dev/dm\" ] }'";

    my @out = qx { $cmd 2> /dev/null };

    die "[error]: $self\n" if ($?>>8);

    foreach (@out) {
	chomp;
	my ($vg_attr, $pv_name) = split (/:/, $_);
	if ($vg_attr =~ /c$/) {
	    push (@devices, $pv_name);
	}
    }

    return (@devices);
}

sub get_devices_scsi ()
{
    my $self = (caller(0))[3];
    my @devices;

    opendir (\*DIR, "/sys/block/") or die "$!\n";
    @devices = grep { /^sd/ } readdir (DIR);
    closedir (DIR);

    return (@devices);
}

sub get_mpath_name ($)
{
    my $self = (caller(0))[3];
    my ($dev) = @_;
    my $name;

    if ($dev =~ /^\/dev\//) {
	$dev = substr ($dev, 5);
    }

    open (\*FILE, "/sys/block/$dev/dm/name") or die "$!\n";
    chomp ($name = <FILE>);
    close (FILE);

    return ($name);
}

sub get_mpath_uuid ($)
{
    my $self = (caller(0))[3];
    my ($dev) = @_;
    my $uuid;

    if ($dev =~ /^\/dev\//) {
	$dev = substr ($dev, 5);
    }

    open (\*FILE, "/sys/block/$dev/dm/uuid") or die "$!\n";
    chomp ($uuid = <FILE>);
    close (FILE);

    return ($name);
}

sub get_mpath_slaves ($)
{
    my $self = (caller(0))[3];
    my ($dev) = @_;
    my @slaves;

    if ($dev =~ /^\/dev\//) {
	$dev = substr ($dev, 5);
    }

    opendir (\*DIR, "/sys/block/$dev/slaves/") or die "$!\n";

    @slaves = grep { !/^\./ } readdir (DIR);
    if ($slaves[0] =~ /^dm/) {
	@slaves = get_mpath_slaves ($slaves[0]);
    } else {
	@slaves = map { "/dev/$_" } @slaves;
    }

    closedir (DIR);

    return (@slaves);
}

sub get_registration_keys ($)
{
    my $self = (caller(0))[3];
    my ($dev) = @_;
    my @keys;

    my $cmd = "sg_persist -n -i -k -d $dev";
    my @out = qx { $cmd };

    die "[error]: $self\n" if ($?>>8);

    foreach (@out) {
	chomp;
	if ($_ =~ s/^\s+0x//i) {
	    push (@keys, $_);
	}
    }

    return (@keys);
}

sub get_reservation_key ($)
{
    my $self = (caller(0))[3];
    my ($dev) = @_;
    my $key;

    my $cmd = "sg_persist -n -i -r -d $dev";
    my @out = qx { $cmd };

    die "[error]: $self\n" if ($?>>8);

    foreach (@out) {
	chomp;
	if ($_ =~ s/^\s+key=0x//i) {
	    $key = $_;
	    last;
	}
    }

    return ($key)
}

sub get_options_stdin ()
{
    my $num = 0;

    while (<STDIN>) {
	chomp;
	s/^\s*//;
	s/\s*$//;

	next if (/^#/);

	$num++;

	next unless ($_);

	my ($opt, $arg) = split (/\s*=\s*/, $_);

	if ($opt eq "") {
	    exit (1);
	}
	elsif ($opt eq "aptpl") {
	    $opt_a = $arg;
	}
	elsif ($opt eq "devices") {
	    $opt_d = $arg;
	}
	elsif ($opt eq "logfile") {
	    $opt_f = $arg;
	}
	elsif ($opt eq "key") {
	    $opt_k = $arg;
	}
	elsif ($opt eq "nodename") {
	    $opt_n = $arg;
	}
	elsif ($opt eq "action") {
	    $opt_o = $arg;
	}
    }
}

sub print_usage ()
{
    print "Usage:\n";
    print "\n";
    print "$ME [options]\n";
    print "\n";
    print "Options:\n";
    print "  -a               Use APTPL flag\n";
    print "  -d <devices>     Devices to be used for action\n";
    print "  -f <logfile>     File to write debug/error output\n";
    print "  -h               Usage\n";
    print "  -k <key>         Key to be used for current action\n";
    print "  -n <nodename>    Name of node to operate on\n";
    print "  -o <action>      Action: off (default), on, or status\n";
    print "  -q               Quiet mode\n";
    print "  -V               Version\n";

    exit (0);
}

sub print_version ()
{
    print "$ME $RELEASE_VERSION $BUILD_DATE\n";
    print "$REDHAT_COPYRIGHT\n" if ( $REDHAT_COPYRIGHT );

    exit (0);
}

sub print_metadata ()
{
    print "<?xml version=\"1.0\" ?>\n";
    print "<resource-agent name=\"fence_scsi\"" .
          " shortdesc=\"fence agent for SCSI-3 persistent reservations\">\n";
    print "<longdesc>fence_scsi</longdesc>\n";
    print "<parameters>\n";
    print "\t<parameter name=\"aptpl\" unique=\"1\" required=\"0\">\n";
    print "\t\t<getopt mixed=\"-a\"/>\n";
    print "\t\t<content type=\"boolean\"/>\n";
    print "\t\t<shortdesc lang=\"en\">" .
          "Use APTPL flag for registrations" .
          "</shortdesc>\n";
    print "\t</parameter>\n";
    print "\t<parameter name=\"devices\" unique=\"1\" required=\"0\">\n";
    print "\t\t<getopt mixed=\"-d\"/>\n";
    print "\t\t<content type=\"string\"/>\n";
    print "\t\t<shortdesc lang=\"en\">" .
          "List of devices to be used for fencing action" .
          "</shortdesc>\n";
    print "\t</parameter>\n";
    print "\t<parameter name=\"logfile\" unique=\"1\" required=\"0\">\n";
    print "\t\t<getopt mixed=\"-f\"/>\n";
    print "\t\t<content type=\"string\"/>\n";
    print "\t\t<shortdesc lang=\"en\">" .
          "File to write error/debug messages" .
          "</shortdesc>\n";
    print "\t</parameter>\n";
    print "\t<parameter name=\"key\" unique=\"1\" required=\"0\">\n";
    print "\t\t<getopt mixed=\"-k\"/>\n";
    print "\t\t<content type=\"string\"/>\n";
    print "\t\t<shortdesc lang=\"en\">" .
          "Key value to be used for fencing action" .
          "</shortdesc>\n";
    print "\t</parameter>\n";
    print "\t<parameter name=\"action\" unique=\"1\" required=\"0\">\n";
    print "\t\t<getopt mixed=\"-o\"/>\n";
    print "\t\t<content type=\"string\" default=\"off\"/>\n";
    print "\t\t<shortdesc lang=\"en\">" .
          "Fencing action" .
          "</shortdesc>\n";
    print "\t</parameter>\n";
    print "\t<parameter name=\"nodename\" unique=\"1\" required=\"0\">\n";
    print "\t\t<getopt mixed=\"-n\"/>\n";
    print "\t\t<content type=\"string\"/>\n";
    print "\t\t<shortdesc lang=\"en\">" .
          "Name of node" .
          "</shortdesc>\n";
    print "\t</parameter>\n";
    print "</parameters>\n";
    print "<actions>\n";
    print "\t<action name=\"on\"/>\n";
    print "\t<action name=\"off\"/>\n";
    print "\t<action name=\"status\"/>\n";
    print "\t<action name=\"metadata\"/>\n";
    print "</actions>\n";
    print "</resource-agent>\n";

    exit (0);
}

################################################################################

if (@ARGV > 0) {
    getopts ("ad:f:hk:n:o:qV") or print_usage;

    print_usage if (defined $opt_h);
    print_version if (defined $opt_V);

    ## handle the metadata action here to avoid other parameter checks
    ##
    if ($opt_o =~ /^metadata$/i) {
	print_metadata;
    }
}
else {
    get_options_stdin ();
}

## if the logfile (-f) parameter was specified, open the logfile
## and redirect STDOUT and STDERR to the logfile.
##
if (defined $opt_f) {
    open (LOG, >">$opt_f") or die "$!\n";
    open (STDOUT, ">&LOG");
    open (STDERR, ">&LOG");
}

## verify that either key or nodename have been specified
##
if ((!defined $opt_n) && (!defined $opt_k)) {
    print_usage ();
}

## determine key value
##
if (defined $opt_k) {
    $key = $opt_k;
}
else {
    $key = get_key ($opt_n);
}

## verify that key is not zero
##
if ($key == 0) {
    log_error ("key cannot be zero");
}

## remove any leading zeros from key
##
if ($key =~ /^0/) {
    $key =~ s/^0+//;
}

## get devices
##
if (defined $opt_d) {
    @devices = split (/\s*,\s*/, $opt_d);
}
else {
    @devices = get_devices_clvm ();
}

## verify that device list is not empty
##
if (scalar (@devices) == 0) {
    log_error ("no devices found");
}

## default action is "off"
##
if (!defined $opt_o) {
    $opt_o = "off";
}

## determine the action to perform
##
if ($opt_o =~ /^on$/i) {
    do_action_on ($key, @devices);
}
elsif ($opt_o =~ /^off$/i) {
    do_action_off ($key, @devices);
}
elsif ($opt_o =~ /^status/i) {
    do_action_status ($key, @devices);
}
else {
    log_error ("unknown action '$opt_o'");
    exit (1);
}

## close the logfile
##
if (defined $opt_f) {
    close (LOG);
}

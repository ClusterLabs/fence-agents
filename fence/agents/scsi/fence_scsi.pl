#!/usr/bin/perl

use File::Basename;
use Getopt::Std;
use IPC::Open3;

#BEGIN_VERSION_GENERATION
$RELEASE_VERSION="";
$REDHAT_COPYRIGHT="";
$BUILD_DATE="";
#END_VERSION_GENERATION

my $ME = fileparse ($0, ".pl");

################################################################################

sub log_debug ($)
{
    my ($msg) = @_;

    print STDOUT "[debug]: $msg\n" unless defined ($opt_q);
}

sub log_error ($)
{
    my ($msg) = @_;

    print STDERR "[error]: $msg\n" unless defined ($opt_q);
}

sub do_action_on ($@)
{
    (my $self = (caller(0))[3]) =~ s/^main:://;

    my ($node_key, @devices) = @_;

    key_write ($node_key);

    foreach $dev (@devices) {
	do_register_ignore ($node_key, $dev);

	if (!get_reservation_key ($dev)) {
	    do_reserve ($node_key, $dev);
	}
    }
}

sub do_action_off ($@)
{
    (my $self = (caller(0))[3]) =~ s/^main:://;

    my ($node_key, @devices) = @_;

    my $host_key = key_read ();

    if ($host_key eq $node_key) {
	log_error ($self);
	exit (1);
    }

    foreach $dev (@devices) {
	my @keys = grep { /$node_key/ } get_registration_keys ($dev);

	if (scalar (@keys) != 0) {
	    do_preempt_abort ($host_key, $node_key, $dev);
	}
    }
}

sub do_action_status ($@)
{
    (my $self = (caller(0))[3]) =~ s/^main:://;

    my ($node_key, @devices) = @_;

    my $dev_count = 0;
    my $key_count = 0;

    foreach $dev (@devices) {
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
    (my $self = (caller(0))[3]) =~ s/^main:://;

    my ($host_key, $node_key, $dev) = @_;

    if (substr ($dev, 5) =~ /^dm/) {
	my @slaves = get_mpath_slaves ($dev);

	foreach (@slaves) {
	    do_register ($node_key, $_);
	}
	return;
    }

    my $cmd = "sg_persist -n -o -G -K $host_key -S $node_key -d $dev";
    $cmd .= " -Z" if (defined $opt_a);

    my $pid = open3 (\*IN, \*OUT, \*ERR, $cmd) or die "$!\n";

    die "[error]: $self\n" if ($?>>8);

    close (IN);
    close (OUT);
    close (ERR);
}

sub do_register_ignore ($$)
{
    (my $self = (caller(0))[3]) =~ s/^main:://;

    my ($node_key, $dev) = @_;

    if (substr ($dev, 5) =~ /^dm/) {
	my @slaves = get_mpath_slaves ($dev);

	foreach (@slaves) {
	    do_register_ignore ($node_key, $_);
	}
	return;
    }

    my $cmd = "sg_persist -n -o -I -S $node_key -d $dev";
    $cmd .= " -Z" if (defined $opt_a);

    my $pid = open3 (\*IN, \*OUT, \*ERR, $cmd) or die "$!\n";

    waitpid ($pid, 0);

    die "[error]: $self\n" if ($?>>8);

    close (IN);
    close (OUT);
    close (ERR);
}

sub do_reserve ($$)
{
    (my $self = (caller(0))[3]) =~ s/^main:://;

    my ($host_key, $dev) = @_;

    my $cmd = "sg_persist -n -o -R -T 5 -K $host_key -d $dev";
    my $pid = open3 (\*IN, \*OUT, \*ERR, $cmd) or die "$!\n";

    waitpid ($pid, 0);

    die "[error]: $self\n" if ($?>>8);

    close (IN);
    close (OUT);
    close (ERR);
}

sub do_release ($$)
{
    (my $self = (caller(0))[3]) =~ s/^main:://;

    my ($host_key, $dev) = @_;

    my $cmd = "sg_persist -n -o -L -T 5 -K $host_key -d $dev";
    my $pid = open3 (\*IN, \*OUT, \*ERR, $cmd) or die "$!\n";

    waitpid ($pid, 0);

    die "[error]: $self\n" if ($?>>8);

    close (IN);
    close (OUT);
    close (ERR);
}

sub do_preempt ($$$)
{
    (my $self = (caller(0))[3]) =~ s/^main:://;

    my ($host_key, $node_key, $dev) = @_;

    my $cmd = "sg_persist -n -o -P -T 5 -K $host_key -S $node_key -d $dev";
    my $pid = open3 (\*IN, \*OUT, \*ERR, $cmd) or die "$!\n";

    waitpid ($pid, 0);

    die "[error]: $self\n" if ($?>>8);

    close (IN);
    close (OUT);
    close (ERR);
}

sub do_preempt_abort ($$$)
{
    (my $self = (caller(0))[3]) =~ s/^main:://;

    my ($host_key, $node_key, $dev) = @_;

    my $cmd = "sg_persist -n -o -A -T 5 -K $host_key -S $node_key -d $dev";
    my $pid = open3 (\*IN, \*OUT, \*ERR, $cmd) or die "$!\n";

    waitpid ($pid, 0);

    die "[error]: $self ($dev)\n" if ($?>>8);

    close (IN);
    close (OUT);
    close (ERR);
}

sub key_read ()
{
    (my $self = (caller(0))[3]) =~ s/^main:://;

    open (\*FILE, "</var/lib/cluster/fence_scsi.key") or die "$!\n";

    chomp (my $key = <FILE>);

    close (FILE);

    return ($key);
}

sub key_write ($)
{
    (my $self = (caller(0))[3]) =~ s/^main:://;

    open (\*FILE, ">/var/lib/cluster/fence_scsi.key") or die "$!\n";

    print FILE "$_[0]\n";

    close (FILE);
}

sub get_key ($)
{
    (my $self = (caller(0))[3]) =~ s/^main:://;

    my $key = sprintf ("%.4x%.4x", get_cluster_id (), get_node_id ($_[0]));

    return ($key);
}

sub get_node_id ($)
{
    (my $self = (caller(0))[3]) =~ s/^main:://;

    my $cmd = "cman_tool nodes -n $_[0] -F id";
    my $pid = open3 (\*IN, \*OUT, \*ERR, $cmd) or die "$!\n";

    waitpid ($pid, 0);

    die "[error]: $self\n" if ($?>>8);

    chomp (my $node_id = <OUT>);

    close (IN);
    close (OUT);
    close (ERR);

    return ($node_id);
}

sub get_cluster_id ()
{
    (my $self = (caller(0))[3]) =~ s/^main:://;

    my $cmd = "cman_tool status";
    my $pid = open3 (\*IN, \*OUT, \*ERR, $cmd) or die "$!\n";

    waitpid ($pid, 0);

    die "[error]: $self\n" if ($?>>8);

    my $cluster_id;

    while (<OUT>) {
	chomp;

	my ($param, $value) = split (/\s*:\s*/, $_);

	if ($param =~ /^cluster\s+id/i) {
	    $cluster_id = $value;
	}
    }

    close (IN);
    close (OUT);
    close (ERR);

    return ($cluster_id);
}

sub get_devices_clvm ()
{
    (my $self = (caller(0))[3]) =~ s/^main:://;

    my $cmd = "vgs --noheadings " .
              "    --separator : " .
              "    --sort pv_uuid " .
              "    --options vg_attr,pv_name " .
              "    --config 'global { locking_type = 0 } " .
              "              devices { preferred_names = [ \"^/dev/dm\" ] }'";

    my $pid = open3 (\*IN, \*OUT, \*ERR, $cmd) or die "$!\n";

    waitpid ($pid, 0);

    die "[error]: $self\n" if ($?>>8);

    my @devices;

    while (<OUT>) {
	chomp;

	my ($vg_attr, $pv_name) = split (/:/, $_);

	if ($vg_attr =~ /c$/) {
	    push (@devices, $pv_name);
	}
    }

    close (IN);
    close (OUT);
    close (ERR);

    return (@devices);
}

sub get_devices_scsi ()
{
    (my $self = (caller(0))[3]) =~ s/^main:://;

    opendir (\*DIR, "/sys/block/") or die "$!\n";

    my @devices = grep { /^sd/ } readdir (DIR);

    closedir (DIR);

    return (@devices);
}

sub get_mpath_name ($)
{
    (my $self = (caller(0))[3]) =~ s/^main:://;

    my ($dev) = @_;

    if ($dev =~ /^\/dev\//) {
	$dev = substr ($dev, 5);
    }

    open (\*FILE, "/sys/block/$dev/dm/name") or die "$!\n";

    chomp (my $name = <FILE>);

    close (FILE);

    return ($name);
}

sub get_mpath_uuid ($)
{
    (my $self = (caller(0))[3]) =~ s/^main:://;

    my ($dev) = @_;

    if ($dev =~ /^\/dev\//) {
	$dev = substr ($dev, 5);
    }

    open (\*FILE, "/sys/block/$dev/dm/uuid") or die "$!\n";

    chomp (my $uuid = <FILE>);

    close (FILE);

    return ($name);
}

sub get_mpath_slaves ($)
{
    (my $self = (caller(0))[3]) =~ s/^main:://;

    my ($dev) = @_;

    if ($dev =~ /^\/dev\//) {
	$dev = substr ($dev, 5);
    }

    opendir (\*DIR, "/sys/block/$dev/slaves/") or die "$!\n";

    my @slaves = grep { !/^\./ } readdir (DIR);

    if ($slaves[0] =~ /^dm/) {
	@slaves = get_mpath_slaves ($slaves[0]);
    }
    else {
	@slaves = map { "/dev/$_" } @slaves;
    }

    closedir (DIR);

    return (@slaves);
}

sub get_registration_keys ($)
{
    (my $self = (caller(0))[3]) =~ s/^main:://;

    my ($dev) = @_;

    my $cmd = "sg_persist -n -i -k -d $dev";
    my $pid = open3 (\*IN, \*OUT, \*ERR, $cmd) or die "$!\n";

    waitpid ($pid, 0);

    die "[error]: $self\n" if ($?>>8);

    my @keys;

    while (<OUT>) {
    	chomp;

	if ($_ =~ s/^\s+0x//i) {
	    push (@keys, $_);
	}
    }

    close (IN);
    close (OUT);
    close (ERR);

    return (@keys);
}

sub get_reservation_key ($)
{
    (my $self = (caller(0))[3]) =~ s/^main:://;

    my ($dev) = @_;

    my $cmd = "sg_persist -n -i -r -d $dev";
    my $pid = open3 (\*IN, \*OUT, \*ERR, $cmd) or die "$!\n";

    waitpid ($pid, 0);

    die "[error]: $self\n" if ($?>>8);

    my $key;

    while (<OUT>) {
    	chomp;

	if ($_ =~ s/^\s+key=0x//i) {
	    $key = $_;
	    last;
	}
    }

    close (IN);
    close (OUT);
    close (ERR);

    return ($key);
}

sub get_options_stdin ()
{
    my $num = 0;

    while (<STDIN>)
    {
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

################################################################################

if (@ARGV > 0) {
    getopts ("ad:f:hk:n:o:qV") or die "$!\n";

    print_usage if (defined $opt_h);
    print_version if (defined $opt_V);
}
else {
    get_options_stdin ();
}

if (defined $opt_f) {
    open (LOG, ">$opt_f") or die "$!\n";
    open (STDOUT, ">&LOG");
    open (STDERR, ">&LOG");
}

if ((!defined $opt_n) && (!defined $opt_k)) {
    log_error ("No '-n' or '-k' flag specified.");
    exit (1);
}

if (defined $opt_k) {
    $key = $opt_k;
}
else {
    $key = get_key ($opt_n);
}

if (defined $opt_d) {
    @devices = split (/\s*,\s*/, $opt_d);
}
else {
    @devices = get_devices_clvm ();
}

if (!defined $opt_o) {
    $opt_o = "off";
}

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

if (defined $opt_f) {
    close (LOG);
}

#!/usr/bin/perl

use Getopt::Std;
use IPC::Open3;
use POSIX;

my $ME = $0;

END {
  defined fileno STDOUT or return;
  close STDOUT and return;
  warn "$ME: failed to close standard output: $!\n";
  $? ||= 1;
}

$_ = $0;
s/.*\///;
my $pname = $_;
my @device_list;

#BEGIN_VERSION_GENERATION
$RELEASE_VERSION="";
$REDHAT_COPYRIGHT="";
$BUILD_DATE="";
#END_VERSION_GENERATION

sub usage
{
    print "Usage\n";
    print "\n";
    print "$pname [options]\n";
    print "\n";
    print "Options:\n";
    print "  -n <node>		ip address or hostname of node to fence\n";
    print "  -h			usage\n";
    print "  -u			unfence\n";
    print "  -v			verbose\n";
    print "  -V			version\n";

    exit 0;
}

sub version
{
    print "$pname $RELEASE_VERSION $BUILD_DATE\n";
    print "$REDHAT_COPYRIGHT\n" if ($REDHAT_COPYRIGHT);
}

sub fail_usage
{
    ($msg) = @_;

    print STDERR $msg."\n" if $msg;
    print STDERR "Please use '-h' for usage.\n";

    exit 1;
}

sub check_sg_persist
{
    my ($in, $out, $err);
    my $cmd = "sg_persist -V";
    my $pid = open3($in, $out, $err, $cmd) or die "$!\n";

    waitpid($pid, 0);

    die "unable to execute sg_persist.\n" if ($?>>8);

    close ($in);
    close ($out);
    close ($err);
}

sub get_cluster_id
{
    my ($in, $out, $err);
    my $cmd = "cman_tool status";
    my $pid = open3($in, $out, $err, $cmd) or die "$!\n";

    waitpid($pid, 0);

    die "unable to execute cman_tool.\n" if ($?>>8);

    my $cluster_id;

    while (<$out>) {
	chomp;

	my ($name, $value) = split(/\s*:\s*/, $_);

	if ($name eq "Cluster Id") {
	    $cluster_id = $value;
	    last;
	}
    }

    close ($in);
    close ($out);
    close ($err);

    return $cluster_id;
}

sub get_node_id
{
    ($node) = @_;

    my ($in, $out, $err);
    my $cmd = "ccs_tool query /cluster/clusternodes/clusternode[\@name=\\\"$node\\\"]/\@nodeid";
    my $pid = open3($in, $out, $err, $cmd) or die "$!\n";

    waitpid($pid, 0);

    die "Unable to execute ccs_tool.\n" if ($?>>8);

    while (<$out>) {
        chomp;
        $node_id = $_;
    }

    close ($in);
    close ($out);
    close ($err);

    return $node_id;
}

sub get_host_name
{
    my ($in, $out, $err);
    my $cmd = "cman_tool status";
    my $pid = open3($in, $out, $err, $cmd) or die "$!\n";

    waitpid($pid, 0);

    die "unable to execute cman_tool.\n" if ($?>>8);

    my $host_name;

    while (<$out>) {
	chomp;

	my ($name, $value) = split(/\s*:\s*/, $_);

	if ($name eq "Node name") {
	    $host_name = $value;
	    last;
	}
    }

    close ($in);
    close ($out);
    close ($err);

    return $host_name;
}

sub get_node_name
{
    return $opt_n;
}

sub get_key
{
    ($node) = @_;

    my $cluster_id = get_cluster_id;
    my $node_id = get_node_id($node);

    if ($node_id == 0) {
	die "unable to determine nodeid for node '$node'\n";
    }

    my $key = sprintf "%.4x%.4x", $cluster_id, $node_id;

    return $key;
}

sub get_options_stdin
{
    my $opt;
    my $line = 0;

    while (defined($in = <>)) {

	$_ = $in;
	chomp;

	## strip leading and trailing whitespace
	##
	s/^\s*//;
	s/\s*$//;

	## skip comments
	##
	next if /^#/;

	$line += 1;
	$opt = $_;

	next unless $opt;

	($name, $value) = split(/\s*=\s*/, $opt);

	if ($name eq "")
	{
	    print STDERR "parse error: illegal name in option $line\n";
	    exit 2;
	}
	elsif ($name eq "agent")
	{
	    ## ignore this
	}
	elsif ($name eq "node")
	{
	    $opt_n = $value;
	}
	elsif ($name eq "nodename")
	{
	    $opt_n = $value;
	}
	elsif ($name eq "action")
	{
	    ## if "action=on", the we are performing an unfence operation.
	    ## any other value for "action" is ignored. the default is a
	    ## fence operation.
	    ##
	    if ($value eq "on") {
		$opt_u = $value;
	    }
	}
    }
}

sub get_scsi_devices
{
    my ($in, $out, $err);

    my $cmd = "vgs --config 'global { locking_type = 0 }'" .
              "    --noheadings --separator : -o vg_attr,pv_name 2> /dev/null";

    my $pid = open3($in, $out, $err, $cmd) or die "$!\n";

    waitpid($pid, 0);

    die "unable to execute vgs.\n" if ($?>>8);

    while (<$out>) {
	chomp;

	my ($attrs, $dev) = split(/:/, $_);

	if ($attrs =~ /.*c$/) {
	    $dev =~ s/\(.*\)//;
	    push(@device_list, $dev);
	}
    }

    close ($in);
    close ($out);
    close ($err);
}

sub create_registration
{
    my ($key, $dev) = @_;

    my ($in, $out, $err);
    my $cmd = "sg_persist -n -d $dev -o -I -S $key";
    my $pid = open3($in, $out, $err, $cmd) or die "$!\n";

    waitpid($pid, 0);

    die "unable to create registration.\n" if ($?>>8);

    close ($in);
    close ($out);
    close ($err);
}

sub create_reservation
{
    my ($key, $dev) = @_;

    my ($in, $out, $err);
    my $cmd = "sg_persist -n -d $dev -o -R -K $key -T 5";
    my $pid = open3($in, $out, $err, $cmd) or die "$!\n";

    waitpid($pid, 0);

    die "unable to create reservation.\n" if ($?>>8);

    close ($in);
    close ($out);
    close ($err);
}

sub fence_node
{
    my $host_name = get_host_name;
    my $host_key = get_key($host_name);

    my $node_name = get_node_name;
    my $node_key = get_key($node_name);

    my ($in, $out, $err);

    foreach $dev (@device_list)
    {
	## check that the key we are attempting to remove
	## is actually registered with the device. if the key is not
	## registered, there is nothing to do for this device.
	##
	system ("sg_persist -n -d $dev -i -k | grep -qiE \"^[[:space:]]*0x$key\"");

	if (($?>>8) != 0) {
	    next;
	}

	if ($host_key eq $node_key) {
	    ## this sg_persist command is for the case where you attempt to
	    ## fence yourself (ie. the local node is the same at the node to
	    ## be fence). this will not work if the node is the reservation
	    ## holder, since you can't unregister while holding the reservation.
	    ##
	    my $cmd = "sg_persist -n -d $dev -o -G -K $host_key -S 0";
	}
	else {
	    ## this sg_persist command will remove the registration for $host_key.
	    ## the local node will also become the reservation holder, regardless
	    ## of which node was holding the reservation prior to the fence operation.
	    ##
	    my $cmd = "sg_persist -n -d $dev -o -A -K $host_key -S $node_key -T 5";
	}

	my $pid = open3($in, $out, $err, $cmd) or die "$!\n";

	waitpid($pid, 0);

	die "unable to execute sg_persist.\n" if ($?>>8);

	close ($in);
	close ($out);
	close ($err);
    }
}

sub unfence_node
{
    my $host_name = get_host_name;
    my $host_key = get_key($host_name);

    foreach $dev (@device_list)
    {
	create_registration ($host_key, $dev);

	## check to see if a reservation already exists.
	## if no reservation exists, this node/key will become
	## the reservation holder.
	##
	system ("sg_persist -n -d $dev -i -r | grep -qiE \"^[[:space:]]*Key=0x\"");

	if (($?>>8) != 0) {
	    create_reservation ($host_key, $dev);
	}
    }
}

if (@ARGV > 0) {

    getopts("hn:uvV") || fail_usage;

    usage if defined $opt_h;
    version if defined $opt_V;

    if (!defined $opt_u) {
	fail_usage "No '-n' flag specified." unless defined $opt_n;
    }

} else {

    get_options_stdin();

}

## get a list of scsi devices. this call will build a list of devices
## (device_list) by querying clvm for a list of devices that exist in
## volume groups that have the cluster bit set.
##
get_scsi_devices;

if ($opt_u) {
    unfence_node;
} else {
    fence_node;
}

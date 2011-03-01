#!/usr/bin/perl

use POSIX;

################################################################################

my $dev_file = "/var/run/cluster/fence_scsi.dev";
my $key_file = "/var/run/cluster/fence_scsi.key";

################################################################################

sub log_debug ($)
{
    my $time = strftime ("%b %e %T", localtime);
    my $msg = shift;

    print STDOUT "$time [$0] debug: $msg\n" if ($verbose);

    return;
}

sub log_error ($)
{
    my $time = strftime ("%b %e %T", localtime);
    my $msg = shift;

    print STDERR "$time [$0] error: $msg\n";

    return;
}

sub do_reset ($)
{
    my $dev = shift;

    my $cmd = "sg_turs $dev";
    my @out = qx { $cmd 2> /dev/null };

    return;
}

sub get_registration_keys ($)
{
    my $dev = shift;
    my @keys = ();

    do_reset ($dev);

    my $cmd = "sg_persist -n -i -k -d $dev";
    my @out = qx { $cmd 2> /dev/null };

    if ($?>>8 != 0) {
	log_error ("$cmd");
	exit (0);
    }

    foreach (@out) {
	chomp;
	if (s/^\s+0x//i) {
	    push (@keys, $_);
	}
    }

    return (@keys);
}

sub get_reservation_keys ($)
{
    my $dev = shift;
    my @keys = ();

    do_reset ($dev);

    my $cmd = "sg_persist -n -i -r -d $dev";
    my @out = qx { $cmd 2> /dev/null };

    if ($?>>8 != 0) {
	log_error ("$cmd");
	exit (0);
    }

    foreach (@out) {
	chomp;
	if (s/^\s+key=0x//i) {
	    push (@keys, $_);
	}
    }

    return (@keys);
}

sub get_verbose ()
{
    open (\*FILE, "</etc/sysconfig/watchdog") or return;
    chomp (my @opt = <FILE>);
    close (FILE);

    foreach (@opt) {
	next if (/^#/);
	next unless ($_);

	if (/^verbose=yes$/i) {
	    return (1);
	}
    }

    return (0);
}

sub key_read ()
{
    open (\*FILE, "<$key_file") or exit (0);
    chomp (my $key = <FILE>);
    close (FILE);

    return ($key);
}

sub dev_read ()
{
    open (\*FILE, "<$dev_file") or exit (0);
    chomp (my @dev = <FILE>);
    close (FILE);

    return (@dev);
}

################################################################################

if ($ARGV[0] =~ /^repair$/i) {
    exit ($ARGV[1]);
}

if (-e "/etc/sysconfig/watchdog") {
    $verbose = get_verbose ();
}

if (! -e $dev_file) {
    log_debug ("$dev_file does not exit");
    exit (0);
} elsif (-z $dev_file) {
    log_debug ("$dev_file is empty");
    exit (0);
}

if (! -e $key_file) {
    log_debug ("$key_file does not exist");
    exit (0);
} elsif (-z $key_file) {
    log_debug ("$key_file is empty");
    exit (0);
}

my $key = key_read ();
my @dev = dev_read ();

foreach (@dev) {
    my @keys = grep { /^$key$/i } get_registration_keys ($_);

    if (scalar (@keys) != 0) {
	log_debug ("key $key registered with device $_");
	exit (0);
    } else {
	log_debug ("key $key not registered with device $_");
    }
}

log_debug ("key $key not registered with any devices");

exit (2);

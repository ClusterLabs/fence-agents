Fence agents
============
Fence agents were developed as device "drivers" which are able to prevent computers from destroying data on shared storage. Their aim is to isolate a corrupted computer, using one of three methods:

  * Power - A computer that is switched off cannot corrupt data, but it is important to not do a "soft-reboot" as we won't know if this is possible. This also works for virtual machines when the fence device is a hypervisor.
  * Network - Switches can prevent routing to a given computer, so even if a computer is powered on it won't be able to harm the data.
  * Configuration - Fibre-channel switches or SCSI devices allow us to limit who can write to managed disks.

Fence agents do not use configuration files, as configuration management is outside of their scope. All of the configuration has to be specified either as command-line arguments or lines of standard input (see the complete list for more info).

Because many fence agents are quite similar to each other, a fencing library (in Python) was developed. Please use it for further development. Creating or modifying a new fence agent should be quite simple using this library.

# fence-agents
Fence agents
 Fence agents were developed as "drivers" for devices that are able to prevent computers of destroying data on shared storage. Their target is to isolate corrupted computer, there are three main ways:

  * electric power - computer that is switched off can not corrupt data but it is important to not perform so called "soft- reboot" where applications are closed correctly as we do not know if this is possible. Similarly it works also for virtual machines when fence device is a hypervisor.
  * network - network switches can forbid routing from selected computer, so even if computer is running it is not able to work with data
  * data - Fibre-channel switches or SCSI devices allows us to limit who can write to managed disks 

Fence agents do not use configuration files as configuration management is outside their scope. All of the arguments have to be specified either as command-line arguments or lines on standard input (take a look at complete list). Because fence agents are quite similar, fencing library (in Python) was developed and we will assume that you will use it for further developing. Creating or modifying a new fence agent should be quite simple. 

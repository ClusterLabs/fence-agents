# Two node cross-link fence agent

The problem that this fence agents tries to solve is the following:

Given a two-node cluster with a direct crosslink ethernet cable
between the two nodes (in addition to the normal networking setup), we want to
be able to maintain quorum on node (A) when node (B) lost power.
The loss of power on node (B) in this case implies its BMC/IPMI is also
not available which would be normally used in fencing in this case.

Note: An external PDU would be preferrable and would solve this
situation more elegantly. The assumption here is that something
like that won't be available in this environment.

This works by creating a stonith level composed of a BMC/IPMI
fencing at level 1 and then the fence_crosslink agent at level 2.
 
In case node (A) has lost power, then node (B) will do the following:
1. Try to fence node (B) via IPMI, which will fail since the node has no
power and the BMC is unavailable
2. Check via fence_crosslink the cross-cable interconnect. If the cross cable
IP is not reachable, then we know for "sure" (this is a potentially broad
assumption) that the node is really down and fence_crosslink tells pacemaker
that the fencing was successful, so pacemaker can work with that new
information.
 
Here are some example configuration commands:
~~~
pcs stonith create crosslink-controller-1 fence_crosslink crosscableip=1.1.1.2 pcmk_host_list=controller-1 pcmk_reboot_action=off
pcs stonith create crosslink-controller-0 fence_crosslink crosscableip=1.1.1.1 pcmk_host_list=controller-0 pcmk_reboot_action=off
# We make sure the stonith resource do not run on the same node as the fencing target
pcs constraint location crosslink-controller-1 avoids controller-1
pcs constraint location crosslink-controller-0 avoids controller-0
pcs stonith level add 2 controller-0 crosslink-controller-0
pcs stonith level add 2 controller-1 crosslink-controller-1
~~~

Testing done:
- Simulate power outage by turning off the controller-1 VM and its IPMI interface and leaving the crosslink intact.

  * Expected Outcome:
  We should retain quorum on controller-0 and all services should be running on controller-0. No UNCLEAN resources should be observed on controller-0.
  * Actual Outcome:
  Matched the expected outcome.

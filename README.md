## Background

A fat-tree is built for data centers (and supercomputers), where the “leaves” are servers doing compute work.
If one server loses its link, the job scheduler just moves the work to another healthy CPU/GPU server.

The Root is at the top: the core switches.


Bandwidth - how much data can flow through a link \ network.

## Approach

- k pods, each with two layers of k/2 switches.
- Each edge switch has k/2 hosts.
- (k/2)^2 core switches, with one port per pod. Each pod has k/2 aggregation switches, and each has k/2 uplinks, so every pod sends out (k/2) × (k/2) = k^2/4 links toward the core.
- k^3/4 hosts in total. There are k pods and k^2/4 hosts per pod, so the total is k × k²/4
- Each pod has k/2 edge + k/2 aggregation = k switches.
All k pods have k × k = k^2 switches.
Add the core switches: K^2/4
Total: k^2 + k^2/4 = 5k^2/4.






## Instructions for running the code



## Results
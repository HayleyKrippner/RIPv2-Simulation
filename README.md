# RIPv2-Simulation

This is a implementation of the Routing Information Protcol version 2.
Split-horizon routing with poison reverse is used.

Open seven different terminals.
Run manager.py in each, providing the command line argument of the router file. This will start a router in each terminal.
Observe the routing tables as the network converges.

If you close a terminal,  the network will recoverge.
If you then revive a router by opening a terminal and providing the revelant router file as a command line arguement, the network will converge back to its previous state.


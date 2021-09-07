# ----------------------------------- COSC364 Assignment 1 --------------------------------

# This is the Router class. It handles the following:
#   1.  initializing a router, including an outputs dictionary and its routing table,
#   2.  opening input sockets and listening for packets,
#   3.  starting the router's tasks,
#   4.  creating and sending a response packet,
#   5.  processing and validating an incoming packet,
#   6.  display a routing table of the router,
#   7.  handling when a timeout occurs
#   8.  starting garbage collection,

# Authors: Hayley Krippner, Sarah Bealing

import socket
import select
import math
from timer import Timer
import asyncio

IP_ADDRESS = "127.0.0.1"
BUFFER = 504  # Max RIP packet size is 4 byte header + (25 RIP entries * 20 bytes each)


class Router:
    """
    Router class

    Contains the functionality used by any router.
    """

    def __init__(self, router_id, input_ports, outputs, timer_values):
        """
        Router initialisation

        INPUTS: router_id, an int which is the the router id
                input_ports, ints which are the ports that the router will listen for incoming
                packets on
                outputs, a list of tuples [(port, metric, peer_router_id), ...] associated with the
                router's neighbours' info
                timer_values, a list of the values corresponding to the periodic update, timeout and
                garbage collection duration
        OUTPUTS: N/A
        """

        self.router_id = router_id
        self.input_ports = input_ports
        self.active_sockets = {}  # sockets router is listening on

        self.outputs = {}
        # dictionary containing
        # peer_router_id: {
        #     "port": router's peer_router_id's port,
        #     "metric": metric from router to the router with peer_router_id
        #
        # }

        self.initialise_outputs_dict(outputs)
        self.periodic_update_time = timer_values[0]
        self.timeout = timer_values[1]
        self.garbage_collection_time = timer_values[2]

        self.tasks = set()  # set of asynchronous tasks to get through

        self.routing_table = {}
        self.initialise_routing_table()

        print(f"[Router {self.router_id}] Created Router object with router_id: {self.router_id}," +
              f" input_ports: {self.input_ports}, initial routing table: {self.routing_table}," +
              f" periodic_update_time: {self.periodic_update_time}, timeout: {self.timeout}," +
              f" garbage_collection_time: {self.garbage_collection_time}")

        self.open_input_sockets()

        self.periodic_update_timer = Timer(self.periodic_update_time, self, None, True)
        # True since is periodic update timer (not garbage or route timeout)

        new_timer = asyncio.create_task(
            self.periodic_update_timer.start())  # Asynchronously start the timer
        self.tasks.add(new_timer)

    def initialise_outputs_dict(self, outputs):
        """
        Converts outputs list from config file to dictionary where we can find metric/port for a
        given peer_router_id

        INPUTS: outputs, a list of tuples [(port, metric, peer_router_id), ...]
        OUTPUTS: N/A
        """

        for output_tuple in outputs:
            port = output_tuple[0]
            metric = output_tuple[1]
            peer_router_id = output_tuple[2]

            self.outputs.update({
                peer_router_id: {
                    "port": port,
                    "metric": metric

                }
            })

    def initialise_routing_table(self):
        """
        Initialises the routing table. Each routing table entry contains the router id, 
        the outgoing port to get to the router, the associated next hop router, metric and Timer.

        Example of routing table entry:
            2: {
            "port_number": 5000,
            "next_router": 2,
            "metric": 6,
            "route_changed": True
            "timer": Timer
            }

        INPUTS: N/A
        OUTPUTS: N/A
        """

        self.routing_table.update({
            self.router_id: {
                "port_number": "",
                "next_router": "",
                "metric": 0,
                "route_changed": True,  # Always True for myself, so I don't delete myself
                "timer": ""
            }
        })

        print(f"[Router {self.router_id}] Initialised routing table. Routing table is now:")
        print(self.display_routing_table())

    async def run_tasks(self):
        """
        Asynchronously runs tasks: timer countdowns, listening for packets.

        INPUTS: N/A
        OUTPUTS: N/A
        """

        running = True

        while running:
            done, pending = await asyncio.wait(self.tasks, return_when=asyncio.FIRST_COMPLETED)
            running = len(
                pending) > 0
            # Will always have listen_for_packets loop pending, so we're always listening for packets

    def open_input_sockets(self):
        """
        Sets up a new UDP socket for each of the router's input ports.
        A listening task is added to the asynchronous tasks.

        INPUTS: N/A
        OUTPUTS: N/A
        """

        for input_port in self.input_ports:
            # creates a UDP socket
            udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

            # binds the socket to the input port
            udp_socket.bind((IP_ADDRESS, input_port))

            # adds the socket to the list of sockets that the router is listening on
            self.active_sockets.update({input_port: udp_socket})

        print(f"[Router {self.router_id}] Populated active_sockets for router {self.router_id} " +
              f"with values: {self.active_sockets}")

        listen = asyncio.create_task(self.listen_for_packets())
        self.tasks.add(listen)

    async def listen_for_packets(self):
        """
        Asynchronously listens for incoming RIP packets on its specified sockets.
        If a packet is received, it is passed to the handle_incoming_packet function
        and another listening task is added to the asynchronous tasks.

        INPUTS: N/A
        OUTPUTS: N/A
        """

        socket_list = list(self.active_sockets.values())

        while True:

            # Allows for listening on input ports asynchronously
            # By making this function async so it can be handled as an asyncio task
            await asyncio.sleep(0.01)

            try:
                # The following line is blocking for 0.1 seconds
                incoming_packets, _, _ = select.select(socket_list, [], [], 0.1)
            except ValueError:
                print(
                    f"[Router {self.router_id}] ERROR: an error occurred when a packet was "
                    f"attempted to be received")
                break

            if len(incoming_packets) > 0:  # packet(s) have been received
                print(f"[Router {self.router_id}] An incoming packet has been received: {incoming_packets}")
                try:
                    print(f"[Router {self.router_id}] Trying to receive from buffer")
                    incoming_packet, sender_address = incoming_packets[0].recvfrom(BUFFER)
                    self.handle_incoming_packet(incoming_packet)
                except OSError:
                    print(
                        f"[Router {self.router_id}] ERROR: The incoming packet exceeded the "
                        f"buffer size of {BUFFER} bytes.")

                listen = asyncio.create_task(self.listen_for_packets())
                self.tasks.add(listen)

    def timeout_occurred(self, destination, is_periodic_update):
        """
        Called by the Timer object when an entry in the routing table has timed out,
        or a periodic update is due.

        INPUTS: destination, the router destination for the entry we are timing
                             is_periodic_update, boolean specifying whether the Timer is a
                             periodic update or not
        OUTPUTS: N/A
        """

        if is_periodic_update:
            self.send_response_packets()

            # reset periodic update timer
            self.periodic_update_timer.reset(self.periodic_update_time)
            new_timer = asyncio.create_task(
                self.periodic_update_timer.start())  # Asynchronously start the timer
            self.tasks.add(new_timer)

            return

        print(f"[Router {self.router_id}] Route has timed out for destination: {destination}")

        # If we haven't haven't started garbage collection, we start it now

        try:
            if self.routing_table[destination]["route_changed"] == True:
                self.start_garbage_collection(destination)
            else:  # Garbage collection has timed out and the destination is considered unreachable
                self.routing_table.pop(destination)
                print(
                    f"[Router {self.router_id}] Table entry for destination {destination} has been removed.\n" +
                    f"Routing table is now \n{self.display_routing_table()}\n")

                print(f"[Router {self.router_id}] Deleted entry for destination {destination}")
        except KeyError:
            print(f"[Router {self.router_id}] Destination {destination} has already been removed.")

    def start_garbage_collection(self, dst_router_id):
        """
        Starts the garbage collection process.

        The metric is set to 16 to indicate that the route is not useful and
        the router_change flag is set to False since the router has not heard
        from the router in the last 18 seconds. The Router's timer is reset to the
        garbage collection time of 12 seconds and added as a task to the async tasks list.

        Called by timeout_occurred (routing table entry timeout i.e. have not heard from router
        and are considering it as unreachable) and process_incoming_packet
        (when received message that route is infinity) functions.

        INPUTS: dst_router_id, the router id of the router destination for the entry we are timing
        OUTPUTS: N/A
        """

        print(f"[Router {self.router_id}] Starting deletion process for route to destination {dst_router_id}")

        self.routing_table[dst_router_id]["metric"] = 16
        self.routing_table[dst_router_id]["route_changed"] = False
        # has not recently received packet saying route is valid i.e. in the past 18 seconds

        route_timer = self.routing_table[dst_router_id]["timer"]
        route_timer.reset(self.garbage_collection_time)
        new_timer_task = asyncio.create_task(
            route_timer.start())  # Asynchronously start the timer
        self.tasks.add(new_timer_task)

        print(
            f"[Router {self.router_id}] Routing table entry changed for {dst_router_id}\n" +
            f"Routing table is now \n{self.display_routing_table()}\n")

        self.send_response_packets()

    def create_response(self, receiving_router):
        """
        Creates an outgoing packet using the same format as the incoming packet's format.

        Response packet will be in the following format, e.g. where there are two entries:
                [command, version, 0, sender_router_id,
                                           0, afi, 0, 0,
                                           0, 0, 0, dest_router_id_1,
                                           0, 0, 0, 0,
                                           0, 0, 0, 0,
                                           0, 0, 0, metric_1,
                                           0, afi, 0, 0,
                                           0, 0, 0, dest_router_id_2,
                                           0, 0, 0, 0,
                                           0, 0, 0, 0,
                                           0, 0, 0, metric_2]

        The command is always 2 as it is response, version is always 2,
        sender_router_id is the id of the router sending the packet,
        dest_router_id is the id of the router where the packet is going to,
        metric is the cost to reach to destination router from the current router
        and afi is the address family identifier which is always 2 by default
        which corresponds to AF_INET.

        Note that the response packet is in bytes.

        INPUTS: receiving_router, the id of the router that will send the response packet.
        OUTPUTS: response_packet, the updated response packet that will be sent to the
                                  router's neighbouring routers. It is in the form of a bytearray.
        """

        command = 2
        version = 2
        sender_router_id = self.router_id
        afi = 2

        response_packet = [command, version, 0, sender_router_id]

        for dest_router_id, info in self.routing_table.items():
            metric = info.get('metric')

            # Split horizon with poison reverse
            if info.get("next_router") == receiving_router:
                metric = 16

            entry = [
                0, afi, 0, 0,
                0, 0, 0, dest_router_id,
                0, 0, 0, 0,
                0, 0, 0, 0,
                0, 0, 0, metric,
            ]
            response_packet += entry

        response_packet = bytearray(response_packet)
        return response_packet

    def send_response_packets(self):
        """
        Determines which output ports the response packets need to be sent via
        in order the to send it to the router's direct neighbours.
        The tailored response packet is sent to all of a router's neighbours.

        INPUTS: N/A
        OUTPUTS: N/A
        """

        sending_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

        # loop through output ports of the router and send the packet via each one
        for output in self.outputs:
            output_port_num = self.outputs[output]["port"]  # needed for sendto function below
            neighbour_id = output

            response_packet = self.create_response(neighbour_id)

            sending_socket.sendto(response_packet, (IP_ADDRESS, output_port_num))
            print(
                f"[Router {self.router_id}] The response packet has been sent via the output port " +
                f"{output_port_num} to neighbour with id of {neighbour_id}")

    def handle_incoming_packet(self, packet):
        """
        Handles incoming packets by checking if it is a valid.
        If it is valid, then it will be processed.
        Calls functions to validate and process the packet.

        INPUTS: packet, the incoming packet that needs to be validated.
        OUTPUTS: N/A
        """

        valid_packet = self.validate_incoming_packet(packet)
        if valid_packet:
            sender_router_id, packet_entries = valid_packet
            self.process_incoming_packet(sender_router_id, packet_entries)

    def validate_incoming_packet(self, packet):
        """
        Checks incoming packets for correctness. Takes packet as a list of bytes.

        INPUTS: packet, the incoming packet that needs to be validated.
        OUTPUTS: False if the packet is invalid, otherwise sender_router_id,
                 the id of the router that sent the packet,
                 and packet_entries, the individual entries within the received packet,
                 are returned to be used in packet processing.
        """

        print(f"[Router {self.router_id}] Checking incoming packet...")
        command = packet[0]
        version = packet[1]
        sender_router_id = (packet[2] << 8) + packet[3]

        exp_id_min = 1
        exp_id_max = 64000

        if command != 2:
            print(
                f"[Router {self.router_id}] ERROR: Command field of incoming packet is "
                f"not 2 (response). Instead it is {command}. Dropping packet.")
            return False
        if version != 2:
            print(
                f"[Router {self.router_id}] ERROR: Version field of incoming packet is not 2. "
                + f"Instead it is {version}. Dropping packet.")
            return False
        if sender_router_id < exp_id_min or sender_router_id > exp_id_max:
            print(
                f"[Router {self.router_id}] ERROR: router_id of sender is not within the required "
                f"range of 1 to 64000. Dropping packet.")
            return False

        num_entries = math.ceil(len(packet[4:]) / 20)
        packet_entries = []

        # Loop through entries in the packet and validate each entry
        for i in range(num_entries):
            entry_start = 4 + (i * 20)  # Packet index of the first byte of this entry
            packet_entry = self.validate_rip_entry(packet, entry_start)
            if not packet_entry:
                return False
            else:
                packet_entries.append(packet_entry)

        print(f"[Router {self.router_id}] Incoming packet passed all checks")
        return sender_router_id, packet_entries

    def validate_rip_entry(self, packet, start_index):
        """
        Checks the correctness of an RIP entry in an incoming packet.
        If valid entry, returns tuple of (dst_router_id, metric)
        to be used by packet processing. If not valid entry, returns False.

        INPUTS: packet, the incoming packet that needs to be validated.
                start_index, the start index of the entry in terms of the packet.
        OUTPUTS: If valid entry, returns tuple of (dst_router_id, metric)
                 to be used by packet processing.
                 dst_router_id is an int of the id of the destination router
                 metric is an int that is the cost to get from the current router to the
                 destination router.
                 If not valid entry, returns False.
        """

        try:
            # First 2 bytes should be 2 (Address family AF_INET)
            afi = (packet[start_index] << 8) + packet[start_index + 1]
            if afi != 2:
                print(
                    f"[Router {self.router_id}] ERROR: Address family identifier is not 2 (AF_INET). " +
                    f"Instead it is {afi}. Dropping packet.")
                return False

            # Second 2 bytes should be 0 (must be zero field)
            zero_field_2_bytes = (packet[start_index + 2] << 8) + packet[start_index + 3]
            if zero_field_2_bytes != 0:
                print(
                    f"[Router {self.router_id}] ERROR: Must be zero field (2 bytes) is not 0. " +
                    f"Instead it is {zero_field_2_bytes}. Dropping packet.")
                return False

            # Next 4 bytes is destination router-id (between 1 and 64000)
            dst_router_id = (packet[start_index + 4] << 24) + (
                    packet[start_index + 5] << 16) + (packet[start_index + 6] << 8) + packet[start_index + 7]
            if dst_router_id < 1 or dst_router_id > 64000:
                print(
                    f"[Router {self.router_id}] ERROR: router_id of destination is not within "
                    f"the required range of 1 to 64000. Dropping packet.")
                return False

            # Next 8 bytes are zero
            all_zero_8_bytes = all(byte == 0 for byte in packet[start_index + 8:start_index + 16])
            if not all_zero_8_bytes:
                print(f"[Router {self.router_id}] ERROR: Must be zero field (8 bytes) is not 0. "
                      f"Dropping packet.")
                return False

            # Next 4 bytes is metric (between 1 and 16, 16 for infinity)
            metric = (packet[start_index + 16] << 24) + (
                    packet[start_index + 17] << 16) + (packet[start_index + 18] << 8) + packet[start_index + 19]
            if metric < 0 or metric > 16:
                print(
                    f"[Router {self.router_id}] ERROR: metric of destination is not within the "
                    f"required range of 0 to 16. Dropping packet.")
                return False

            return (dst_router_id, metric)

        except IndexError:
            print(f"[Router {self.router_id}] ERROR: RIP entry was less that 20 bytes. "
                  f"Dropping packet.")
            return False

    def process_incoming_packet(self, sender_router_id, packet_entries):
        """
        Processes an incoming RIP response packet.

        If the destination router id is the current router's id, then the current router
        knows that the sending router is alive and reachable.

        If the destination is not in the Router's table, then an entry is created and added.

        If the destination is in the Router's table and the next hop address is the same as
        existing route, the new new route cost is adopted, provided not infinity. The same
        next-hop is the best route known and the route is replace when a better one is
        discovered. If the metric is infinity, garbage collection is started.

        If the destination is in the Router's table and another router is advertising it
        to this Router, then the metrics are compared and the next hop address resulting
        from the lower metric is adopted. The routing table entry is updated.

        Note that in all cases except when garbage collection is started, the route_changed
        flag is True as we know the router is alive and the timeout timer is reset.

        INPUTS: sender_router_id, the id of the router which sent the packet
                packet_entries, a list of tuples in the form of (dst_router_id, metric)
        OUTPUTS: N/A
        """

        num_entries = len(packet_entries)
        print(
            f"[Router {self.router_id}] Processing packet from Router {sender_router_id} "
            f"with {num_entries}  entries: {packet_entries}")

        for entry in packet_entries:
            print(f"[Router {self.router_id}] Processing entry: {entry}")
            dst_router_id = entry[0]

            # Reset direct link to sender_router_id
            if dst_router_id == self.router_id:
                print(
                    f"[Router {self.router_id}] Resetting routing table entry for neighbour " +
                    f"destination {sender_router_id}")
                self.routing_table[sender_router_id][
                    "route_changed"] = True  # just heard directly from neighbour i.e. know is alive
                route_timer = self.routing_table[sender_router_id]["timer"]
                route_timer.reset(self.timeout)
                continue

            advertised_metric = entry[1]
            # Metric to destination is sum of advertised metric and metric of link to sender
            metric = advertised_metric + self.outputs[sender_router_id]["metric"]

            # New destination
            if dst_router_id not in self.routing_table:
                if metric < 16:  # valid route to dest
                    print(
                        f"[Router {self.router_id}] Adding new destination {dst_router_id} "
                        f"to routing table with metric {metric}")
                    next_router_port = self.outputs[sender_router_id]["port"]
                    self.routing_table.update({
                        dst_router_id: {
                            "port_number": next_router_port,
                            "next_router": sender_router_id,
                            "metric": metric,
                            "route_changed": True,
                            "timer": Timer(self.timeout, self, dst_router_id)
                        }
                    })
                    print(
                        f"[Router {self.router_id}] Added entry for destination {dst_router_id}. " +
                        f"Routing table is now \n{self.display_routing_table()}\n")
                    # Asynchronously start the timer
                    new_timer = asyncio.create_task(
                        self.routing_table[dst_router_id]["timer"].start())

                    self.tasks.add(new_timer)

            # Existing destination
            else:
                print(f"[Router {self.router_id}] Updating routing table entry for "
                      f"destination {dst_router_id}")

                # Next hop address is same as existing route
                # Must adopt new route cost for existing route, regardless if larger than
                # current val
                if self.routing_table[dst_router_id]["next_router"] == sender_router_id:
                    if metric < 16:
                        self.routing_table[dst_router_id]["metric"] = metric
                        self.routing_table[dst_router_id]["route_changed"] = True
                        route_timer = self.routing_table[dst_router_id]["timer"]
                        route_timer.reset(self.timeout)
                        print(
                            f"[Router {self.router_id}] Updated entry for destination "
                            f"{dst_router_id}. \nRouting table is now \n{self.display_routing_table()}\n")

                    # Existing route has changed to metric infinity
                    # Start garbage collection
                    else:
                        self.start_garbage_collection(dst_router_id)

                # New next hop address
                # Existing dest but another router is advertising it to this Router
                else:
                    print(f"[Router {self.router_id}] Comparing new route for "
                          f"destination {dst_router_id}")
                    if metric < self.routing_table[dst_router_id]["metric"]:
                        print(
                            f"[Router {self.router_id}] New metric of {metric} is better "
                            f"than {self.routing_table[dst_router_id]['metric']}. "
                            f"Updating next hop address for destination {dst_router_id}")
                        self.routing_table[dst_router_id]["port_number"] = self.routing_table[sender_router_id][
                            "port_number"]
                        self.routing_table[dst_router_id]["next_router"] = sender_router_id
                        self.routing_table[dst_router_id]["metric"] = metric
                        self.routing_table[dst_router_id]["route_changed"] = True
                        route_timer = self.routing_table[dst_router_id]["timer"]
                        route_timer.reset(self.timeout)
                        print(
                            f"[Router {self.router_id}] Changing table entry for destination "
                            f"{dst_router_id}. \nRouting table is now \n{self.display_routing_table()}\n")
                    else:
                        print(f"[Router {self.router_id}] New route to {dst_router_id} with "
                              f"metric {metric} is not better than current route with" +
                              f" metric {self.routing_table[dst_router_id]['metric']}.")

    def display_routing_table(self):
        """
        Creates a visual representation of a routing table for the Router.

        INPUTS: N/A
        OUTPUTS: table, the visual representation of a routing table of the given Router.
        """

        table = ""
        table_heading = "+-----------------------------------------------------------------------+\n" \
                        f"|                                Router ID: {self.router_id}                           |\n" \
                        "+-----------------------------------------------------------------------+\n" \
                        "| Neighbour Destination |  Metric  |   Next Router  | Route Change Flag |\n"

        table_body = ""

        for key, value in self.routing_table.items():
            table_body += "+-----------------------------------------------------------------------+\n"
            table_body += f"|          {key}            |    {value['metric']}    |         {value['next_router']}   " \
                          f"   |           {value['route_changed']}   |\n"
        table = table_heading + table_body + "+---------------------------------------------------------------------" \
                                             "--+\n"
        return table

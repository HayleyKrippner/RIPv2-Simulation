# ----------------------------------- COSC364 Assignment 1 --------------------------------
# This is the manager. It does the following:
#   1. parses each configuration file's data
#   2. creates a Router

# Authors: Hayley Krippner, Sarah Bealing

import sys
from router import Router
import asyncio

# Global Constants
PERIOD_UPDATE = 3  # seconds
TIMEOUT = 18  # seconds
GARBAGE_COLLECTION = 12  # seconds
EXPECTED_LINES = 4  # number of expected lines in configuration file

TASKS = set()  # Set of async tasks manager is handling for Router


# ------------------------------------ process config file ---------------------------------
def start_manager():
    """
    This function takes the second command line argument as the config file.
    It ensures that only this argument is present.

    INPUTS: N/A
    OUTPUTS: N/A
    """

    if len(sys.argv) > 2:
        print("More than 2 arguments have been provided. Please only provide manager.py and "
              "the config file as arguments.")
        exit_programme()

    else:
        path_to_starter_file = sys.argv[1]
        print("The program is starting...")
        process_file(path_to_starter_file)
        print("Parsing process is complete")


def process_file(filename):
    """
    This function opens the file, gets its contents and closes it before calling the parse_file
    function.

    INPUTS: filename, the filename of the text file containing the configuration information
                      for the given router
    OUTPUTS: N/A
    """

    router_file = ""
    try:
        router_file = open(filename, "r")
    except FileNotFoundError:
        print("ERROR: file not found!")
        exit_programme()

    print('The file "{0}" has been opened'.format(filename))
    lines = [line.strip("\n") for line in router_file if line != "\n"]

    # removes lines starting with '#' i.e. lines with comments
    lines_excluding_comments = [line for line in lines if line[0] != '#']
    router_file.close()
    open_router(lines_excluding_comments, filename)


def open_router(file_content, filename):
    """
    This function takes the configuration file, parses its contents, creates a new Router
    and starts its tasks.

        Router tasks:
        1) A global periodic update timer per Router
        2) route timeout for each entry in a Router's routing table
           Initially router timeout counting down to 0, then is the garbage collection time,
           counting down to 0 seconds
        3) listening for packets,one task for each Router. Once completed, it repeats
           indefinitely (until Router dies)

    INPUTS: file_content, the list of the lines in the configuration file which are the router
                          id line, the inputs line,
                          the outputs line and the timer values line.
            filename, the filename of the text file containing the configuration information for
                      the given router
    OUTPUTS: N/A
    """

    print("Beginning file content parsing process...")

    total_lines = len(file_content)
    if total_lines < EXPECTED_LINES:
        print("ERROR: The configuration file {0} has {1} line(s) and the expected number of "
              "lines is {2}".format(filename, total_lines, EXPECTED_LINES))
        exit_programme()
    else:
        # file contains expected number of lines

        exp_id_min = 1
        exp_id_max = 64000
        exp_port_min = 1024
        exp_port_max = 64000
        exp_metric_min = 1
        exp_metric_max = 16

        router_line = file_content[0]
        inputs_line = file_content[1]
        outputs_line = file_content[2]
        timer_line = file_content[3]

        router_id = ""
        try:
            router_id = parse_router_id(router_line, exp_id_min, exp_id_max)
        except TypeError:
            print("ERROR: Line 1 of configuration file has a syntax error. It must conform to the "
                  "format of 'router-id ID'.")
            exit_programme()

        inputs = parse_inputs(inputs_line, router_id, exp_port_min, exp_port_max)
        outputs = parse_outputs(outputs_line, inputs, router_id, exp_port_min, exp_port_max,
                                exp_metric_min, exp_metric_max, exp_id_min, exp_id_max)
        timer_vals = parse_timers(timer_line)

        router = Router(router_id, inputs, outputs, timer_vals)
        new_router_tasks = asyncio.create_task(router.run_tasks())
        TASKS.add(new_router_tasks)


def parse_router_id(router_line, exp_id_min, exp_id_max):
    """
    This function parses and validates the line in the configuration file containing the
    router-id.

    INPUTS: router_line, the first line in the configuration file, expected to contain
                         information of the router's id
                         in the format 'router-id ID'. Example: 'router-id 1'.
            exp_id_min, the allowed minimum value of an id.
            exp_id_max, the allowed maximum value of an id.
    OUTPUTS:
            router_id, an int which is the parsed and validated router id
    """

    try:

        router_id_words = router_line[0:10]
        epx_min_len = 10

        if router_id_words == "router-id " and len(router_line) >= epx_min_len:
            try:
                router_id = int(router_line[10:])
            except IndexError:
                print("ERROR: No router id was provided in line 1. Please specify using the "
                      "format 'router-id ID'.")
                exit_programme()
            except ValueError:
                print("ERROR: The router id provided in line 1 was not an integer. Please "
                      "specify using the format 'router-id ID'")
                exit_programme()
            else:
                if router_id in range(exp_id_min, exp_id_max + 1):
                    return router_id
                else:
                    print("ERROR: Router id in line 1 is not within the valid range of "
                          "{0} - {1}, inclusive".format(exp_id_min, exp_id_max))
                    exit_programme()
    except ValueError:
        # throw error of invalid line
        print("ERROR: Line 1 of configuration file does not conform to the format of "
              "'router-id ID'.")
        exit_programme()


def parse_inputs(inputs_line, router_id, exp_port_min, exp_port_max):
    """
    This function parses and validates the line containing the input ports of the router.
    INPUTS: inputs_line, the second line in the configuration file, expected to contain
                        information of the router's
                        input ports in the format 'input-ports P1, P2, ... Pn'.
                        Example: 'input-ports 6110, 6201, 7345'.
            router_id, the router id associated with the input ports.
            exp_id_min, the allowed minimum value of an input port.
            exp_id_max, the allowed maximum value of an input port.
    OUTPUTS: unique_inputs, a list of the parsed and validated input ports which are unique.
    """

    curr_input = ""

    try:
        input_ports_words = inputs_line[0:12]
        epx_min_len = 12

        if input_ports_words == "input-ports " and len(inputs_line) >= epx_min_len:
            inputs_raw = inputs_line.split()
            inputs_raw.pop(0)
            inputs_cleaned = remove_commas(inputs_raw)
            unique_inputs = []

            if len(inputs_cleaned) == 0:
                print("ERROR: Router with id {0} has no input ports specified in line 2 and "
                      "requires at least 1.".format(router_id))
                exit_programme()

            for i in range(0, len(inputs_cleaned)):
                try:
                    curr_input = int(inputs_cleaned[i])
                except ValueError:
                    print("ERROR: The router id provided in line 2 was not an integer. Please "
                          "specify using the format 'input-ports P1, P2, ... Pn'.")
                    exit_programme()
                if curr_input not in range(exp_port_min, exp_port_max + 1):
                    print("ERROR: Input port in line 2 is not an integer within the valid range "
                          "of {0} - {1}, inclusive".format(exp_port_min, exp_port_max))
                    exit_programme()
                elif curr_input in unique_inputs:
                    print("ERROR: Input port {0} in line 2 is already an input port of the router "
                          "with id of {1}.  Its input ports are "
                          "{2}.".format(curr_input,
                                        router_id,','.join([str(input_val) for input_val in unique_inputs])))
                    exit_programme()

                unique_inputs.append(curr_input)  # add to all inputs of current router so far
            return unique_inputs

    except ValueError:
        # throw error of invalid line
        print("ERROR: Line 2 of configuration file does not conform to the format of "
              "'input-ports P1, P2, ... Pn'.")
        exit_programme()
    else:
        print("ERROR: Line 2 of configuration file does not conform to the format of "
              "'input-ports P1, P2, ... Pn'.")
        exit_programme()


def parse_outputs(outputs_line, existing_inputs, router_id, exp_port_min, exp_port_max,
                  exp_metric_min, exp_metric_max, exp_id_min, exp_id_max):
    """
    This function parses and validates the line containing the "contact information" for
    neighboured routers.
    This includes the input port number of a peer router, the metric value for the link
    to the peer router
    as well as the router-id of the peer router.

    INPUTS: outputs_line, the third line in the configuration file, expected to contain
                          information of the router's output ports in the format
                          'outputs P1-M1-ID1, P2-M2-ID2, ... ,Pn-Mn-IDn' where Pn is a port
                           number, Mn is a metric and IDn is a router id.
                          Example: 'outputs 5000-1-1, 5002-5-4'.
            existing_inputs, a list of router's current ports
            router_id, the router id associated with the input ports.
            exp_id_min, the allowed minimum value of an input port.
            exp_id_max, the allowed maximum value of an input port.
            exp_metric_min, the allowed minimum value of a metric of a link.
            exp_metric_max, the allowed maximum value of a metric of a link.
            exp_id_min, the allowed minimum value of an input port.
            exp_id_max, the allowed maximum value of an input port.
    OUTPUTS: outputs_info, a list of the parsed and validated outputs' info. Each list element
                           is a tuple in the format of (output_port_num, metric, router_id).
    """

    try:
        outputs_word = outputs_line[0:8]
        epx_min_len = 8

        if outputs_word == "outputs " and len(outputs_line) >= epx_min_len:
            outputs_raw = outputs_line.split()
            outputs_raw.pop(0)
            outputs_cleaned = remove_commas(outputs_raw)

            if len(outputs_cleaned) == 0:
                print("ERROR: Router with id {0} has no neighbouring routers specified in line 3 "
                      "and requires at least 1.".format(router_id))
                exit_programme()

            # i.e. change 5000-1-1 to [5000, 1, 1]
            outputs_sep_vals = []
            for output in outputs_cleaned:
                separated_vals = output.split('-')
                outputs_sep_vals.append(separated_vals)

            element_type = ['peer input port', 'link metric', 'peer router-id']
            outputs_info = []

            for vals_list in outputs_sep_vals:
                converted = []

                if len(vals_list) != 3:
                    print("ERROR: Output information for a peer router does not match the "
                          "expected format of P1-M1-ID1, where P is the peer router's port "
                          "number, M is the link's metric and ID is the peer router's router-id.")
                    exit_programme()

                for i in range(0, len(vals_list)):
                    try:
                        converted.append(int(vals_list[i]))
                    except TypeError:
                        print("ERROR: The {0} provided in line 3 was not an integer. {1} was "
                              "given. Please specify using the format P1-M1-ID1, where P is the"
                              " peer router's port number, M is the link's metric and ID is the"
                              " peer router's router-id."
                              .format(element_type[i], vals_list[i]))
                        exit_programme()
                peer_input_port = converted[0]
                link_metric = converted[1]
                peer_router_id = converted[2]

                # 1. check port number is within valid range
                if peer_input_port not in range(exp_port_min, exp_port_max + 1):
                    print("ERROR: Peer router's input port of {0} in line 3 is not an integer "
                          "within the valid range of {1} - {2}, inclusive"
                          .format(peer_input_port, exp_port_min, exp_port_max))
                    exit_programme()

                # 2. Check the peer_input_port (output port of current router) isn't in
                # current router's list of inputs
                elif peer_input_port in existing_inputs:
                    print("ERROR: The specified peer router's input port of {0} in line 3 is "
                          "already an input port of router {1}.".format(peer_input_port, router_id))
                    exit_programme()

                # 3. check metric is valid
                elif link_metric not in range(exp_metric_min, exp_metric_max + 1):
                    print("ERROR: Invalid metric value of {0} for the link connecting router"
                          " {1} to router with port number {2} in line 3. Metric must be an integer"
                          " between {3} and {4}, inclusive.".format(link_metric,
                                                                    router_id,
                                                                    peer_input_port,
                                                                    exp_metric_min,
                                                                    exp_metric_max))
                    exit_programme()

                # 4. check router-id is int, within range
                elif peer_router_id not in range(exp_id_min, exp_id_max + 1):
                    print("ERROR: Router id is not an integer within the valid range of "
                          "{0} - {1}, inclusive".format(exp_id_min, exp_id_max))
                    exit_programme()

                outputs_info.append((peer_input_port, link_metric, peer_router_id))

            return outputs_info

    except ValueError:
        print("ERROR: Line 3 of configuration file does not conform to the format of "
              "'outputs P1-M1-ID1, P2-M2-ID2, ... ,Pn-Mn-IDn'.")
        exit_programme()
    else:
        if len(outputs_line) < epx_min_len:
            print("ERROR: Router with id {0} has no neighbouring routers specified in "
                  "line 3 and requires at least 1.".format(router_id))
            exit_programme()
        else:
            print(
                "ERROR: Line 3 of configuration file does not conform to the format of "
                "'outputs P1-M1-ID1, P2-M2-ID2, ... ,Pn-Mn-IDn'.")
            exit_programme()


def parse_timers(timer_line):
    """
    This function parses and validates the line containing the timer information for the router.

    INPUTS: timer_line, the fourth line in the configuration file, expected to contain
                        information of the period for sending updates, the duration until a
                        timeout occurs and how frequent garbage collection is.
    OUTPUTS: timer_vals, a list of the three timer values specified above as integers in the
                         format 'timer-values , T1, T2, T3'. Example: 'timer-values 3, 18, 12'.
    """

    try:
        if timer_line[0:13] == "timer-values " and len(timer_line) >= 13:
            timers_raw = timer_line.split()
            timers_raw.pop(0)
            timers_cleaned = remove_commas(timers_raw)

            periodic_update_cleaned = timers_cleaned[0]
            timeout_cleaned = timers_cleaned[1]
            garbage_collection_cleaned = timers_cleaned[2]

            if len(timers_cleaned) < 3:
                print("ERROR: Only {0} timer value(s) were specified in line 4 and 3 were "
                      "expected.".format(len(timers_cleaned)))
                exit_programme()
            elif int(periodic_update_cleaned) != PERIOD_UPDATE:
                print("ERROR: The specified periodic update timer value of {0} in line 4 "
                      "was received but {1} was expected."
                      .format(int(periodic_update_cleaned), PERIOD_UPDATE))
                exit_programme()
            elif int(timeout_cleaned) != TIMEOUT:
                print("ERROR: The specified timeout period value of {0} in line 4 was "
                      "received but {1} was expected.".format(int(timeout_cleaned), TIMEOUT))
                exit_programme()
            elif int(garbage_collection_cleaned) != GARBAGE_COLLECTION:
                print("ERROR: The specified garbage collection period value of {0} in line "
                      "4 was received but {1} was expected."
                      .format(int(garbage_collection_cleaned), GARBAGE_COLLECTION))
                exit_programme()

            timer_values = [PERIOD_UPDATE, TIMEOUT, GARBAGE_COLLECTION]

            return timer_values

    except:
        # throw error of invalid line
        print("ERROR: Line 4 of configuration file does not conform to the format of "
              "'input-ports P1, P2, ... Pn'.")
        exit_programme()


def remove_commas(non_clean_list):
    """
    This function removes the commas from a list of ints that are strings which contain
    a comma as the last value in the string.

    INPUTS: non_clean_list, the list of strings to clean.
    OUTPUTS: cleaned, the list of cleaned strings.
    """

    cleaned = []
    for element in non_clean_list:
        if element[-1] == ',':
            cleaned.append(element[:-1])
        else:
            cleaned.append(element)
    return cleaned


def exit_programme():
    """
    This function exits the program.

    INPUTS: N/A
    OUTPUTS: N/A
    """

    print("The programming is stopping now...")
    sys.exit()


async def run_manager_tasks():
    """
    This function runs the asynchronous tasks of the manager.

    INPUTS: N/A
    OUTPUTS: N/A
    """

    running = True

    while running:
        done, pending = await asyncio.wait(TASKS, return_when=asyncio.FIRST_COMPLETED)
        running = len(pending) > 0


async def main():
    """
    This function begins the program.

    INPUTS: N/A
    OUTPUTS: N/A
    """

    start_manager()
    await run_manager_tasks()


asyncio.run(main())

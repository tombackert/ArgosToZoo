import zmq
import json
import time

def initialize_zmq_client(server_address="tcp://localhost:5555"):
    """Initializes and returns a ZMQ REQ socket connected to the server."""
    context = zmq.Context()
    socket = context.socket(zmq.REQ)
    try:
        socket.connect(server_address)
        print(f"Python client attempting to connect to ARGoS ZMQ server at {server_address}...")
        # Send a simple PING or initial handshake to confirm connection if desired
        # For REQ/REP, a send must be followed by a recv.
        # A simple test:
        socket.send_json({"command": "GET_SIMULATION_TIME"}) # Send a harmless initial request
        message = socket.recv_json() # Wait for reply
        if message.get("status") == "success":
            print(f"Successfully connected and received initial time: {message.get('time')}")
        else:
            print(f"Connected, but initial command failed: {message}")

    except zmq.error.ZMQError as e:
        print(f"Failed to connect to ZMQ server at {server_address}: {e}")
        socket.close()
        context.term()
        return None, None
    print(f"Python client connected to {server_address}")
    return context, socket

# Example usage:
# ZMQ_SERVER_PORT = 5555 # Should match the port in the.argos file
# zmq_server_address = f"tcp://localhost:{ZMQ_SERVER_PORT}"
# context, socket = initialize_zmq_client(zmq_server_address)
# if not socket:
#     exit("Could not connect to ARGoS ZMQ server.")


def send_request(socket, request_obj):
    """Sends a JSON request and waits for a JSON response."""
    try:
        # print(f"Sending request: {request_obj}")
        socket.send_json(request_obj)
        response_obj = socket.recv_json()
        # print(f"Received response: {response_obj}")
        return response_obj
    except zmq.error.ZMQError as e:
        print(f"ZMQ Error during request/response: {e}")
        # Consider how to handle this - maybe raise exception or return error structure
        return {"status": "error", "message": f"ZMQ communication error: {e}"}
    except json.JSONDecodeError as e:
        print(f"JSON Decode Error for response: {e}")
        # This might happen if ARGoS sends non-JSON or malformed JSON
        return {"status": "error", "message": f"JSON decode error: {e}"}


def get_simulation_time(socket):
    request = {"command": "GET_SIMULATION_TIME"}
    return send_request(socket, request)

def get_all_robot_ids(socket):
    request = {"command": "GET_ALL_ROBOT_IDS"}
    return send_request(socket, request)

def get_robot_state(socket, robot_id):
    request = {
        "command": "GET_ROBOT_STATE",
        "robot_id": robot_id
    }
    return send_request(socket, request)

def get_all_robot_states(socket):
    request = {"command": "GET_ALL_ROBOT_STATES"}
    return send_request(socket, request)

# Example of basic error checking for a response:
# state_fb0 = get_robot_state(socket, "fb0")
# if state_fb0 and state_fb0.get("status") == "success":
#     print(f"fb0 State: Position={state_fb0.get('position')}, Orientation={state_fb0.get('orientation')}")
# else:
#     print(f"Error getting fb0 state: {state_fb0.get('message', 'Unknown error')}")



def main_loop(socket):
    """Main operational loop for the Python client."""
    try:
        while True:
            # Get current simulation time
            sim_time_response = get_simulation_time(socket)
            if sim_time_response and sim_time_response.get("status") == "success":
                print(f"Current ARGoS Simulation Time: {sim_time_response.get('time')}")
            else:
                print(f"Could not get simulation time: {sim_time_response.get('message', 'No response')}")
                # Potentially break or attempt to reconnect if time is critical

            # Get all robot IDs
            ids_response = get_all_robot_ids(socket)
            if ids_response and ids_response.get("status") == "success":
                robot_ids = ids_response.get("ids")
                print(f"Available robot IDs: {robot_ids}")

                # Get state for each robot
                for robot_id in robot_ids:
                    state = get_robot_state(socket, robot_id)
                    if state and state.get("status") == "success":
                        pos = state.get('position', {})
                        ori = state.get('orientation', {})
                        print(f"  State of {robot_id}: Pos=({pos.get('x',0):.2f}, {pos.get('y',0):.2f}, {pos.get('z',0):.2f}), "
                              f"Ori=(Qx={ori.get('x',0):.2f}, Qy={ori.get('y',0):.2f}, Qz={ori.get('z',0):.2f}, Qw={ori.get('w',0):.2f})")
                    else:
                        print(f"  Could not get state for {robot_id}: {state.get('message', 'No response') if state else 'No response'}")
            else:
                print(f"Could not get robot IDs: {ids_response.get('message', 'No response') if ids_response else 'No response'}")

            # Placeholder for ArgosToZoo specific logic:
            # e.g., analyze data, make decisions, potentially send control commands (if implemented)
            # control_command_response = send_request(socket, {"command": "SOME_CONTROL_ACTION",...})

            time.sleep(1)  # Polling interval: send requests every 1 second

    except KeyboardInterrupt:
        print("\nPython client shutting down due to KeyboardInterrupt.")
    except zmq.error.ZMQError as e:
        print(f"\nPython client encountered a ZMQ error: {e}. Shutting down.")
    finally:
        if socket and not socket.closed:
            print("Closing ZMQ socket.")
            socket.close()
        if 'context' in locals() and context and not context.closed: # Check if context was defined
            print("Terminating ZMQ context.")
            context.term()

if __name__ == "__main__":
    ZMQ_SERVER_PORT = 5555 # Ensure this matches the.argos file configuration
    zmq_server_address = f"tcp://localhost:{ZMQ_SERVER_PORT}"
    
    context, client_socket = initialize_zmq_client(zmq_server_address)
    
    if client_socket:
        main_loop(client_socket)
    else:
        print("Exiting: ZMQ client socket could not be initialized.")
import zmq
import json
import time
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

def initialize_zmq_client(server_address="tcp://localhost:5555"):
    """Initializes and returns a ZMQ REQ socket connected to the server."""
    context = zmq.Context()
    socket = context.socket(zmq.REQ)
    try:
        socket.connect(server_address)
        logging.info(f"Python client attempting to connect to ARGoS ZMQ server at {server_address}...")
        
        socket.send_json({"command": "GET_SIMULATION_TIME"})
        message = socket.recv_json()
        if message.get("status") == "success":
            logging.info(f"Successfully connected and received initial time: {message.get('time')}")
        else:
            logging.warning(f"Connected, but initial command failed: {message}")
    
    except zmq.error.ZMQError as e:
        logging.error(f"Failed to connect to ZMQ server at {server_address}: {e}")
        socket.close()
        context.term()
        return None, None
    
    logging.info(f"Python client connected to {server_address}")
    return context, socket

def send_request(socket, request_obj):
    """Sends a JSON request and waits for a JSON response."""
    try:
        socket.send_json(request_obj)
        response_obj = socket.recv_json()
        return response_obj
    except zmq.error.ZMQError as e:
        logging.error(f"ZMQ Error during request/response: {e}")
        return {"status": "error", "message": f"ZMQ communication error: {e}"}
    except json.JSONDecodeError as e:
        logging.error(f"JSON Decode Error for response: {e}")
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


def main_loop(socket):
    """Main operational loop for the Python client."""
    try:
        while True:
            # Get current simulation time
            sim_time_response = get_simulation_time(socket)
            print()
            if sim_time_response and sim_time_response.get("status") == "success":
                logging.info(f"Current ARGoS Simulation Time: {sim_time_response.get('time')}")
            else:
                logging.warning(f"Could not get simulation time: {sim_time_response.get('message', 'No response')}")

            # Get all robot IDs
            ids_response = get_all_robot_ids(socket)
            if ids_response and ids_response.get("status") == "success":

                robot_ids = ids_response.get("ids")
                logging.info(f"Available robot IDs: {robot_ids}")

                # Get state for each robot
                for robot_id in robot_ids:
                    state = get_robot_state(socket, robot_id)
                    if state and state.get("status") == "success":
                        pos = state.get('position', {})
                        ori = state.get('orientation', {})
                        logging.info(
                            f"State of {robot_id}: Pos=({pos.get('x',0):.2f}, {pos.get('y',0):.2f}, {pos.get('z',0):.2f}), "
                            f"Ori=(Qx={ori.get('x',0):.2f}, Qy={ori.get('y',0):.2f}, Qz={ori.get('z',0):.2f}, Qw={ori.get('w',0):.2f})"
                        )
                    else:
                        logging.warning(f"  Could not get state for {robot_id}: {state.get('message', 'No response') if state else 'No response'}")
            else:
                logging.warning(f"Could not get robot IDs: {ids_response.get('message', 'No response') if ids_response else 'No response'}")

            ### PLACEHOLDER ###
            # TODO: Implement Issue #8 here
            # Placeholder for ArgosToZoo specific logic:
            # e.g., analyze data, make decisions, send control commands
            # control_command_response = send_request(socket, {"command": "SOME_CONTROL_ACTION",...})

            time.sleep(1)  # Polling interval: send requests every 1 second

    except KeyboardInterrupt:
        logging.info("Python client shutting down due to KeyboardInterrupt.")
    except zmq.error.ZMQError as e:
        logging.error(f"Python client encountered a ZMQ error: {e}. Shutting down.")
    finally:
        if socket and not socket.closed:
            logging.info("Closing ZMQ socket.")
            socket.close()
        if 'context' in locals() and context and not context.closed: # Check if context was defined
            logging.info("Terminating ZMQ context.")
            context.term()

if __name__ == "__main__":
    ZMQ_SERVER_PORT = 5555 # Needs to match .argos file config
    zmq_server_address = f"tcp://localhost:{ZMQ_SERVER_PORT}"
    
    context, client_socket = initialize_zmq_client(zmq_server_address)
    
    if client_socket:
        main_loop(client_socket)
    else:
        logging.error("Exiting: ZMQ client socket could not be initialized.")
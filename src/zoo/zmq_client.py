# zmq_client.py
import zmq
import json

class ZMQClient:
    """A resilient ZeroMQ client using a REQ socket with polling."""

    def __init__(self, port="5555", timeout_ms=5000):
        """
        Initializes the client, context, and socket.
        
        Args:
            port (str): The port to connect to.
            timeout_ms (int): The timeout in milliseconds for waiting for a reply.
        """
        self.context = zmq.Context()
        self.socket = self.context.socket(zmq.REQ)
        self.socket.connect(f"tcp://localhost:{port}")
        
        self.poller = zmq.Poller()
        self.poller.register(self.socket, zmq.POLLIN)
        
        self.timeout = timeout_ms
        print(f"ZMQClient initialized, connecting to port {port}...")

    def send_command(self, command, payload=None):
        """
        Sends a command and payload to the server and waits for a reply.

        Args:
            command (str): The command to send (e.g., 'RESET', 'STEP').
            payload (dict, optional): The data associated with the command.

        Returns:
            dict: The JSON response from the server.

        Raises:
            TimeoutError: If no reply is received within the specified timeout.
        """
        request = {
            "command": command,
            "payload": payload or {}
        }
        
        self.socket.send_json(request)
        
        # Use the poller to wait for a reply with a timeout [2, 3]
        socks = dict(self.poller.poll(self.timeout))
        
        if self.socket in socks and socks[self.socket] == zmq.POLLIN:
            reply = self.socket.recv_json()
            return reply
        else:
            # Handle timeout case [4, 5]
            print("ZMQ Error: Request timed out.")
            # To recover, we must close and reopen the socket to break the strict REQ/REP state machine
            self.socket.close()
            self.poller.unregister(self.socket)
            
            self.socket = self.context.socket(zmq.REQ)
            self.poller.register(self.socket, zmq.POLLIN)
            
            raise TimeoutError("No response from C++ simulator within the timeout period.")

    def close(self):
        """Closes the socket and terminates the context."""
        print("Closing ZMQClient.")
        self.socket.close()
        self.context.term()
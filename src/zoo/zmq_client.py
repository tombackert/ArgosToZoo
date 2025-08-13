# zmq_client.py
import zmq
import json
import time

class ZMQClient:
    """A resilient ZeroMQ client using a REQ socket with polling."""

    def __init__(self, port="5555", timeout_ms=5000, handshake_attempts=3, handshake_timeout_ms=1000):
        """
        Initializes the client, context, and socket.
        
        Args:
            port (str): The port to connect to.
            timeout_ms (int): The timeout in milliseconds for waiting for a reply.
        """
        self.context = zmq.Context()
        self.port = port
        self.timeout = timeout_ms
        self.handshake_attempts = handshake_attempts
        self.handshake_timeout_ms = handshake_timeout_ms

        self.poller = zmq.Poller()
        self._create_socket()
        print(f"ZMQClient initialized, connecting to port {port} (timeout={timeout_ms}ms)...")

    def _create_socket(self):
        # (Re)create and register a REQ socket
        self.socket = self.context.socket(zmq.REQ)
        self.socket.connect(f"tcp://localhost:{self.port}")
        try:
            self.poller.register(self.socket, zmq.POLLIN)
        except KeyError:
            pass

    def _destroy_socket(self):
        try:
            self.poller.unregister(self.socket)
        except Exception:
            pass
        try:
            self.socket.close(0)
        except Exception:
            pass
        self.socket = None

    def _handshake(self):
        # Simple 'ping' handshake to realign REQ/REP state machine after recovery
        for attempt in range(self.handshake_attempts):
            try:
                self.socket.send_json({"command": "ping", "payload": {"t": attempt}})
                socks = dict(self.poller.poll(self.handshake_timeout_ms))
                if self.socket in socks and socks[self.socket] == zmq.POLLIN:
                    _ = self.socket.recv_json()  # discard
                    return True
            except Exception:
                time.sleep(0.05)
        return False

    def _recover(self):
        print("[ZMQClient] Attempting recovery: recreating socket & handshake...")
        self._destroy_socket()
        self._create_socket()
        if not self._handshake():
            raise RuntimeError("ZMQClient recovery handshake failed after attempts")
        print("[ZMQClient] Recovery successful.")

    def send_command(self, command, payload=None, retries=1):
        """
        Sends a command and payload to the server and waits for a reply.

        Args:
            command (str): The command to send (e.g., 'reset', 'step').
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
        
        attempt = 0
        last_exc = None
        while attempt <= retries:
            try:
                self.socket.send_json(request)
                socks = dict(self.poller.poll(self.timeout))
                print(f"Sent command: [{command}], waiting for reply (attempt {attempt})...")
                if self.socket in socks and socks[self.socket] == zmq.POLLIN:
                    reply = self.socket.recv_json()
                    return reply
                else:
                    raise TimeoutError("poll timeout")
            except (TimeoutError, zmq.ZMQError, RuntimeError) as e:
                last_exc = e
                print(f"[ZMQClient] Warning: send_command failed ({e}).")
                attempt += 1
                if attempt > retries:
                    break
                try:
                    self._recover()
                except Exception as rec_e:
                    print(f"[ZMQClient] Recovery attempt failed: {rec_e}")
                    last_exc = rec_e
                    continue
        # Exhausted
        if isinstance(last_exc, TimeoutError):
            raise TimeoutError("No response from C++ simulator within the timeout period (after retries)") from last_exc
        raise last_exc

    def close(self):
        """Closes the socket and terminates the context."""
        print("Closing ZMQClient.")
        self.socket.close()
        self.context.term()

"""ZeroMQ client with retry & recovery (FUP-08) plus structured logging (FUP-10).

Replaces stdout prints with a lightweight logger to allow quiet/test modes.
"""
import zmq
import time
from typing import Optional
from .logging_utils import get_logger, SimpleLogger


class ZMQClient:
    """Resilient ZeroMQ REQ client with poll-based timeout + recovery.

    Parameters
    ----------
    port : str
        Server port.
    timeout_ms : int
        Poll timeout for normal requests (ms).
    handshake_attempts : int
        Attempts for recovery handshake.
    handshake_timeout_ms : int
        Timeout (ms) for each handshake poll.
    logger : Optional[SimpleLogger]
        If provided, used for all log output; otherwise a default INFO logger.
    """

    def __init__(
        self,
        port: str = "5555",
        timeout_ms: int = 5000,
        handshake_attempts: int = 3,
        handshake_timeout_ms: int = 1000,
        logger: Optional[SimpleLogger] = None,
    ):
        self.context = zmq.Context()
        self.port = port
        self.timeout = timeout_ms
        self.handshake_attempts = handshake_attempts
        self.handshake_timeout_ms = handshake_timeout_ms
        self.logger = logger or get_logger("INFO")

        self.poller = zmq.Poller()
        self._create_socket()
        self.logger.debug(
            "ZMQClient initialized", port=port, timeout_ms=timeout_ms
        )

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
        self.logger.warn("Recovery start: recreating socket & handshake")
        self._destroy_socket()
        self._create_socket()
        if not self._handshake():
            raise RuntimeError("ZMQClient recovery handshake failed after attempts")
        self.logger.info("Recovery successful")

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
                self.logger.debug(
                    "Command sent; awaiting reply", command=command, attempt=attempt
                )
                if self.socket in socks and socks[self.socket] == zmq.POLLIN:
                    reply = self.socket.recv_json()
                    return reply
                else:
                    raise TimeoutError("poll timeout")
            except (TimeoutError, zmq.ZMQError, RuntimeError) as e:
                last_exc = e
                self.logger.warn("send_command failed", error=str(e), attempt=attempt)
                attempt += 1
                if attempt > retries:
                    break
                try:
                    self._recover()
                except Exception as rec_e:
                    self.logger.error("Recovery attempt failed", error=str(rec_e))
                    last_exc = rec_e
                    continue
        # Exhausted
        if isinstance(last_exc, TimeoutError):
            raise TimeoutError(
                "No response from C++ simulator within the timeout period") from last_exc
        raise last_exc

    def close(self):
        """Closes the socket and terminates the context."""
        try:
            if getattr(self, "socket", None):
                self.socket.close(0)
            if getattr(self, "context", None):
                self.context.term()
            self.logger.debug("ZMQClient closed")
        except Exception as e:
            self.logger.warn("Error during ZMQClient close", error=str(e))

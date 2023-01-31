import ez.repl

import socket
from overrides import override
from tcping import Ping
from typing import Tuple

class InvalidNetworkAddressException(Exception):
    pass

class NetworkAddressUnreachableException(Exception):
    pass

class Transport(ez.repl.Transport):
    def __init__(self):
        self.conn = None
        self.hostname = None
        self.port = None

    @classmethod
    def parseNetworkAddress(cls, networkAddress: str) -> Tuple[str, int]:
        parts = networkAddress.split(':')
        if len(parts) != 2:
            raise InvalidNetworkAddressException(networkAddress)
        try:
            port = int(parts[1])
        except ValueError:
            raise InvalidNetworkAddressException("Invalid port number: " + parts[1])
        return tuple((parts[0], port))

    @classmethod
    def ping(cls, info: Tuple[str, int], timeout: int = 60):
        try:
            hostname = info[0]
            port = info[1]
            check = Ping(hostname, port, timeout)
            #check.ping(1)
        except Exception as ex:
            raise NetworkAddressUnreachableException(str(ex))

    @override(check_signature=False)
    def reset(self, info: Tuple[str, int]):
        if self.conn:
            self.close()
        self.hostname = info[0]
        self.port = info[1]

    @override
    def handshake(self):
        assert self.conn == None, "Call reset() before any reconnect"
        try:
            # hostname, port
            self.conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.conn.connect((self.hostname, self.port))
        except ConnectionRefusedError as ex:
            self.conn = None
            raise ez.repl.HandshakeFailedException(str(ex))
        except OSError as ex:
            self.conn = None
            raise ez.repl.HandshakeFailedException(str(ex))

    @override
    def finalize(self):
        assert self.conn, "Call handshake() before finalizing"
        return self

    def read(self, size: int) -> bytes:
        assert self.conn, "Not yet connected"
        assert size > 0, "Number of bytes must be positive"
        bytesReceived = b''
        numBytesRemaining = size
        try:
            while numBytesRemaining > 0:
                # What we pass here is the MAXIMUM number of bytes to be read.
                # We don't follow the advice from the docs to pass something
                # like 4096. Instead, we abuse the parameter to receive exactly
                # one message and keep our code simple.
                batch = self.conn.recv(numBytesRemaining)
                numBytesRemaining -= len(batch)
                bytesReceived += batch
        except ValueError:
            raise ConnectionAbortedError(f"Lost connection to {self.hostname}:{self.port}")
        return bytesReceived

    def write(self, data: bytes):
        assert self.conn, "Not yet connected"
        self.conn.send(data)

    def close(self):
        assert self.conn, "Not yet connected"
        self.conn.close()
        self.conn = None

import ez.repl

from abc import abstractmethod
from collections import deque
from overrides import override
from select import epoll, EPOLLIN

class SubprocessHandshakeFailedException(ez.repl.HandshakeFailedException):
    def __init__(self, actual: bytes):
        self.actualReceived = " ".join([f"{byte:02x}" for byte in actual])

class Transport(ez.repl.Transport):
    def __init__(self):
        super().__init__()
        self.process = None
        self.timeout_connect = True

    @abstractmethod
    def launch(self, firmware: str):
        # Derived classes may set timeout_connect to False, e.g. to give users
        # sufficient time to connect a debugger.
        pass

    @abstractmethod
    def shutdown(self):
        pass

    @override(check_signature=False)
    def reset(self, info: str) -> bool:
        if self.process:
            self.shutdown()
        self.process = self.launch(info)
        self.inbound = self.process.stdout
        self.outbound = self.process.stdin
        self.inbound_pending = deque()
        self.inbound_poll = epoll()
        self.inbound_poll.register(self.inbound, EPOLLIN)
        self.timeout_poll = 1.0 if self.timeout_connect else None
        return True

    @override
    def finalize(self):
        # Once we are connected, we always fetch with timeout
        self.timeout_poll = 0.1
        return self

    def awaitToken(self, token: bytes):
        idx = 0
        actual = bytearray()
        while idx < len(token):
            byte = self.read(1)
            if len(byte) == 0:
                raise SubprocessHandshakeFailedException(actual)
            actual += byte
            if byte[0] == token[idx]:
                idx += 1  # Match: receive next character
            else:
                idx = 0   # Mismatch: start from beginning
        return # Success

    def fetch(self, minimum: int = None):
        size = 0
        while True:
            ret = self.inbound_poll.poll(self.timeout_poll)
            if not ret or ret[0][1] is not EPOLLIN:
                return size
            buf = self.inbound.read1()
            size += len(buf)
            self.inbound_pending.extend(buf)
            if minimum and size > minimum:
                return size

    def read(self, size: int) -> bytes:
        data = bytearray()
        missing = size - len(self.inbound_pending)
        if missing > 0:
            self.fetch(missing) # TODO: Retry if bytes missing?
        for _ in range(size):
            data.append(self.inbound_pending.popleft())
        return data

    def write(self, data: bytes):
        self.outbound.write(data)
        self.outbound.flush()

    def close(self):
        self.inbound.close()
        self.outbound.close()

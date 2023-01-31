from codecs import ascii_encode, ascii_decode
from functools import reduce
from io import BytesIO
from overrides import override
from typing import List

import ez.io
import ez.repl
import ez.repl.opcode

def is_uint32_t(n):
    return n >= 0 and abs(n) <= 0xffffffff

def uint32_t(n):
    assert is_uint32_t(n)
    return n

def sum(values: List[int]):
    return reduce(lambda x,y: x+y, values) if len(values) > 0 else 0

def dumpMessage(data: bytes, layout: List[int], indent: str = "  "):
    assert len(data) == sum(layout), "Message layout corrupt"
    it = iter(data)
    for item in [[next(it) for _ in range(size)] for size in layout]:
        ez.io.debug(indent + " ".join([f"{byte:02x}" for byte in item]))

class InboundMessage32(ez.repl.InboundMessage):
    HEADER_SIZE = 32
    def __init__(self, parent):
        self.parent = parent
        self.endian = parent.endian
        # While reading messages we track item sizes, so that we can dump bytes
        # in a structured way once we're done()
        self.layout = []
        self.dump = parent.dumpMessage
        # Read whole messages and buffer them for random-access without
        # side-effects on the underlying channel.
        self.buffer = BytesIO()
        # Message size is first header item. Copy the bytes to the buffer and
        # read it back so it's considered in the message layout.
        bytesSize = parent.stream.read(8)
        self.buffer.write(bytesSize)
        self.buffer.seek(0)
        self.size = self.readUInt32()
        assert len(self.layout) == 1, "Size field is recorded in message layout"
        assert self.layout[0] == len(bytesSize), "Size field is recorded correctly"
        # Copy remaining message to the buffer and read all header info
        numBytesRemaining = self.size - len(bytesSize)
        bytesRemaining = parent.stream.read(numBytesRemaining)
        assert len(bytesRemaining) == numBytesRemaining
        self.buffer.write(bytesRemaining)
        self.buffer.seek(len(bytesSize))
        self.opcode = self.readUInt32()
        _ = self.readUInt32() # TODO: seqID is unused. but right now it's still in the protocol
        self.tag = self.readUInt32()
        assert len(self.layout) == 4, "Header fields recorded in message layout"
        assert self.buffer.tell() == self.HEADER_SIZE, "Done with header"
    def readByte(self) -> int:
        self.layout += [1]
        return self.buffer.read(1)[0]
    @override
    def readErrorCode(self) -> int:
        assert self.buffer.tell() == self.HEADER_SIZE, "Error code is first byte in body"
        return self.readByte()
    def readUInt32(self) -> int:
        self.layout += [8]
        return uint32_t(int.from_bytes(self.buffer.read(8), self.endian))
    @override
    def readAddr(self) -> int:
        return self.readUInt32()
    @override
    def readSize(self) -> int:
        return self.readUInt32()
    @override
    def readBytes(self) -> bytes:
        length = self.readSize()
        self.layout[-1] += length # Size + Content as a single item
        return self.buffer.read(length)
    @override
    def readString(self) -> str:
        bytes = self.readBytes()
        str, _ = ascii_decode(bytes)
        return str
    # FIXME: Deprecated! Firmwares should stop to send such messages!
    @override
    def readBytesRemaining(self) -> bytes:
        length = self.size - self.buffer.tell()
        self.layout += [length] # Size + Content as a single item
        return self.buffer.read(length)
    @override
    def done(self) -> bool:
        if self.buffer.tell() < self.size:
            return False
        self.buffer.seek(0)
        self.dump(ez.repl.opcode.name(self.opcode) + ' <-',
                  self.buffer.read(self.size), self.layout)
        return True

seqId = 0 # FIXME: New firmware ABIs shouldn't need that

class OutboundMessage32(ez.repl.OutboundMessage):
    def __init__(self, parent, banner: str):
        self.buffer = BytesIO()
        self.parent = parent
        self.layout = []
        self.banner = banner
    @override
    def writeUInt32(self, data: int):
        assert is_uint32_t(data)
        self.buffer.write(int.to_bytes(data, 8, self.parent.endian))
        self.layout += [8]
    @override
    def fixupUInt32(self, data: int, item: int):
        insertPos = self.buffer.tell()
        assert item >= 0 and item < len(self.layout)
        self.buffer.seek(sum(self.layout[:item]))
        assert is_uint32_t(data)
        self.buffer.write(int.to_bytes(data, 8, self.parent.endian))
        self.buffer.seek(insertPos)
    @override
    def writeAddr(self, data: int):
        self.writeUInt32(data)
    @override
    def writeSize(self, data: int):
        self.writeUInt32(data)
    @override
    def writeBytes(self, data: bytes):
        length = len(data)
        self.writeSize(length)
        self.layout[-1] += length # Size + Content as a single item
        self.buffer.write(data)
    @override
    def writeString(self, data: str):
        byteData, _ = ascii_encode(data) # FIXME: Let's assume that for now
        self.writeBytes(byteData)
    @override
    def send(self):
        global seqId
        seqId += 1 # TODO: Right now seqID is still in the protocol
        bufferSize = self.buffer.tell()
        self.fixupUInt32(bufferSize, 0)
        self.fixupUInt32(seqId, 2)
        self.buffer.seek(0)
        data = self.buffer.read(bufferSize)
        self.parent.stream.write(data)
        self.parent.dumpMessage(self.banner + ' ->', data, self.layout)

# FIXME: In 0.0.5 protocol all numeric fields are still 64-bit wide!
class Stream32(ez.repl.IOSerializer):
    def __init__(self):
        super().__init__()
        self.stream = None
    @override
    def open(self, stream):
        if self.stream:
            self.stream.close()
        self.stream = stream
    @override
    def connected(self) -> bool:
        return self.stream != None
    @override
    def message(self, opcode: int, tag: int = 0, symbol: str = "") -> OutboundMessage32:
        assert self.endian != 'unknown', "Endianness undefined. Can only write single bytes."
        banner = ez.repl.opcode.name(opcode)
        if len(symbol) > 0:
            banner += f" {symbol} (0x{tag:08x})"
        # Size and sequence ID are injected upon send()
        msg = OutboundMessage32(self, banner)
        msg.writeUInt32(0)
        msg.writeUInt32(opcode)
        msg.writeUInt32(0)
        msg.writeUInt32(tag)
        return msg
    @override
    def receive(self) -> InboundMessage32:
        assert self.endian != 'unknown', "Endianness undefined. Can only read single bytes."
        return InboundMessage32(self)
    def dumpMessage(self, banner: str, data: bytes, layout: List[int], indent: str = "  "):
        if self.verbose:
            ez.io.debug(banner)
            dumpMessage(data, layout, indent)
    @override
    def close(self):
        self.stream.close()
        self.stream = None

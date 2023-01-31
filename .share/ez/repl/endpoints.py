from . import *

# TODO: Setup and hangup are no endpoints! Make DeviceResponse
class SetupMessageDecoder(EndpointResponseDecoder):
    def __init__(self, msg: InboundMessage):
        import ez.repl.opcode
        if msg.opcode != ez.repl.opcode.Connect:
            self.forceDone(msg)
            raise DeviceProtocolException(
                "Unexpected op-code. Expected Setup but received: " +
                ez.repl.opcode.name(msg.opcode))
        if msg.tag != 0:
            self.forceDone(msg)
            raise DeviceProtocolException(
                "Expected TagAddr field to be zero in Setup message")

        _ = msg.readString() # Device version is deprecated
        self.codeBufferAddr = msg.readAddr()
        self.codeBufferSize = msg.readSize()

        self.endpoints = dict()
        numBoostrapFuncs = msg.readSize()
        for _ in range(numBoostrapFuncs):
            symbol = msg.readString()
            addr = msg.readAddr()
            self.endpoints[symbol] = addr # TODO: Handle collisions?
        self.checkDone(msg)

class HangupMessageDecoder(EndpointResponseDecoder):
    def __init__(self, msg: InboundMessage):
        import ez.repl.opcode
        import ez.repl.errorcode
        if msg.readErrorCode() != ez.repl.errorcode.Success:
            raise OperationFailedException("Disconnect failed: ", msg)
        if msg.opcode != ez.repl.opcode.Disconnect:
            self.forceDone(msg)
            raise DeviceProtocolException(
                "Unexpected response op-cpode for disconnect request: " +
                ez.repl.opcode.name(msg.opcode))
        self.checkDone(msg)

class EmptyResponseDecoder(EndpointResponseDecoder):
    def decode(self, msg: InboundMessage) -> dict:
        return {}

class LookupResponseDecoder(EndpointResponseDecoder):
    def __init__(self, symbols: dict):
        self.symbols = symbols
    def decode(self, msg: InboundMessage) -> dict:
        self.checkSymbolCount(msg)
        resp = {}
        for key in self.symbols:
            resp[key] = msg.readAddr()
        return resp
    def checkSymbolCount(self, msg: InboundMessage):
        actualItems = msg.readSize()
        expectedItems = len(self.symbols)
        if actualItems != expectedItems:
            raise DeviceProtocolException(
                "Lookup response has invalid number of addresses: " +
                f"expected {expectedItems} but received {actualItems}")

class Lookup(Endpoint):
    def encode(self, msg: OutboundMessage, symbols: dict):
        if len(symbols) == 0:
            raise HostAPIException("Empty symbol set in lookup request")
        msg.writeSize(len(symbols))
        for key in symbols:
            msg.writeString(key)
        return LookupResponseDecoder(symbols)

class Commit(Endpoint):
    def encode(self, msg: OutboundMessage, segments: dict):
        if len(segments) == 0:
            raise HostAPIException("Empty segment set in commit request")
        msg.writeSize(len(segments))
        for addr in segments:
            assert type(addr) is not str or addr.isdigit(), "Segment key must be convertible to int"
            if not 'size' in segments[addr]:
                raise HostAPIException(f"Missing 'size' attribute in segment 0x{addr}")
            if not 'data' in segments[addr]:
                raise HostAPIException(f"Missing 'data' attribute in segment 0x{addr}")
            msg.writeAddr(int(addr))
            msg.writeSize(segments[addr]['size'])
            msg.writeBytes(segments[addr]['data'])
        return EmptyResponseDecoder()

class Execute(Endpoint):
    def encode(self, msg: OutboundMessage, input: dict):
        if not 'addr' in input:
            raise HostAPIException(f"Missing 'addr' attribute in execute request")
        msg.writeAddr(input['addr'])
        return EmptyResponseDecoder()

class CStringResponseDecoder(EndpointResponseDecoder):
    def decode(self, msg: InboundMessage):
        return { 'str': msg.readString() }
    # FIXME: Add a leading error byte to the response!
    def __call__(self, msg: InboundMessage):
        #self.checkErrorCode(msg)
        output = self.decode(msg)
        self.checkDone(msg)
        return output

class MemReadCString(Endpoint):
    def encode(self, msg: OutboundMessage, input: dict):
        assert 'addr' in input, "Missing 'addr' attribute in MemReadCString"
        msg.writeAddr(input['addr'])
        return CStringResponseDecoder()

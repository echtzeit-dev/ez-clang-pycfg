import inject

import ez.io
import ez.util
import ez.repl
import ez.repl.opcode
import ez.repl.errorcode

from abc import abstractmethod
from codecs import ascii_decode
from overrides import EnforceOverrides
from typing import Any, List

_componentMap = {}
def register(map):
    global _componentMap
    _componentMap.update(map)
    def reassociate(binder):
         for entry in _componentMap:
            binder.bind_to_constructor(entry, _componentMap[entry])
    import inject
    inject.clear_and_configure(reassociate, bind_in_runtime=False)

class HandshakeFailedException(Exception):
    pass

class Transport(EnforceOverrides):
    @abstractmethod
    def reset(self, info: Any):
        pass
    @abstractmethod
    def handshake(self):
        pass
    @abstractmethod
    def finalize(self):
        pass

class ReplaceFirmwareException(Exception):
    def __init__(self, exitCode: int, commandLine: List[str], output: str):
        super().__init__(
            "Replace firmware failed with exit code: " + str(exitCode) +
            "\nCommand line: " + " ".join(commandLine) +
            "\nOutput:\n" + output)

class RecoveryFailedException(Exception):
    def __init__(self, deviceId: str):
        super().__init__("Failed to recover connection: " + deviceId)

class Recovery(EnforceOverrides):
    def __init__(self):
        self.verbose = False
    @abstractmethod
    def bundledFirmware(self) -> str:
        pass
    @classmethod
    def bundledFirmwareInDefaultPath(cls, deviceId: str, fileName: str) -> str:
        import ez
        import os
        return "/" + os.path.join("usr", "lib", "ez-clang", ez.__version__, "firmware", deviceId, fileName)
    @abstractmethod
    def attemptAutoRecovery(self) -> bool:
        pass
    @abstractmethod
    def negotiateRecovery(self) -> bool:
        pass
    def notifyAutoRecoveryFailed(self, deviceId: str):
        ez.io.warning("Failed to connect: " + deviceId)
    def raiseRecoveryFailedException(self, deviceId: str):
        raise RecoveryFailedException(deviceId)

class InboundMessage(EnforceOverrides):
    @abstractmethod
    def readErrorCode(self) -> int:
        pass
    @abstractmethod
    def readAddr(self) -> int:
        pass
    @abstractmethod
    def readSize(self) -> int:
        pass
    @abstractmethod
    def readString(self) -> str:
        pass
    @abstractmethod
    def readBytes(self) -> bytes:
        pass
    @abstractmethod
    def readBytesRemaining(self) -> bytes:
        pass
    @abstractmethod
    def done(self) -> bool:
        pass

class OutboundMessage(EnforceOverrides):
    @abstractmethod
    def writeAddr(self, data: int):
        pass
    @abstractmethod
    def writeSize(self, data: int):
        pass
    @abstractmethod
    def writeBytes(self, data: bytes):
        pass
    @abstractmethod
    def writeString(self, data: str):
        pass
    @abstractmethod
    def writeUInt32(self, data: int):
        pass
    @abstractmethod
    def fixupUInt32(self, data: int, item: int):
        pass
    @abstractmethod
    def send(self):
        pass

class IOSerializer(EnforceOverrides):
    def __init__(self):
        self.endian = 'unknown'
        self.verbose = False
    @abstractmethod
    def connected(self):
        pass
    @abstractmethod
    def open(self, stream):
        pass
    @abstractmethod
    def message(self, opcode: int) -> OutboundMessage:
        pass
    @abstractmethod
    def receive(self) -> InboundMessage:
        pass
    @abstractmethod
    def close(self):
        pass

class DeviceABIException(Exception):
    pass

class DeviceResponsePaddingException(DeviceABIException):
    def __init__(self, msg: InboundMessage):
        extraBytes = len(msg.readBytesRemaining())
        msg.done() # Dump entire message
        super().__init__(f"Unexpected message size: {extraBytes} extra bytes")

class DeviceErrorReportException(Exception):
    pass

class DeviceProtocolException(Exception):
    pass

class HostAPIException(Exception):
    pass

class OperationFailedException(Exception):
    def __init__(self, message: str, response: InboundMessage):
        details = response.readString()
        response.done() # Dump message bytes
        super().__init__(message + details)

class UnexpectedDisconnectException(Exception):
    pass

class UnexpectedRebootException(Exception):
    def __init__(self, connectMessage: InboundMessage):
        super().__init__("Received unexpected connect request")
        self.connectMessage = connectMessage # We did read the header already, the message-body is remaining

class EndpointResponseDecoder():
    def checkErrorCode(self, msg: InboundMessage):
        if msg.readErrorCode() != ez.repl.errorcode.Success:
            raise DeviceErrorReportException(msg.readString())
    def checkDone(self, msg: InboundMessage):
        if not msg.done():
            raise DeviceResponsePaddingException(msg)
    def forceDone(self, msg: InboundMessage):
        msg.readBytesRemaining()
        msg.done()
    def __call__(self, msg: InboundMessage):
        self.checkErrorCode(msg)
        output = self.decode(msg)
        self.checkDone(msg)
        return output
    @abstractmethod
    def decode(self, msg: InboundMessage) -> dict:
        raise NotImplementedError("Implement in derived class for each endpoint")

class Endpoint():
    def __init__(self, symbol: str):
        self.symbol = symbol
        self.addr = 0
    @abstractmethod
    def encode(self, msg: OutboundMessage, input: dict) -> EndpointResponseDecoder:
        pass
    def assignDeviceAddress(self, addr: int):
        assert self.addr == 0, "Device address can be assigned only once"
        self.addr = addr
    def handleUnexpectedResponse(self, response: InboundMessage) -> dict:
        if response.opcode == ez.repl.opcode.Call:
            response.done()
            raise Exception("Callbacks not yet supported")
        elif response.opcode == ez.repl.opcode.Connect:
            response.done()
            raise UnexpectedRebootException(response)
        elif response.opcode == ez.repl.opcode.Disconnect:
            if response.readErrorCode() == ez.repl.errorcode.Success:
                response.readBytesRemaining()
                response.done()
                raise DeviceProtocolException("Unexpected disconnect without error message")
            else:
                msg = response.readString()
                response.done()
                raise UnexpectedDisconnectException(msg)
        else:
            response.done()
            raise DeviceABIException("Received unknown opcode: " + response.opcode +
                                     "\nExpected response to call request.")

class Session:
    def __init__(self, deviceId: str = '<unknown device id>'):
        self.deviceId = deviceId
        self.disconnecting = False
        self.endpoints = {
            'lookup': ez.repl.endpoints.Lookup('__ez_clang_rpc_lookup'),
            'commit': ez.repl.endpoints.Commit('__ez_clang_rpc_commit'),
            'execute': ez.repl.endpoints.Execute('__ez_clang_rpc_execute'),
            'memory.read.cstr': ez.repl.endpoints.MemReadCString('__ez_clang_rpc_mem_read_cstring')
        }

    @inject.params(transport=Transport, recovery=Recovery)
    def connect(self, info, transport: Transport, recovery: Recovery):
        transport.reset(info)
        try:
            transport.handshake()
        except HandshakeFailedException:
            if not recovery.attemptAutoRecovery():
                recovery.notifyAutoRecoveryFailed(self.deviceId)
                if not recovery.negotiateRecovery():
                    recovery.raiseRecoveryFailedException(self.deviceId)
                    # unreachable
        return transport.finalize()

    def relocateEndpoint(self, symbol: str, address: int) -> bool:
        endpoint = [ep for ep in self.endpoints.values() if ep.symbol == symbol]
        if len(endpoint) == 0:
            return False
        else:
            assert len(endpoint) == 1, "Endpoints with clashing symbol names"
            endpoint[0].assignDeviceAddress(address)
            return True

    def resolveEndpoint(self, name: str) -> Endpoint:
        if not name in self.endpoints:
            raise HostAPIException("Unknown endpoint: " + name)
        endpoint = self.endpoints[name]
        if endpoint.addr == 0:
            # Lookup actual device addresses lazily
            addresses = self.call('lookup', { endpoint.symbol: 0 })
            endpoint.addr = addresses[endpoint.symbol]
        return endpoint

    @inject.params(stream=IOSerializer)
    def call(self, endpoint: str, input: dict, stream: IOSerializer) -> dict:
        # Encode and send request + store decode functor
        ep = self.resolveEndpoint(endpoint)
        request = stream.message(ez.repl.opcode.Call, ep.addr, ep.symbol)
        decode = ep.encode(request, input)
        request.send()

        # Await and decode response
        result = None
        while True:
            response = stream.receive()
            if not (response.tag != 0) == (response.opcode == ez.repl.opcode.Call):
                raise DeviceABIException("Tag field must not be used outside Call messages")
            if response.opcode == ez.repl.opcode.Result:
                # Defer output until execution finished
                result = response.readBytesRemaining() # FIXME!
                response.done()
            elif response.opcode == ez.repl.opcode.StdOut:
                str, _ = ascii_decode(response.readBytesRemaining()) # FIXME!
                response.done()
                ez.io.output(str)
            elif response.opcode == ez.repl.opcode.Return:
                output = decode(response)
                if result:
                    ez.io.output(self.formatExpressionResult(result))
                return output
            else:
                return ep.handleUnexpectedResponse(response)

    # FIXME: This entire function is a hack!
    @inject.params(stream=IOSerializer)
    def formatExpressionResult(self, result: bytes, stream: IOSerializer):
        resultStr = self.host.formatResult(result)
        declType = self.host.getResultDeclTypeAsString()
        # For c-strings: read contents from device memory and dump it right away
        if declType == "char *" or declType == "const char *":
            addr = int.from_bytes(result, stream.endian)
            response = self.call('memory.read.cstr', { 'addr': addr })
            resultStr += " " + response['str']
        return resultStr

    @inject.params(stream=IOSerializer)
    def disconnect(self, stream: IOSerializer) -> bool:
        if stream.connected() and not self.disconnecting:
            with ez.util.ScopeGuard(self.disconnecting):
                stream.message(ez.repl.opcode.Disconnect).send()
                ez.repl.endpoints.HangupMessageDecoder(stream.receive())
                stream.close()
        return True

import ez.repl.endpoints
register({
    IOSerializer: lambda: IOSerializer(),
    Recovery: lambda: Recovery(),
    Session: lambda: Session(),
    Transport: lambda: Transport(),
})

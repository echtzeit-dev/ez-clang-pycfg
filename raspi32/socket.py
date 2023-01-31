import ez.io
import ez_clang_api
if ez_clang_api.Host.debugPython(__debug__):
    import debugpy
    debugpy.listen(5678)
    ez.io.note("Python API waiting for debugger. Attach to localhost:5678 to proceed.")
    debugpy.wait_for_client()
    debugpy.breakpoint()

import inject
import os
import socket
from tcping import Ping
from typing import Tuple
from overrides import override

import ez.repl
import ez.repl.endpoints
import ez.repl.serialize
import ez.repl.socket
import ez.util
import ez.util.package

class Raspi32Transport(ez.repl.socket.Transport):
    pass

class Raspi32Recovery(ez.repl.Recovery):
    @override
    def bundledFirmware(self) -> str:
        # We cannot change the executor that runs on the remote end (right now)
        return None

    @inject.params(transport=ez.repl.Transport)
    def awaitHandshake(self, transport: Raspi32Transport, timeout: float = 5.0) -> bool:
        import sys
        import time
        self.handshakeFailedReason = ""
        waiting = "Connecting: waiting for device response."
        start = time.time()
        while time.time() - start < timeout:
            try:
                transport.handshake()
                sys.stdout.write("\n") if len(waiting) == 1 else None
                return True
            except ez.repl.HandshakeFailedException as ex:
                sys.stdout.write(waiting)
                sys.stdout.flush()
                waiting = "."
                self.handshakeFailedReason = str(ex)
                time.sleep(0.95)
                continue
            except:
                break
        sys.stdout.write("\n") if len(waiting) == 1 else None
        return False

    @override
    def attemptAutoRecovery(self) -> bool:
        # Sockets are pretty reliable. Just wait and retry for a bit.
        return self.awaitHandshake()

    @inject.params(transport=ez.repl.Transport)
    @override(check_signature=False)
    def notifyAutoRecoveryFailed(self, deviceId: str, transport: Raspi32Transport):
        details = f" ({self.handshakeFailedReason})" if self.handshakeFailedReason else ""
        ez.io.warning(f"Failed to connect: {deviceId}@{transport.hostname}:{transport.port}{details}")

    @inject.params(transport=ez.repl.Transport)
    @override(check_signature=False)
    def negotiateRecovery(self, transport: Raspi32Transport) -> bool:
        if ez.io.ask("No-one listening. Start executor on network device " +
                     f"{transport.hostname}:{transport.port} and try again"):
            try:
                return self.awaitHandshake()
            except ez.repl.HandshakeFailedException as ex:
                ez.io.error(str(ex))
        return False

ez.repl.register({
    ez.repl.IOSerializer: lambda: ez.repl.serialize.Stream32(),
    ez.repl.Recovery: lambda: Raspi32Recovery(),
    ez.repl.Session: lambda: ez.repl.Session(deviceId='raspi32'),
    ez.repl.Transport: lambda: Raspi32Transport(),
})

def accept(networkAddress: str) -> Tuple[str, int]:
    try:
        info = Raspi32Transport.parseNetworkAddress(networkAddress)
        Raspi32Transport.ping(info)
        return info
    except ez.repl.socket.InvalidNetworkAddressException as ex:
        ez.io.debug(str(ex))
        return None
    except ez.repl.socket.NetworkAddressUnreachableException as ex:
        ez.io.debug(str(ex))
        return None

@inject.params(session=ez.repl.Session, stream=ez.repl.IOSerializer)
def connect(info: Tuple[str, int], host: ez_clang_api.Host,
            raspi32: ez_clang_api.Device, session: ez.repl.Session,
            stream: ez.repl.serialize.Stream32) -> ez.repl.IOSerializer:
    session.host = host # FIXME: formatExpressionResult()
    raspi32.name = session.deviceId
    raspi32.transport = "TCP -> raspi32" # TODO: Rename property to 'description' or so
    stream.endian = 'little'
    stream.verbose = 'rpc_bytes' in host.verbose()
    stream.open(session.connect(info))
    return stream

@inject.params(session=ez.repl.Session)
def setup(stream: ez.repl.IOSerializer, host: ez_clang_api.Host,
          raspi32: ez_clang_api.Device, session: ez.repl.Session):
    # Read setup message
    setup = ez.repl.endpoints.SetupMessageDecoder(stream.receive())

    # Start configuring device
    raspi32.setCodeBuffer(setup.codeBufferAddr, setup.codeBufferSize)
    for symbol in setup.endpoints:
        if not session.relocateEndpoint(symbol, setup.endpoints[symbol]):
            ez.io.warning(f"No endpoint for bootstrap function {symbol} " +
                          f"(0x{setup.endpoints[symbol]:08x})")

    if session.endpoints['lookup'].addr == 0:
        raise ez.repl.DeviceProtocolException("Missing bootstrap symbol " +
                                              session.endpoints['lookup'].symbol)

    # TODO: Include debug/release build and built-in features in setup message
    raspi32.debug = True
    raspi32.features = [ "-lc" ]

    # Hardware specific infos can be hardcoded
    raspi32.triple = "arm-none-eabi"
    raspi32.cpu = "cortex-a53"
    raspi32.page_size = 4096
    raspi32.default_alignment = 64

    # Extract default paths from the reference compiler
    #
    # Note: PlatformIO has no toolchain packages for arm-linux-gnueabihf (yet?),
    # so we must install it manually. E.g. on Ubuntu run:
    #
    #   > sudo apt update
    #   > sudo apt install -y g++-arm-linux-gnueabihf
    #
    gcc = ez.util.package.findCompiler("arm-linux-gnueabihf-g++")

    # If the firmware has libc builtin, we need matching includes
    if "-lc" in raspi32.features:
        raspi32.header_search_paths += gcc.parseHeaderSearchPaths(["-march=armv6+fp"])

    # Compiler flags and defines: Pass triple and CPU. Clang resolves the
    # subarch as ARMv8-A, which is in line with the Raspberry Pi3 docs. Noting
    # it here because 32-bit Raspbian reports uname armv7l and the system GCC
    # claims to compile for armv6..
    #
    raspi32.flags += [ "-target", "arm-linux-gnueabihf", "-mcpu=cortex-a53", "-mthumb",
                       "-mfloat-abi=hard", "-mfpu=vfp" ]
    raspi32.flags += [ "-Og", "-g2" ] if raspi32.debug else [ "-Os", "-g0" ]
    raspi32.flags += [ "-fno-rtti", "-fno-exceptions", "-std=c++17" ]
    raspi32.flags += [ "-DDEBUG" ] if raspi32.debug else [ "-DNDEBUG" ]

    return host.addDevice(raspi32)

@inject.params(session=ez.repl.Session)
def call(endpoint: str, data: dict, session: ez.repl.Session) -> dict:
    return session.call(endpoint, data)

@inject.params(session=ez.repl.Session, stream=ez.repl.IOSerializer)
def disconnect(session: ez.repl.Session, stream: ez.repl.IOSerializer):
    # In our TCP connection, the remote host is the server and we are the
    # client! Let's issue a second disconnect to let the server know we finished
    # receiving its response and it can finally shut down the connection.
    if stream.connected() and not session.disconnecting:
        with ez.util.ScopeGuard(session.disconnecting):
            stream.message(ez.repl.opcode.Disconnect).send()
            ez.repl.endpoints.HangupMessageDecoder(stream.receive())
            stream.message(ez.repl.opcode.Disconnect).send() # Acknowledge done
            stream.close()
    return True

import ez.io
import ez_clang_api
if ez_clang_api.Host.debugPython(__debug__):
    import debugpy
    debugpy.listen(('0.0.0.0', 5678))
    ez.io.note("Python API waiting for debugger. Attach to 0.0.0.0:5678 to proceed.")
    debugpy.wait_for_client()
    debugpy.breakpoint()

import inject
import os
from overrides import override

import ez.repl
import ez.repl.endpoints
import ez.repl.subprocess
import ez.repl.serialize
import ez.util
import ez.util.package

class LM3S811Transport(ez.repl.subprocess.Transport):
    @override
    def launch(self, firmware: str):
        # Basic QEMU invocation
        cmd = ["qemu-system-arm", "-machine", "lm3s811evb", "-nographic", "-m", "16K",
                                  "-kernel", firmware, "-serial", "stdio",
                                  "-monitor", "null"]

        # Debug QEMU firmware: ez-clang --connect=qemu --rpc-debug-qemu
        if ez_clang_api.Host.debugQemu():
            cmd += ["-s", "-S"]
            self.timeout_connect = False
            print("QEMU waiting for debugger. Attach to localhost:1234 to proceed.")
            print(" ".join(cmd))

        # Run QEMU without stdout buffering
        import subprocess
        cmd = ["stdbuf", "-oL"] + cmd
        return subprocess.Popen(cmd, stdin=subprocess.PIPE,
                                     stdout=subprocess.PIPE,
                                     stderr=subprocess.STDOUT)

    @override
    def shutdown(self):
        if self.process:
            self.process.kill()
            self.process = None

    @override
    def handshake(self):
        magic = "01 23 57 bd bd 57 23 01"
        try:
            self.awaitToken(bytes.fromhex(magic))
        except ez.repl.HandshakeFailedException as ex:
            ex.message = f"Did not receive handshake sequence '{magic}'"
            raise ex

class LM3S811Recovery(ez.repl.Recovery):
    @override
    def bundledFirmware(self) -> str:
        return self.bundledFirmwareInDefaultPath('lm3s811', 'release.axf')
    @override
    def attemptAutoRecovery(self) -> bool:
        return False
    @override
    def negotiateRecovery(self) -> bool:
        return False

ez.repl.register({
    ez.repl.IOSerializer: lambda: ez.repl.serialize.Stream32(),
    ez.repl.Recovery: lambda: LM3S811Recovery(),
    ez.repl.Session: lambda: ez.repl.Session(deviceId='lm3s811'),
    ez.repl.Transport: lambda: LM3S811Transport(),
})

@inject.params(recovery=ez.repl.Recovery)
def accept(id: str, recovery: LM3S811Recovery):
    if id.startswith('lm3s811'):
        return recovery.bundledFirmware()
    return None

@inject.params(session=ez.repl.Session, stream=ez.repl.IOSerializer)
def connect(firmware: str, host: ez_clang_api.Host,
            lm3s811: ez_clang_api.Device, session: ez.repl.Session,
            stream: ez.repl.serialize.Stream32) -> ez.repl.IOSerializer:
    session.host = host # FIXME: formatExpressionResult()
    lm3s811.name = session.deviceId
    lm3s811.transport = "qemu -> lm3s811" # TODO: Rename property to 'description' or so
    stream.endian = 'little'
    stream.verbose = 'rpc_bytes' in host.verbose()
    stream.open(session.connect(firmware))
    return stream

@inject.params(session=ez.repl.Session)
def setup(stream: ez.repl.IOSerializer, host: ez_clang_api.Host,
          lm3s811: ez_clang_api.Device, session: ez.repl.Session):
    # Read setup message
    setup = ez.repl.endpoints.SetupMessageDecoder(stream.receive())

    # Start configuring device
    lm3s811.setCodeBuffer(setup.codeBufferAddr, setup.codeBufferSize)
    for symbol in setup.endpoints:
        if not session.relocateEndpoint(symbol, setup.endpoints[symbol]):
            ez.io.warning(f"No endpoint for bootstrap function {symbol} " +
                          f"(0x{setup.endpoints[symbol]:08x})")

    if session.endpoints['lookup'].addr == 0:
        raise ez.repl.DeviceProtocolException("Missing bootstrap symbol " +
                                              session.endpoints['lookup'].symbol)

    # TODO: Include debug/release build and built-in features in setup message
    lm3s811.debug = True
    lm3s811.features = [ "-lc" ]

    # Hardware specific infos can be hardcoded
    lm3s811.triple = "arm-none-eabi"
    lm3s811.cpu = "cortex-m3"
    lm3s811.page_size = 64
    lm3s811.default_alignment = 16

    # Extract default paths from the reference compiler
    gcc = ez.util.package.findCompiler("toolchain-gccarmnoneeabi")

    # If the firmware has libc builtin, we need matching includes
    if "-lc" in lm3s811.features:
        lm3s811.header_search_paths += gcc.parseHeaderSearchPaths(["-mcpu=cortex-m3"])

    # Compiler flags and defines
    lm3s811.flags += [ "-target", "arm-none-eabi", "-mcpu=cortex-m3", "-mthumb",
                       "-march=armv7m", "-mfpu=none", "-mfloat-abi=soft" ]
    lm3s811.flags += [ "-Og", "-g2", "-ggdb2" ] if lm3s811.debug else [ "-Os", "-g0" ]
    lm3s811.flags += [ "-fno-rtti", "-fno-exceptions", "-std=gnu++17", "-nostdlib",
                       "-ffunction-sections", "-fdata-sections",
                       "-fno-threadsafe-statics" ]
    lm3s811.flags += [ "-DDEBUG" ] if lm3s811.debug else [ "-DNDEBUG" ]

    return host.addDevice(lm3s811)

@inject.params(session=ez.repl.Session)
def call(endpoint: str, data: dict, session: ez.repl.Session) -> dict:
    return session.call(endpoint, data)

@inject.params(session=ez.repl.Session, transport=ez.repl.Transport)
def disconnect(session: ez.repl.Session, transport: LM3S811Transport):
    res = session.disconnect()
    transport.shutdown()
    return res

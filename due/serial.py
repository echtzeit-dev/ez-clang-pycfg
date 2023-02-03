import ez.io
import ez_clang_api
if ez_clang_api.Host.debugPython(__debug__):
    import debugpy
    debugpy.listen(('0.0.0.0', 5678))
    ez.io.note("Python API waiting for debugger. Attach to 0.0.0.0:5678 to proceed.")
    debugpy.wait_for_client()
    debugpy.breakpoint()

import inject
from overrides import override

import ez.repl
import ez.repl.endpoints
import ez.repl.serial
import ez.repl.serialize
import ez.util
import ez.util.package

from serial.tools.list_ports_linux import SysFS

class DueTransport(ez.repl.serial.Transport):
    @override
    def handshake(self):
        assert self.stream, "Connect serial stream first"
        magic = "01 23 57 bd bd 57 23 01"
        try:
            self.awaitToken(bytes.fromhex(magic))
        except ez.repl.HandshakeFailedException as ex:
            ex.message = f"Did not receive handshake sequence '{magic}'"
            raise ex

class DueRecovery(ez.repl.serial.Recovery):
    @override
    def bundledFirmware(self) -> str:
        return self.bundledFirmwareInDefaultPath('due', 'firmware.bin')

    @inject.params(transport=ez.repl.Transport)
    @override(check_signature=False)
    def replaceDeviceFirmware(self, image: str, transport: DueTransport):
        self.hardReset(transport.info)
        tool = ez.util.package.findBossac()
        cmd = [ tool, "--info", "--port", transport.info.device, "--write",
                      "--reset", "--erase", "-U", "false", "--boot", image ]
        cmd.append("--debug") if self.verbose else None

        import subprocess
        try:
            ez.io.note("Uploading new firmware")
            subprocess.run(cmd, capture_output=True, check=True)
        except subprocess.CalledProcessError as ex:
            raise ez.repl.ReplaceFirmwareException(ex.returncode, cmd,
                                                   ex.output.decode())
        return transport.awaitReconnect()

ez.repl.register({
    ez.repl.Recovery: lambda: DueRecovery(),
    ez.repl.Session: lambda: ez.repl.Session(deviceId='due'),
    ez.repl.IOSerializer: lambda: ez.repl.serialize.Stream32(),
    ez.repl.Transport: lambda: DueTransport(),
})

def accept(info: SysFS) -> SysFS:
    if info.manufacturer and info.manufacturer.startswith('Arduino'):
        if info.product and info.product.startswith('Arduino Due'):
            return info
        if info.hwid and info.hwid.startswith('USB VID:PID=2341:003D'):
            return info
    return None

@inject.params(session=ez.repl.Session, stream=ez.repl.IOSerializer)
def connect(info: SysFS, host: ez_clang_api.Host, due: ez_clang_api.Device,
            session: ez.repl.Session, stream: ez.repl.serialize.Stream32
            ) -> ez.repl.IOSerializer:
    session.host = host # FIXME: formatExpressionResult()
    due.name = session.deviceId
    due.transport = info.device + " -> Arduino Due" # TODO: Rename property to 'description' or so
    stream.endian = 'little'
    stream.verbose = 'rpc_bytes' in host.verbose()
    stream.open(session.connect(info))
    return stream

@inject.params(session=ez.repl.Session)
def setup(stream: ez.repl.IOSerializer, host: ez_clang_api.Host,
          due: ez_clang_api.Device, session: ez.repl.Session):
    # Read setup message
    setup = ez.repl.endpoints.SetupMessageDecoder(stream.receive())

    # Start configuring device
    due.setCodeBuffer(setup.codeBufferAddr, setup.codeBufferSize)
    for symbol in setup.endpoints:
        if not session.relocateEndpoint(symbol, setup.endpoints[symbol]):
            ez.io.warning(f"No endpoint for bootstrap function {symbol} " +
                          f"(0x{setup.endpoints[symbol]:08x})")

    if session.endpoints['lookup'].addr == 0:
        raise ez.repl.DeviceProtocolException("Missing bootstrap symbol " +
                                              session.endpoints['lookup'].symbol)

    # TODO: Include debug/release build and built-in features in setup message
    due.debug = True
    due.features = [ "-lc", "framework-arduino-sam" ]

    # Hardware specific infos can be hardcoded
    due.triple = "arm-none-eabi"
    due.cpu = "cortex-m3"
    due.page_size = 256
    due.default_alignment = 32

    # Extract default paths from the reference compiler
    gcc = ez.util.package.findCompiler("toolchain-gccarmnoneeabi@1.70201.0")

    # If the firmware has libc builtin, we need matching includes
    if "-lc" in due.features:
        due.header_search_paths += gcc.parseHeaderSearchPaths(["-mcpu=cortex-m3"])

    # If the firmware has Arduino builtin, we only need matching includes
    if "framework-arduino-sam" in due.features:
        sam = ez.util.package.findLibrary("framework-arduino-sam")
        due.header_search_paths += sam.getHeaderSearchPaths()

    # Compiler flags
    due.flags += [ "-target", "arm-none-eabi", "-mcpu=cortex-m3", "-mthumb",
                    "-march=armv7m", "-mfpu=none", "-mfloat-abi=soft" ]
    due.flags += [ "-Og", "-g2", "-ggdb2" ] if due.debug else [ "-Os", "-g0" ]
    due.flags += [ "-fno-rtti", "-fno-exceptions", "-std=gnu++17", "-nostdlib",
                    "-ffunction-sections", "-fdata-sections",
                    "-fno-threadsafe-statics" ]

    # Compiler defines
    due.flags += [ "-DDEBUG" ] if due.debug else [ "-DNDEBUG" ]
    due.flags += [
        "-D__SAM3X8E__",
        "-DARDUINO_SAM_DUE", "-DARDUINO_ARCH_SAM", "-DARDUINO=10805",
        "-DF_CPU=84000000L",
    ]

    return host.addDevice(due)

@inject.params(session=ez.repl.Session)
def call(endpoint: str, data: dict, session: ez.repl.Session) -> dict:
    return session.call(endpoint, data)

@inject.params(session=ez.repl.Session)
def disconnect(session: ez.repl.Session):
    return session.disconnect()

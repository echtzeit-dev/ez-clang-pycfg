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

import ez.repl
import ez.repl.endpoints
import ez.repl.serial
import ez.repl.serialize
import ez.util
import ez.util.package

from overrides import override
from serial.tools.list_ports_linux import SysFS

class MetroTransport(ez.repl.serial.Transport):
    @override
    def handshake(self):
        assert self.stream, "Connect serial stream first"
        magic = "01 23 57 bd bd 57 23 01"
        with ez.util.timeout(self.timeout, "Connect attempt"):
            self.stream.write(bytes.fromhex(magic))
        try:
            self.awaitToken(bytes.fromhex(magic))
        except ez.repl.HandshakeFailedException as ex:
            ex.message = f"Did not receive handshake sequence '{magic}'"
            raise ex

class MetroRecovery(ez.repl.serial.Recovery):
    @override
    def bundledFirmware(self) -> str:
        return self.bundledFirmwareInDefaultPath('adafruit_metro_m0', 'firmware.bin')

    @inject.params(transport=ez.repl.Transport)
    @override(check_signature=False)
    def replaceDeviceFirmware(self, image: str, transport: MetroTransport):
        self.hardReset(transport.info)
        tool = ez.util.package.findBossac()
        cmd = [ tool, "--info", "--port", transport.info.device, "--write",
                      "--reset", "--erase", "-U", "true", image ]
        cmd.append("--debug") if self.verbose else None

        import subprocess
        try:
            ez.io.note("Uploading new firmware")
            subprocess.run(cmd, capture_output=True, check=True)
        except subprocess.CalledProcessError as ex:
            raise ez.repl.ReplaceFirmwareException(ex.returncode, cmd,
                                                   ex.output.decode())

        # FIXME: Make sure the device finished booting before sending more data.
        #
        # This looks like a bug. It appeared first time, when the long-blink
        # was introduced as the reboot inidicator. This blocks the Arduino
        # setup() function for a bit.
        #
        # If the delay here is shorter than the boot time, the handshake
        # sequence gets duplicated into the new stream somehow:
        #
        #   ez.repl.OperationFailedException: Disconnect failed.
        #   Message header invalid. All values must be in 32-bit range.
        #   Received bytes interpretation:
        #     Length:  01 23 57 BD BD 57 23 01
        #     Opcode:  01 23 57 BD BD 57 23 01
        #     SeqID:   20 00 00 00 00 00 00 00
        #     TagAddr: 01 00 00 00 00 00 00 00
        #
        # Not sure why it happens or how to prevent it. The delay workaround is
        # annoying, but it works for now. TeensyLC shows the same symptom,
        # Arduino Due doesn't.
        from time import sleep
        sleep(3)

        return transport.awaitReconnect()

ez.repl.register({
    ez.repl.Recovery: lambda: MetroRecovery(),
    ez.repl.Session: lambda: ez.repl.Session('adafruit_metro_m0'),
    ez.repl.IOSerializer: lambda: ez.repl.serialize.Stream32(),
    ez.repl.Transport: lambda: MetroTransport(),
})

def accept(info: SysFS) -> SysFS:
    if info.manufacturer and info.manufacturer.startswith('Adafruit'):
        if info.product and info.product.startswith('Metro M0'):
            return info
        if info.hwid and info.hwid.startswith('USB VID:PID=239A:8013'):
            return info
    return None

@inject.params(session=ez.repl.Session, stream=ez.repl.IOSerializer)
def connect(info: SysFS, host: ez_clang_api.Host, m0: ez_clang_api.Device,
            session: ez.repl.Session, stream: ez.repl.serialize.Stream32
            ) -> ez.repl.IOSerializer:
    session.host = host # FIXME: formatExpressionResult()
    m0.name = "m0"
    m0.transport = info.device + " -> Adafruit Metro M0" # TODO: Rename property to 'description' or so
    stream.endian = 'little'
    stream.verbose = 'rpc_bytes' in host.verbose()
    stream.open(session.connect(info))
    return stream

@inject.params(session=ez.repl.Session)
def setup(stream: ez.repl.IOSerializer, host: ez_clang_api.Host,
          m0: ez_clang_api.Device, session: ez.repl.Session):
    # Read setup message
    setup = ez.repl.endpoints.SetupMessageDecoder(stream.receive())

    # Start configuring device
    m0.setCodeBuffer(setup.codeBufferAddr, setup.codeBufferSize)
    for symbol in setup.endpoints:
        if not session.relocateEndpoint(symbol, setup.endpoints[symbol]):
            ez.io.warning(f"No endpoint for bootstrap function {symbol} " +
                          f"(0x{setup.endpoints[symbol]:08x})")

    if session.endpoints['lookup'].addr == 0:
        raise ez.repl.DeviceProtocolException("Missing bootstrap symbol " +
                                              session.endpoints['lookup'].symbol)

    # TODO: Include debug/release build and built-in features in setup message
    m0.debug = True
    m0.features = [ "-lc" ]

    # Hardware specific infos can be hardcoded
    m0.triple = "arm-none-eabi"
    m0.cpu = "cortex-m0plus"
    m0.page_size = 256
    m0.default_alignment = 32

    # Extract default paths from the reference compiler
    gcc = ez.util.package.findCompiler("toolchain-gccarmnoneeabi@1.70201.0")

    # If the firmware has libc builtin, we need matching includes
    if "-lc" in m0.features:
        m0.header_search_paths += gcc.parseHeaderSearchPaths(["-mcpu=cortex-m0plus"])

    # Compiler flags
    m0.flags += [ "-target", "arm-none-eabi", "-mcpu=cortex-m0plus", "-mthumb",
                    "-march=armv6", "-mfpu=none", "-mfloat-abi=soft" ]
    m0.flags += [ "-Og", "-g2", "-ggdb2" ] if m0.debug else [ "-Os", "-g0" ]
    m0.flags += [ "-fno-rtti", "-fno-exceptions", "-std=gnu++17", "-nostdlib",
                    "-ffunction-sections", "-fdata-sections",
                    "-fno-threadsafe-statics" ]

    # Compiler defines
    m0.flags += [ "-DDEBUG" ] if m0.debug else [ "-DNDEBUG" ]
    m0.flags += [
        "-D__SAM3X8E__",
        "-DARDUINO_SAM_DUE", "-DARDUINO_ARCH_SAM", "-DARDUINO=10805",
        "-DF_CPU=84000000L",
    ]

    return host.addDevice(m0)

@inject.params(session=ez.repl.Session)
def call(endpoint: str, data: dict, session: ez.repl.Session) -> dict:
    return session.call(endpoint, data)

@inject.params(session=ez.repl.Session)
def disconnect(session: ez.repl.Session):
    return session.disconnect()

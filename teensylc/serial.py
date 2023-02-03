import ez.io
import ez_clang_api
if ez_clang_api.Host.debugPython(__debug__):
    import debugpy
    debugpy.listen(('0.0.0.0', 5678))
    ez.io.note("Python API waiting for debugger. Attach to 0.0.0.0:5678 to proceed.")
    debugpy.wait_for_client()
    debugpy.breakpoint()

import inject
import subprocess

import ez.repl
import ez.repl.endpoints
import ez.repl.serial
import ez.repl.serialize
import ez.util
import ez.util.package

from serial import SerialException
from serial.tools.list_ports_linux import SysFS
from overrides import override

class TeensyTransport(ez.repl.serial.Transport):
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

class TeensyRecovery(ez.repl.serial.Recovery):
    @override
    def bundledFirmware(self) -> str:
        return self.bundledFirmwareInDefaultPath('teensylc', 'firmware.hex')

    @override(check_signature=False)
    def hardReset(self, info: SysFS):
        # This seems to have the same effect as teensy_reboot -s
        # The device disconnects and reconnects as hid-generic (and not cdc_acm)
        from serial import Serial as BuiltinSerial
        with BuiltinSerial(info.device, 134, write_timeout=4, timeout=4):
            ez.io.note("Forcing hard-reset")

    @inject.params(transport=ez.repl.Transport)
    @override(check_signature=False)
    def negotiateRecovery(self, transport: TeensyTransport) -> bool:
        # When pressing the reset button on the TeensyLC board, the device comes
        # back as HID (and not CDC-ACM as we'd need for serial communication).
        # Thus, we skip the manual reboot step for this device. It won't help.
        try:
            if self.attemptReplaceFirmware(transport):
                if self.awaitHandshake():
                    return True
        except SerialException as ex:
            ez.io.error(str(ex))
        except ez.io.UserInterruptException as ex:
            ez.io.error(str(ex))
        return False

    @inject.params(transport=ez.repl.Transport)
    @override(check_signature=False)
    def replaceDeviceFirmware(self, image: str, transport: TeensyTransport) -> SysFS:
        # Looks like the teensy_loader_cli does reset the device if necessary
        #try:
        #    self.hardReset(transport.info)
        #except:
        #    pass # Reset may fail if device disconnected already

        tool = ez.util.package.findTeensyTool('teensy_loader_cli')
        cmd = [tool, '-mmcu=mkl26z64', '-w', '-s', '-v', image]
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
        # Not sure why or how to prevent this. The delay workaround is annoying,
        # but it works for now. MetroM0 shows the same symptom, Due doesn't.
        from time import sleep
        sleep(3)

        return transport.awaitReconnect()

ez.repl.register({
    ez.repl.IOSerializer: lambda: ez.repl.serialize.Stream32(),
    ez.repl.Recovery: lambda: TeensyRecovery(),
    ez.repl.Session: lambda: ez.repl.Session(deviceId='teensylc'),
    ez.repl.Transport: lambda: TeensyTransport(),
})

def accept(info: SysFS) -> SysFS:
    if info.manufacturer and info.manufacturer.startswith('Teensyduino'):
        if info.hwid and info.hwid.startswith('USB VID:PID=16C0:0483'):
            return info
    return None

@inject.params(session=ez.repl.Session, stream=ez.repl.IOSerializer)
def connect(info: SysFS, host: ez_clang_api.Host, teensy: ez_clang_api.Device,
            session: ez.repl.Session, stream: ez.repl.serialize.Stream32
            ) -> ez.repl.IOSerializer:
    session.host = host # FIXME: formatExpressionResult()
    teensy.name = session.deviceId
    teensy.transport = info.device + " -> Teensy LC" # TODO: Rename property to 'description' or so
    stream.endian = 'little'
    stream.verbose = 'rpc_bytes' in host.verbose()
    stream.open(session.connect(info))
    return stream

@inject.params(session=ez.repl.Session)
def setup(stream: ez.repl.IOSerializer, host: ez_clang_api.Host,
          teensy: ez_clang_api.Device, session: ez.repl.Session):
    # Read setup message
    setup = ez.repl.endpoints.SetupMessageDecoder(stream.receive())

    # Start configuring device
    teensy.setCodeBuffer(setup.codeBufferAddr, setup.codeBufferSize)
    for symbol in setup.endpoints:
        if not session.relocateEndpoint(symbol, setup.endpoints[symbol]):
            ez.io.warning(f"No endpoint for bootstrap function {symbol} " +
                          f"(0x{setup.endpoints[symbol]:08x})")

    if session.endpoints['lookup'].addr == 0:
        raise ez.repl.DeviceProtocolException("Missing bootstrap symbol " +
                                              session.endpoints['lookup'].symbol)

    # TODO: Include debug/release build and built-in features in setup message
    teensy.debug = True
    teensy.features = [ "-lc" ]

    # Hardware specific infos can be hardcoded
    teensy.triple = "arm-none-eabi"
    teensy.cpu = "cortex-m0plus"
    teensy.page_size = 256
    teensy.default_alignment = 32

    # Extract default paths from the reference compiler
    # TODO: PlatformIO GCC@1.50401.190816 error: target CPU does not support ARM mode
    gcc = ez.util.package.findCompiler("toolchain-gccarmnoneeabi")

    # If the firmware has libc builtin, we need matching includes
    if "-lc" in teensy.features:
        teensy.header_search_paths += gcc.parseHeaderSearchPaths(["-mcpu=cortex-m0"])

    # Compiler flags
    # TODO: -mno-unaligned-access
    teensy.flags += [ "-target", "arm-none-eabi", "-mcpu=cortex-m0plus", "-mthumb",
                      "-march=armv6", "-mfpu=none", "-mfloat-abi=soft" ]
    teensy.flags += [ "-Og", "-g2", "-ggdb2" ] if teensy.debug else [ "-Os", "-g0" ]
    teensy.flags += [ "-fno-rtti", "-fno-exceptions", "-std=gnu++17", "-nostdlib",
                      "-felide-constructors", "-ffunction-sections", "-fdata-sections" ]

    # Compiler defines
    teensy.flags += [ "-DDEBUG" ] if teensy.debug else [ "-DNDEBUG" ]
    teensy.flags += [
        "-D__MKL26Z64__", "-DUSB_SERIAL",
        "-DARDUINO_TEENSYLC", "-DARDUINO=10805", "-DTEENSYDUINO=156", "-DCORE_TEENSY",
        "-DF_CPU=48000000L" ]

    return host.addDevice(teensy)

@inject.params(session=ez.repl.Session)
def call(endpoint: str, data: dict, session: ez.repl.Session) -> dict:
    return session.call(endpoint, data)

@inject.params(session=ez.repl.Session)
def disconnect(session: ez.repl.Session):
    return session.disconnect()

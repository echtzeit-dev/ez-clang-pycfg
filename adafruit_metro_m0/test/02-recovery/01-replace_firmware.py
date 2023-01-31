# Test device firmware update

import ez.util.test
ez.util.test.add_module_roots(__file__)

import adafruit_metro_m0.serial
info = ez.util.test.lock_device(adafruit_metro_m0.serial.accept)

from overrides import override
class TestMetroRecovery(adafruit_metro_m0.serial.MetroRecovery):
    @override(check_signature=False)
    def negotiateRecovery(self) -> bool:
        # Don't ask the user, just restore bundled firmware
        super().replaceDeviceFirmware(super().bundledFirmware())
        super().awaitHandshake()
        return True

import ez.repl
ez.repl.register({
    ez.repl.Recovery: lambda: TestMetroRecovery(),
    ez.repl.Transport: lambda: adafruit_metro_m0.serial.MetroTransport(),
})

# Find broken firmware image in local test directory
import os
image = os.path.join(os.path.dirname(__file__), 'firmware-setup-magic-truncate.bin')
assert os.path.exists(image), "Failed to load test firmware with truncated setup magic"

# Flash broken firmware image:
#
#   > Found compatible device at /dev/ttyACM1
#   > Forcing hard-reset
#   > Await reconnect
#   > Detected device on new serial port /dev/ttyACM2
#   > Uploading new firmware
#   > Await reconnect
#   > Detected device on new serial port /dev/ttyACM1
#
import inject
inject.instance(ez.repl.Transport).reset(info)
infoNew = inject.instance(ez.repl.Recovery).replaceDeviceFirmware(image)

# Now connect() won't work. The device script is supposed to reach out to
# TestMetroRecovery, which flashes the bundled firmware:
#
#   > Connecting: waiting for device response.....
#   > Did not receive handshake sequence '01 23 57 bd bd 57 23 01'
#   > Actual received bytes were: 14 01 00 00
#   > Failed to connect device at '/dev/ttyACM1': adafruit_metro_m0
#   > Forcing hard-reset
#   > Await reconnect
#   > Detected device on new serial port /dev/ttyACM2
#   > Uploading new firmware
#   > Await reconnect
#   > Detected device on new serial port /dev/ttyACM1
#
import ez_clang_api
stream = adafruit_metro_m0.serial.connect(infoNew, ez_clang_api.Host(), ez_clang_api.Device())
assert stream.connected(), "Failed to update firmware on device"

# Consume and dump setup message
setup = stream.receive()
setup.readBytesRemaining()
setup.done()

# Disconnect to hand back the device in a well-defined state
adafruit_metro_m0.serial.disconnect()

# Test device firmware update

import ez.util.test
ez.util.test.add_module_roots(__file__)

import due.serial
info = ez.util.test.lock_device(due.serial.accept)

class TestDueRecovery(due.serial.DueRecovery):
    def negotiateRecovery(self) -> bool:
        # Don't ask the user, just restore bundled firmware
        super().replaceDeviceFirmware(super().bundledFirmware())
        super().awaitHandshake()
        return True

import ez.repl
ez.repl.register({
    ez.repl.Recovery: lambda: TestDueRecovery(),
    ez.repl.Transport: lambda: due.serial.DueTransport(),
})

# Find broken firmware image in local test directory
import os
image = os.path.join(os.path.dirname(__file__), 'firmware-setup-magic-truncate.bin')
assert os.path.exists(image), "Failed to load test firmware with truncated setup magic"

# Flash broken firmware image:
#
#   > Found compatible device at /dev/ttyACM0
#   > Forcing hard-reset
#   > Await reconnect
#   > Uploading new firmware
#   > Await reconnect
#
import inject
inject.instance(ez.repl.Transport).reset(info)
infoNew = inject.instance(ez.repl.Recovery).replaceDeviceFirmware(image)

# Now connect() won't work. The device script is supposed to reach out to
# TestDueRecovery, which flashes the bundled firmware:
#
#   > Connecting: waiting for device response.....
#   > Did not receive magic sequence '01 23 57 bd bd 57 23 01'
#   > Actual received bytes were: 01 23 57 bd
#   > Failed to connect device at '/dev/ttyACM0': due
#   > Forcing hard-reset
#   > Await reconnect
#   > Uploading new firmware
#   > Await reconnect
#   > Connecting: waiting for device response...
#
import ez_clang_api
stream = due.serial.connect(infoNew, ez_clang_api.Host(), ez_clang_api.Device())
assert stream.connected(), "Failed to update firmware on device"

# Consume and dump setup message
setup = stream.receive()
setup.readBytesRemaining()
setup.done()

# Disconnect to hand back the device in a well-defined state
due.serial.disconnect()

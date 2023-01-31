# Test device connect/disconnect

import ez.util.test
ez.util.test.add_module_roots(__file__)

import adafruit_metro_m0.serial
info = ez.util.test.lock_device(adafruit_metro_m0.serial.accept)

# Test device for checking mandatory properties
import ez_clang_api
testDevice1 = ez_clang_api.Device()

# Test host checks that it obtains the expected device
class TestHost(ez_clang_api.Host):
    def __init__(self):
        self.expectDevice = None
    def addDevice(self, dev: ez_clang_api.Device):
        assert dev == self.expectDevice, "Unexpected device instance"

testHost = TestHost()
testHost.expectDevice = testDevice1
stream = adafruit_metro_m0.serial.connect(info, testHost, testDevice1)
adafruit_metro_m0.serial.setup(stream, testHost, testDevice1)
adafruit_metro_m0.serial.disconnect()

# Reset state of all injected dependencies
ez.repl.register({})

# Connect a different device
testDevice2 = ez_clang_api.Device()
testHost.expectDevice = testDevice2
stream = adafruit_metro_m0.serial.connect(info, testHost, testDevice2)
adafruit_metro_m0.serial.setup(stream, testHost, testDevice2)
adafruit_metro_m0.serial.disconnect()

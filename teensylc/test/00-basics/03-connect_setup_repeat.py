# Test device connect/disconnect

import ez.util.test
ez.util.test.add_module_roots(__file__)

import teensylc.serial
info = ez.util.test.lock_device(teensylc.serial.accept)

# Test host checks that it obtains the expected device
import ez_clang_api
class TestHost(ez_clang_api.Host):
    def __init__(self):
        self.expectDevice = None
    def addDevice(self, dev: ez_clang_api.Device):
        assert dev == self.expectDevice, "Unexpected device instance"

testHost = TestHost()
testDevice1 = ez_clang_api.Device()
testHost.expectDevice = testDevice1
stream = teensylc.serial.connect(info, testHost, testDevice1)
teensylc.serial.setup(stream, testHost, testDevice1)
teensylc.serial.disconnect()

# Reset state of all injected dependencies
ez.repl.register({})

# Connect a different device
testDevice2 = ez_clang_api.Device()
testHost.expectDevice = testDevice2
stream = teensylc.serial.connect(info, testHost, testDevice2)
teensylc.serial.setup(stream, testHost, testDevice2)
teensylc.serial.disconnect()

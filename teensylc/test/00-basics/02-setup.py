# Test device setup

import ez.util.test
ez.util.test.add_module_roots(__file__)

import teensylc.serial
info = ez.util.test.lock_device(teensylc.serial.accept)

# A test device for checking mandatory properties
import ez_clang_api
testDevice = ez_clang_api.Device()

# Check that the device from connect() will be passed on here
class TestHost(ez_clang_api.Host):
    def addDevice(self, dev: ez_clang_api.Device):
        assert dev == testDevice, "Expected given testDevice instance"

testHost = TestHost()
stream = teensylc.serial.connect(info, testHost, testDevice)
assert stream.connected(), "Connection should be established"

teensylc.serial.setup(stream, testHost, testDevice)

# Check that setup() initialized mandatory properties
assert testDevice.name != None, "Failed to initialize mandatory property"
assert testDevice.triple != None, "Failed to initialize mandatory property"
assert testDevice.cpu != None, "Failed to initialize mandatory property"
assert testDevice.page_size != 0, "Failed to initialize mandatory property"
assert testDevice.default_alignment != 0, "Failed to initialize mandatory property"
assert len(testDevice.flags) > 0, "Failed to initialize mandatory property"
assert len(testDevice.header_search_paths) > 0, "Failed to initialize mandatory property"

teensylc.serial.disconnect()

# Test device setup

import ez.util.test
ez.util.test.add_module_roots(__file__)

import lm3s811.qemu
firmware = lm3s811.qemu.accept('lm3s811')

# A test device for checking mandatory properties
import ez_clang_api
testDevice = ez_clang_api.Device()

# Check that the device from connect() will be passed on here
class TestHost(ez_clang_api.Host):
    def addDevice(self, dev: ez_clang_api.Device):
        assert dev == testDevice, "Expected given testDevice instance"

testHost = TestHost()
stream = lm3s811.qemu.connect(firmware, testHost, testDevice)
assert stream.connected(), "Connection should be established"

lm3s811.qemu.setup(stream, testHost, testDevice)

# Check that setup() initialized mandatory properties
assert testDevice.name != None, "Failed to initialize mandatory property"
assert testDevice.triple != None, "Failed to initialize mandatory property"
assert testDevice.cpu != None, "Failed to initialize mandatory property"
assert testDevice.page_size != 0, "Failed to initialize mandatory property"
assert testDevice.default_alignment != 0, "Failed to initialize mandatory property"
assert len(testDevice.flags) > 0, "Failed to initialize mandatory property"
assert len(testDevice.header_search_paths) > 0, "Failed to initialize mandatory property"

lm3s811.qemu.disconnect()

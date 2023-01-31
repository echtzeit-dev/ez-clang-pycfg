# Test device setup

import ez.util.test
ez.util.test.add_module_roots(__file__)

# For standalone testing fill in the hostname:port of your remote host
import raspi32.socket
info = ez.util.test.lock_socket(raspi32.socket.accept, '192.168.1.107:10819')

# A test device for checking mandatory properties
import ez_clang_api
testDevice = ez_clang_api.Device()

# Check that the device from connect() will be passed on here
class TestHost(ez_clang_api.Host):
    def addDevice(self, dev: ez_clang_api.Device):
        assert dev == testDevice, "Expected given testDevice instance"

testHost = TestHost()
stream = raspi32.socket.connect(info, testHost, testDevice)
assert stream.connected(), "Connection should be established"

raspi32.socket.setup(stream, testHost, testDevice)

# Check that setup() initialized mandatory properties
assert testDevice.name != None, "Failed to initialize mandatory property"
assert testDevice.triple != None, "Failed to initialize mandatory property"
assert testDevice.cpu != None, "Failed to initialize mandatory property"
assert testDevice.page_size != 0, "Failed to initialize mandatory property"
assert testDevice.default_alignment != 0, "Failed to initialize mandatory property"
assert len(testDevice.flags) > 0, "Failed to initialize mandatory property"
assert len(testDevice.header_search_paths) > 0, "Failed to initialize mandatory property"

raspi32.socket.disconnect()

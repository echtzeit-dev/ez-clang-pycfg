# Test device connect/disconnect

import ez.util.test
ez.util.test.add_module_roots(__file__)

# For standalone testing fill in the hostname:port of your remote host
import raspi32.socket
info = ez.util.test.lock_socket(raspi32.socket.accept, '192.168.1.107:10819')

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
stream = raspi32.socket.connect(info, testHost, testDevice1)
raspi32.socket.setup(stream, testHost, testDevice1)
raspi32.socket.disconnect()

# Reset state of all injected dependencies
ez.repl.register({})

# Connect a different device
testDevice2 = ez_clang_api.Device()
testHost.expectDevice = testDevice2
stream = raspi32.socket.connect(info, testHost, testDevice2)
raspi32.socket.setup(stream, testHost, testDevice2)
raspi32.socket.disconnect()

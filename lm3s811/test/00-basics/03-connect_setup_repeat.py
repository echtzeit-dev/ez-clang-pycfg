# Test device connect/disconnect

import ez.util.test
ez.util.test.add_module_roots(__file__)

import lm3s811.qemu
firmware = lm3s811.qemu.accept('lm3s811')

# Test host checks that it obtains the expected device
import ez_clang_api
class TestHost(ez_clang_api.Host):
    def __init__(self):
        self.expectSubprocess = None
    def addDevice(self, proc: ez_clang_api.Device):
        assert proc == self.expectSubprocess, "Unexpected subprocess"
testHost = TestHost()

# Connect a first subprocess
testDevice1 = ez_clang_api.Device()
testHost.expectSubprocess = testDevice1
stream = lm3s811.qemu.connect(firmware, testHost, testDevice1)
lm3s811.qemu.setup(stream, testHost, testDevice1)
lm3s811.qemu.disconnect()

# Reset state of all injected dependencies
ez.repl.register({})

# Connect a different subprocess
testDevice2 = ez_clang_api.Device()
testHost.expectSubprocess = testDevice2
stream = lm3s811.qemu.connect(firmware, testHost, testDevice2)
lm3s811.qemu.setup(stream, testHost, testDevice2)
lm3s811.qemu.disconnect()

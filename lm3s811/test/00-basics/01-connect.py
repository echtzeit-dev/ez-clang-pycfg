# Test qemu connect/disconnect

import ez.util.test
ez.util.test.add_module_roots(__file__)

import lm3s811.qemu
firmware = lm3s811.qemu.accept('lm3s811')

# Test a raw handshake
import ez_clang_api
stream = lm3s811.qemu.connect(firmware, ez_clang_api.Host(), ez_clang_api.Device())
assert stream.connected(), "Connection should be established"

# Consume and dump setup message
setup = stream.receive()
setup.readBytesRemaining()
setup.done()

# Disconnect to hand back the device in a well-defined state
lm3s811.qemu.disconnect()
assert not stream.connected(), "Connection should be closed"

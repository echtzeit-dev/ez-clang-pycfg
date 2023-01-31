# Test physical device connection

import ez.util.test
ez.util.test.add_module_roots(__file__)

import due.serial
info = ez.util.test.lock_device(due.serial.accept)

# Test a raw handshake
import ez_clang_api
stream = due.serial.connect(info, ez_clang_api.Host(), ez_clang_api.Device())
assert stream.connected(), "Connection should be established"

# Consume and dump setup message
setup = stream.receive()
setup.readBytesRemaining()
setup.done()

# Disconnect to hand back the device in a well-defined state
due.serial.disconnect()
assert not stream.connected(), "Connection should be closed"

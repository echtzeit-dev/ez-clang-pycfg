# Test physical device connection

import ez.util.test
ez.util.test.add_module_roots(__file__)

import teensylc.serial
info = ez.util.test.lock_device(teensylc.serial.accept)

# Test a raw handshake
import ez.repl
import ez_clang_api
session = ez.repl.Session()
stream = teensylc.serial.connect(info, ez_clang_api.Host(), ez_clang_api.Device(), session)
assert stream.connected(), "Connection should be established"

# Consume and dump setup message
setup = stream.receive()
setup.readBytesRemaining()
setup.done()

# Disconnect to hand back the device in a well-defined state
session.disconnect()
assert not stream.connected(), "Connection should be closed"

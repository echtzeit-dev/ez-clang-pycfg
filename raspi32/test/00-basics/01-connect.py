# Test socket connect/disconnect

import ez.util.test
ez.util.test.add_module_roots(__file__)

# For standalone testing fill in the hostname:port of your remote host
import raspi32.socket
info = ez.util.test.lock_socket(raspi32.socket.accept, '192.168.1.107:10819')

# Test a raw handshake
import ez_clang_api
stream = raspi32.socket.connect(info, ez_clang_api.Host(), ez_clang_api.Device())
assert stream.connected(), "Connection should be established"

# Consume and dump setup message
setup = stream.receive()
setup.readBytesRemaining()
setup.done()

# Disconnect to hand back the device in a well-defined state
raspi32.socket.disconnect()
assert not stream.connected(), "Connection should be closed"

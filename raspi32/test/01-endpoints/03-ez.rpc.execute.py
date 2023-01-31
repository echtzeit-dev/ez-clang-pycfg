# Test device response for calls to the execute endpoint

# NOTE: We can only execute functions that don't take arguments and we don't
# have any such built-in function. Otherwise this test could be simpler!

import ez.util.test
ez.util.test.add_module_roots(__file__)

# For standalone testing fill in the hostname:port of your remote host
import raspi32.socket
info = ez.util.test.lock_socket(raspi32.socket.accept, '192.168.1.107:10819')

# Test device that records the code-buffer range and hands out allocations
import ez_clang_api
class TestDevice(ez_clang_api.Device):
    ALIGNMENT = 0x10    # 16-bit boundary
    def setCodeBuffer(self, address: int, size: int):
        self.mem = self.align(address)
        self.mem_end = self.mem + size
    def isPowerOf2(self, n):
        return (n & (n-1) == 0) and n != 0
    def align(self, n):
        assert self.isPowerOf2(self.ALIGNMENT), "Invalid alignment"
        return (n + self.ALIGNMENT - 1) & ~(self.ALIGNMENT - 1)
    def alloc(self, size: int):
        addr = self.mem
        self.mem = self.align(self.mem + size)
        assert self.mem < self.mem_end, "Out of memory"
        return addr

device = TestDevice()
testHost = ez_clang_api.Host()
stream = raspi32.socket.connect(info, ez_clang_api.Host(), device)
raspi32.socket.setup(stream, testHost, device)

# Scraped from ez-clang debug output running the expression `int a = 0;`
code = bytes.fromhex("81 b0 4d f8 04 0b 70 47")
code_addr = device.alloc(0x10)
data = bytes.fromhex("00 00 00 00")
data_addr = device.alloc(len(data))
assert data_addr - code_addr == 0x10, "Relative distance that must be maintained"

# Transfer code and data for the expression
raspi32.socket.call('commit', {
    code_addr: {'data': code, 'size': len(code)},
    data_addr: {'data': data, 'size': len(data)},
})

# Execute the expression once (we call into the auccessor byte, because this is Thumb code)
response = raspi32.socket.call('execute', {'addr': code_addr + 1})
assert response == {}, "Unexpected response from execute endpoint"

raspi32.socket.disconnect()

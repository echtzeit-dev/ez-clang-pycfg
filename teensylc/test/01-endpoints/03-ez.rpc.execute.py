# Test device response for calls to the execute endpoint

# NOTE: We can only execute functions that don't take arguments and we don't
# have any such built-in function. Otherwise this test could be simpler!

import ez.util.test
ez.util.test.add_module_roots(__file__)

import teensylc.serial
info = ez.util.test.lock_device(teensylc.serial.accept)

# Test device that records the code-buffer range and hands out allocations
# with 2-byte alignment
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
host = ez_clang_api.Host()
stream = teensylc.serial.connect(info, host, device)
teensylc.serial.setup(stream, host, device)

# Scraped from ez-clang debug output running the expression `int a = 0;`
code = bytes.fromhex("81 b0 00 90 01 b0 70 47")
code_addr = device.alloc(0x10)
data = bytes.fromhex("00 00 00 00")
data_addr = device.alloc(len(data))
assert data_addr - code_addr == 0x10, "Relative distance that must be maintained"

# Transfer code and data for the expression
teensylc.serial.call('commit', {
    code_addr: {'data': code, 'size': len(code)},
    data_addr: {'data': data, 'size': len(data)},
})

# Execute the expression once (we call into the successor byte, because this is Thumb code)
response = teensylc.serial.call('execute', {'addr': code_addr + 1})
assert response == {}, "Unexpected response from execute endpoint"

teensylc.serial.disconnect()

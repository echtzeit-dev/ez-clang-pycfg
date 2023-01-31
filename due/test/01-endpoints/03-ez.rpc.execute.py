# Test device response for calls to the commit endpoint

import ez.util.test
ez.util.test.add_module_roots(__file__)

import due.serial
info = ez.util.test.lock_device(due.serial.accept)

# Test device that records the code-buffer range and hands out raw allocations
import ez_clang_api
class TestDevice(ez_clang_api.Device):
    def alloc(self, bytes: int):
        addr = self.mem
        self.mem += bytes
        return addr
    def setCodeBuffer(self, address: int, size: int):
        self.mem = address
        self.mem_end = address + size

device = TestDevice()
host = ez_clang_api.Host()
stream = due.serial.connect(info, host, device)
due.serial.setup(stream, host, device)

# Scraped from ez-clang debug output running the expression `int a = 0;`
code = bytes.fromhex("81 b0 4d f8 04 0b 70 47")
data = bytes.fromhex("00 00 00 00")
code_addr = device.alloc(0x10)
data_addr = device.alloc(len(data))
assert data_addr - code_addr == 0x10, "Relative distance must be maintained"

# Transfer code and data for the expression
due.serial.call('commit', {
    code_addr: {'data': code, 'size': len(code)},
    data_addr: {'data': data, 'size': len(data)},
})

# Execute the expression once (we call into the successor byte, because this is Thumb code)
response = due.serial.call('execute', {'addr': code_addr + 1})
assert response == {}, "Unexpected response from execute endpoint"

due.serial.disconnect()

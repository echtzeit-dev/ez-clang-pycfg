# Test device response for calls to the commit endpoint

import ez.util.test
ez.util.test.add_module_roots(__file__)

import due.serial
info = ez.util.test.lock_device(due.serial.accept)

# Test device that records the code-buffer range and hands out unaligned
# allocations (c-strings can start at any memory address)
import ez_clang_api
class TestDevice(ez_clang_api.Device):
    def advance(self, dist):
        assert self.mem + dist < self.mem_end, "Out of memory"
        return self.mem + dist
    def alloc(self, bytes: int):
        addr = self.mem
        self.mem = self.advance(bytes)
        return addr
    def setCodeBuffer(self, address: int, size: int):
        assert address >= 0x20070000 and address < 0x20088000, "Code buffer must be in RAM"
        assert size > 0 and size < 0x18000, "RAM size is 96K"
        self.mem = address
        self.mem_end = address + size

device = TestDevice()
host = ez_clang_api.Host()
stream = due.serial.connect(info, host, device)
due.serial.setup(stream, host, device)

def isAligned(addr):
    return addr & 0x0f == 0 # 16-bit boundary

for i in range(2):
    # Allocate memory
    cstr_addr = device.alloc(9)
    if i == 0:
        assert isAligned(cstr_addr), "Code-buffer should be aligned"
    else:
        assert not isAligned(cstr_addr), "Unaligned in second iteration"

    # Fill in a zero-terminated string (len includes explicit terminator)
    cstr = b"endcoal\x00"
    response = due.serial.call('commit', {
        cstr_addr: {'data': cstr, 'size': len(cstr)},
    })
    assert response == {}, "Unexpected response from commit endpoint"

    # Read the entire string back via the memory.read.cstr endpoint
    response = due.serial.call('memory.read.cstr', { 'addr': cstr_addr })
    assert response['str'] == 'endcoal', \
        "Failed to read string back through memory.read.cstr"

    # Read back starting on the 4th byte
    response = due.serial.call('memory.read.cstr', { 'addr': cstr_addr + 3 })
    assert response['str'] == 'coal', \
        "Failed to read back tail of string"

due.serial.disconnect()

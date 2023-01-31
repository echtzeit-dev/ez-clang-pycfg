# Test device response for calls to the commit endpoint

import ez.util.test
ez.util.test.add_module_roots(__file__)

import teensylc.serial
info = ez.util.test.lock_device(teensylc.serial.accept)

# Test device that records the code-buffer range and hands out allocations
import ez_clang_api
class TestDevice(ez_clang_api.Device):
    def setCodeBuffer(self, address: int, size: int):
        assert address >= 0x1FFFF800 and address < 0x20001800, "Code buffer must be in RAM"
        assert size > 0 and size < 0x2000, "RAM size is 8K"
        self.mem = address
        self.mem_end = address + size
    def alloc(self, bytes: int):
        addr = self.mem
        self.mem += (bytes | 0x1f) + 1 # Advance to 32-bit boundary
        assert self.mem < self.mem_end, "Out of memory"
        return addr

device = TestDevice()
host = ez_clang_api.Host()
stream = teensylc.serial.connect(info, host, device)
teensylc.serial.setup(stream, host, device)

# Helper function to validate commits
def readBack(addr: int) -> str:
    return teensylc.serial.call('memory.read.cstr', { 'addr': addr })['str']

for _ in range(3):
    # Commit a simple c-string
    import codecs
    endcoal = b"endcoal\x00"
    endcoal_str = codecs.ascii_decode(endcoal)[0].strip('\x00')
    endcoal_addr = device.alloc(len(endcoal))
    response = teensylc.serial.call('commit', {
        endcoal_addr: {'data': endcoal, 'size': len(endcoal)},
    })
    assert response == {}, "Unexpected response from commit endpoint"
    assert readBack(endcoal_addr) == endcoal_str

    # Commit two c-strings and overwrite the previous commit
    import codecs
    endcars = b"endcars\x00"
    endcars_str = codecs.ascii_decode(endcars)[0].strip('\x00')
    endcars_addr = endcoal_addr
    endcoal_addr2 = device.alloc(len(endcoal))
    response = teensylc.serial.call('commit', {
        endcars_addr: {'data': endcars, 'size': len(endcars)},
        endcoal_addr2: {'data': endcoal, 'size': len(endcoal)},
    })
    assert response == {}, "Unexpected response from commit endpoint"
    assert readBack(endcars_addr) == endcars_str
    assert readBack(endcoal_addr) == endcars_str # Overwritten
    assert readBack(endcoal_addr2) == endcoal_str

# TODO: Commiting overlapping segments should fail!

teensylc.serial.disconnect()

# Test device response for calls to the commit endpoint

import ez.util.test
ez.util.test.add_module_roots(__file__)

import adafruit_metro_m0.serial
info = ez.util.test.lock_device(adafruit_metro_m0.serial.accept)

# Test device that records the code-buffer range and hands out allocations
import ez_clang_api
class TestDevice(ez_clang_api.Device):
    def setCodeBuffer(self, address: int, size: int):
        self.mem = address
        self.mem_end = address + size
    def alloc(self, bytes: int):
        addr = self.mem
        self.mem += (bytes | 0x1f) + 1 # Advance to 32-bit boundary
        assert self.mem < self.mem_end, "Out of memory"
        return addr

import ez_clang_api
device = TestDevice()
host = ez_clang_api.Host()
stream = adafruit_metro_m0.serial.connect(info, host, device)
adafruit_metro_m0.serial.setup(stream, host, device)

# Write a raw string into memory
cstr = b"endcoal\x00"
cstr_addr = device.alloc(80)
response = adafruit_metro_m0.serial.call('commit', {
    cstr_addr: {'data': cstr, 'size': len(cstr)},
})
assert response == {}, "Unexpected response from commit endpoint"

# Read the string back via the memory.read.cstr endpoint
import codecs
response = adafruit_metro_m0.serial.call('memory.read.cstr', { 'addr': cstr_addr })
assert response['str'] == codecs.ascii_decode(cstr)[0].strip('\x00'), \
       "Failed to read string back from memory.read.cstr"

adafruit_metro_m0.serial.disconnect()

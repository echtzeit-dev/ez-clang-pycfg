# TODO: This may break with new firmware builds!
# Test expression evaluation for command: auto str = "abcd"

import ez.util.test
ez.util.test.add_module_roots(__file__)

import due.serial
info = ez.util.test.lock_device(due.serial.accept)

# We will run pre-linked code on the device that must run from a fixed address.
# Check the code-buffer to make sure this memory range is available.
import ez_clang_api
class TestDevice(ez_clang_api.Device):
    def setCodeBuffer(self, address: int, size: int):
        assert 0x20073550 >= address, "Cannot map code to expected address"
        assert 0x20073590 < address + size, "Code/data exceeds memory range"

# We don't have the actual compiler at hand to tell us which types we're dealing
# with. Let's mimic the expected behavior for our specific type in Python.
class TestHost(ez_clang_api.Host):
    def getResultDeclTypeAsString(self):
        return "const char *"                   #< We know it's a raw c-string
    def formatResult(self, mem: bytes):
        addr = int.from_bytes(mem, 'little')    #< We know it's an address
        type = self.getResultDeclTypeAsString()
        return f"({type}) 0x{addr:08x}"

host = TestHost()
device = TestDevice()
stream = due.serial.connect(info, host, device)
due.serial.setup(stream, host, device)

# Lookup the function that returns expression results and check its address.
# If it doesn't match what we had in ez-clang, the code below is invalid!
symbol = "__ez_clang_report_value"
lookupResponse = due.serial.call('lookup', { symbol: 0 })
assert lookupResponse[symbol] == 0x8057d, "Re-compile code below"

# Scraped from ez-clang debug output running expression: auto str = "abcd"
data = bytes.fromhex("61 62 63 64 00 00 00 00 80 35 07 20")
code = bytes.fromhex("80 b5 6f 46 82 b0 01 90 43 f2 88 51 4e f2 40 20 "
                     "c2 f2 07 01 c0 f2 01 00 04 22 00 f0 02 f8 02 b0 "
                     "80 bd 40 f2 7d 5c c0 f2 08 0c 60 47")

# Transfer code and data for the expression
commitResponse = due.serial.call('commit', {
    0x20073550: {'data': code, 'size': len(code)},
    0x20073580: {'data': data, 'size': len(data)},
})

# Execute the expression and check that the expected result was dumped
# There is a number of things happening behind this execute call:
#   1. Resolve 'execute' endpoint with a 'lookup' request to the device
#   2. Send the 'execute' request
#   3. Read memory address of expression result from 'Result' response
#   4. Notice end of execution receiving 'Return' response
#   5. Let TestHost format expression result and provide type
#   6. Read back the c-string from the device:
#       a. Resolve 'memory.read.cstr' endpoint from the device (another 'lookup')
#       b. Send the 'memory.read.cstr' request
#       c. Decode the string value from 'Result' response
#   7. Concat and dump type, address and value
#
with ez.util.test.capture_stdout() as output:
    due.serial.call('execute', {'addr': 0x20073551})
    assert "(const char *) 0x20073580 abcd" in output()

due.serial.disconnect()

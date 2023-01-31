# Test expression evaluation for command: auto str = "abcd"

import ez.util.test
ez.util.test.add_module_roots(__file__)

import lm3s811.qemu
firmware = lm3s811.qemu.accept('lm3s811')

# We don't have the actual compiler at hand to tell us which types we're dealing
# with. Let's mimic the expected behavior for our specific type in Python.
import ez_clang_api
class TestHost(ez_clang_api.Host):
    def getResultDeclTypeAsString(self):
        return "const char *"                   #< We know it's a raw c-string
    def formatResult(self, mem: bytes):
        addr = int.from_bytes(mem, 'little')    #< We know it's an address
        type = self.getResultDeclTypeAsString()
        return f"({type}) 0x{addr:08x}"

testHost = TestHost()
testDevice = ez_clang_api.Device()
stream = lm3s811.qemu.connect(firmware, testHost, testDevice)
lm3s811.qemu.setup(stream, testHost, testDevice)

# Lookup the function that returns expression results and check its address.
# If it doesn't match what we had in ez-clang, the below code is invalid!
symbol = "__ez_clang_report_value"
lookupResponse = lm3s811.qemu.call('lookup', { symbol: 0 })
assert lookupResponse[symbol] == 0x4cf, "Re-compile code below"

# Scraped from ez-clang debug output running expression: auto str = "abcd"
data = bytes.fromhex("61 62 63 64 00 00 00 00 50 06 00 20")
code = bytes.fromhex("80 b5 6f 46 82 b0 01 90 40 f2 58 61 4e f2 40 20 "
                     "c2 f2 00 01 c0 f2 01 00 04 22 00 f0 02 f8 02 b0 "
                     "80 bd 40 f2 cf 4c c0 f2 00 0c 60 47")

# Transfer code and data for the expression
commitResponse = lm3s811.qemu.call('commit', {
    0x20000620: {'data': code, 'size': len(code)},
    0x20000650: {'data': data, 'size': len(data)},
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
    lm3s811.qemu.call('execute', {'addr': 0x20000621})
    assert "(const char *) 0x20000650 abcd" in output()

lm3s811.qemu.disconnect()

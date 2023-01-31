# Test device response for calls to the lookup endpoint

import ez.util.test
ez.util.test.add_module_roots(__file__)

import lm3s811.qemu
firmware = lm3s811.qemu.accept('lm3s811')

import ez_clang_api
testHost = ez_clang_api.Host()
testDevice = ez_clang_api.Device()
stream = lm3s811.qemu.connect(firmware, ez_clang_api.Host(), ez_clang_api.Device())
lm3s811.qemu.setup(stream, testHost, testDevice)

for _ in range(3):
    # Lookup the built-in function for returning expression results
    symbol1 = "__ez_clang_report_value"
    response = lm3s811.qemu.call('lookup', { symbol1: 0 })
    assert symbol1 in response, "Missing symbol1 in lookup response"
    assert response[symbol1] != 0, "Success should return a symbol address"

    # Lookup a function that doesn't exist
    symbol2 = "__ez_very_unlikely_that_there_actually_is_a_function_with_this_name"
    response = lm3s811.qemu.call('lookup', { symbol2: 0 })
    assert symbol2 in response, "Missing symbol2 in lookup response"
    assert response[symbol2] == 0, "Failure should return a NULL address"

    # Lookup both functions in a single batch
    response = lm3s811.qemu.call('lookup', { symbol1: 0, symbol2: 0 })
    assert symbol1 in response, "Missing symbol1 in lookup response"
    assert symbol2 in response, "Missing symbol2 in lookup response"
    assert response[symbol1] != 0, "Success should return a symbol address"
    assert response[symbol2] == 0, "Failure should return a NULL address"

lm3s811.qemu.disconnect()

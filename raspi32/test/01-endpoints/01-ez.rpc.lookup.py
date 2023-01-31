# Test device response for calls to the lookup endpoint

import ez.util.test
ez.util.test.add_module_roots(__file__)

# For standalone testing fill in the hostname:port of your remote host
import raspi32.socket
info = ez.util.test.lock_socket(raspi32.socket.accept, '192.168.1.107:10819')

import ez_clang_api
testHost = ez_clang_api.Host()
testDevice = ez_clang_api.Device()
stream = raspi32.socket.connect(info, ez_clang_api.Host(), ez_clang_api.Device())
raspi32.socket.setup(stream, testHost, testDevice)

for _ in range(3):
    # Lookup the built-in function for returning expression results
    symbol1 = "__ez_clang_report_value"
    response = raspi32.socket.call('lookup', { symbol1: 0 })
    assert symbol1 in response, "Missing symbol1 in lookup response"
    assert response[symbol1] != 0, "Success should return a symbol address"

    # Lookup a function that doesn't exist
    symbol2 = "__ez_very_unlikely_that_there_actually_is_a_function_with_this_name"
    response = raspi32.socket.call('lookup', { symbol2: 0 })
    assert symbol2 in response, "Missing symbol2 in lookup response"
    assert response[symbol2] == 0, "Failure should return a NULL address"

    # Lookup both functions in a single batch
    response = raspi32.socket.call('lookup', { symbol1: 0, symbol2: 0 })
    assert symbol1 in response, "Missing symbol1 in lookup response"
    assert symbol2 in response, "Missing symbol2 in lookup response"
    assert response[symbol1] != 0, "Success should return a symbol address"
    assert response[symbol2] == 0, "Failure should return a NULL address"

raspi32.socket.disconnect()

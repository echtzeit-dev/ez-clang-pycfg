# Test device response for calls to the lookup endpoint

import ez.util.test
ez.util.test.add_module_roots(__file__)

import due.serial
info = ez.util.test.lock_device(due.serial.accept)

import ez_clang_api
device = ez_clang_api.Device()
host = ez_clang_api.Host()
stream = due.serial.connect(info, host, device)
due.serial.setup(stream, host, device)

import time
for _ in range(3):
    # Lookup the built-in function for returning expression results
    symbol1 = "__ez_clang_report_value"
    response = due.serial.call('lookup', { symbol1: 0 })
    assert symbol1 in response, "Missing symbol1 in lookup response"
    assert response[symbol1] != 0, "Success should return a symbol address"

    # Lookup a function that doesn't exist
    symbol2 = "__ez_very_unlikely_that_there_actually_is_a_function_with_this_name"
    response = due.serial.call('lookup', { symbol2: 0 })
    assert symbol2 in response, "Missing symbol2 in lookup response"
    assert response[symbol2] == 0, "Failure should return a NULL address"

    # Lookup both functions in a single batch
    response = due.serial.call('lookup', { symbol1: 0, symbol2: 0 })
    assert symbol1 in response, "Missing symbol1 in lookup response"
    assert symbol2 in response, "Missing symbol2 in lookup response"
    assert response[symbol1] != 0, "Success should return a symbol address"
    assert response[symbol2] == 0, "Failure should return a NULL address"
    
    time.sleep(1)

due.serial.disconnect()

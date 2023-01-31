#!/usr/bin/python3

import inject
import os
import time
from overrides import override
from pathlib import Path

import ez.util.test
ez.util.test.add_module_roots(__file__)

# Avoid user input prompts during bulk testing
import ez.repl
import adafruit_metro_m0.serial

class NoInteractiveRecovery(adafruit_metro_m0.serial.MetroRecovery):
    def __init__(self):
        super().__init__()
        self.verbose = True
        self.firmwareUnderTest = super().bundledFirmware()
    def setCustomFirmware(self, file: str):
        if not os.path.exists(file):
            raise RuntimeError("Given firmware image doesn't exist: " + file)
        self.firmwareUnderTest = Path(args.firmware).resolve()
    @override
    def bundledFirmware(self) -> str:
        return self.firmwareUnderTest
    @override(check_signature=False)
    def negotiateRecovery(self):
        return False

ez.repl.register({
    ez.repl.Transport: lambda: adafruit_metro_m0.serial.MetroTransport(),
    ez.repl.Recovery: lambda: NoInteractiveRecovery(),
})

# Main entrypoint for test driver
if __name__ == '__main__':
    start = time.time()
    args = ez.util.test.parseCommandLineArgs()
    info = ez.util.test.lock_device(adafruit_metro_m0.serial.accept, args.connect)

    # Remember UID and check between tests to make sure we stick to one device
    deviceUID = info.serial_number
    print(f"Device unique identifier: {deviceUID}")

    # Wire up transport, so we can reset the firmware
    inject.instance(ez.repl.Transport).reset(info)

    # Override and upload firmware under test
    if not args.no_firmware:
        reco = inject.instance(ez.repl.Recovery)
        if args.firmware:
            reco.setCustomFirmware(args.firmware)
        print("Uploading firmware:", reco.bundledFirmware())
        with ez.util.test.capture_tool_output():
            info = reco.replaceDeviceFirmware(reco.bundledFirmware())

    # Discover and select test cases
    root = Path(os.path.dirname(__file__))
    print("Running tests from", root.resolve())
    categories = ez.util.test.categories(root)
    enabled, disabled = ez.util.test.discover(categories)
    selected = ez.util.test.select(enabled, args.filter, args.filter_out)
    print(f"Selecting {len(selected)} out of {len(enabled + disabled)} discovered tests")

    # Run actual tests one by one
    passed = []
    failed = []
    try:
        for path in selected:
            ez.repl.register({})
            if ez.util.test.run(path, args.timeout):
                passed.append(path)
                info = inject.instance(ez.repl.Transport).info
            else:
                failed.append(path)
                if not args.no_firmware:
                    with ez.util.test.capture_tool_output():
                        info = ez.util.test.lock_device(adafruit_metro_m0.serial.accept, args.connect)
                        inject.instance(ez.repl.Transport).reset(info)
                        reco = inject.instance(ez.repl.Recovery)
                        info = reco.replaceDeviceFirmware(reco.bundledFirmware())
            assert deviceUID == info.serial_number, "Connected device changed"
    finally:
        duration = time.time() - start
        ez.util.test.reportResults(len(enabled), len(disabled), len(selected),
                                   len(passed), len(failed), duration)

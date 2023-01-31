#!/usr/bin/python3

import inject
import os
import time
from overrides import override
from pathlib import Path

import ez.util.test
ez.util.test.add_module_roots(__file__)

import lm3s811.qemu
class LM3S811TestRecovery(lm3s811.qemu.LM3S811Recovery):
    def __init__(self):
        super().__init__()
        self.firmwareUnderTest = super().bundledFirmware()
    def setCustomFirmware(self, file: str):
        if not os.path.exists(file):
            raise RuntimeError("Given firmware image doesn't exist: " + file)
        self.firmwareUnderTest = file
    @override
    def bundledFirmware(self) -> str:
        return self.firmwareUnderTest

ez.repl.register({
    ez.repl.Recovery: lambda: LM3S811TestRecovery(),
})

if __name__ == '__main__':
    start = time.time()
    args = ez.util.test.parseCommandLineArgs()
    root = Path(os.path.dirname(__file__))

    # Override firmware under test
    recovery = inject.instance(ez.repl.Recovery)
    if args.firmware:
        recovery.setCustomFirmware(args.firmware)
    print(f"Test device image: {recovery.bundledFirmware()}")

    # Discover and select test cases
    root = Path(os.path.dirname(__file__))
    print("Running tests from", root.resolve())
    categories = ez.util.test.categories(root)
    enabled, disabled = ez.util.test.discover(categories)
    selected = ez.util.test.select(enabled, args.filter, args.filter_out)
    print(f"Selecting {len(selected)} out of {len(enabled + disabled)} discovered tests")

    passed = []
    failed = []
    try:
        for path in selected:
            ez.repl.register({})
            if ez.util.test.run(path, args.timeout):
                passed.append(path)
            else:
                # No need for recovery; each connect() launches a fresh subprocess
                failed.append(path)
    finally:
        duration = time.time() - start
        ez.util.test.reportResults(len(enabled), len(disabled), len(selected),
                                   len(passed), len(failed), duration)

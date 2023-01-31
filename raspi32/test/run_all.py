#!/usr/bin/python3

import inject
import os
import time
from overrides import override
from pathlib import Path

import ez.util.test
ez.util.test.add_module_roots(__file__)

import raspi32.socket
class NoInteractiveRecovery(raspi32.socket.Raspi32Recovery):
    def __init__(self):
        super().__init__()
        self.verbose = True
    @override(check_signature=False)
    def negotiateRecovery(self) -> bool:
        return False

ez.repl.register({
    ez.repl.Recovery: lambda: NoInteractiveRecovery(),
})

if __name__ == '__main__':
    start = time.time()
    args = ez.util.test.parseCommandLineArgs()
    if args.firmware:
        print("Cannot update firmware via socket connection on remote host: raspi32")
        exit(1)

    info = ez.util.test.lock_socket(raspi32.socket.accept, args.connect)
    print(f"Test device: {args.connect}")

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

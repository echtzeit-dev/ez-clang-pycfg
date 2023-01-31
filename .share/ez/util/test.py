import os
import re
import sys

from argparse import *
from contextlib import contextmanager
from io import StringIO
from pathlib import Path
from serial.tools.list_ports_linux import SysFS, comports
from typing import Callable, List, Pattern, Tuple

import ez.io
import ez.util

def regex_case_insensitive(arg) -> Pattern:
    try:
        return re.compile(arg, re.IGNORECASE)
    except re.error as reason:
        raise ArgumentError(arg, "Invalid regular expression: " + reason)

def parseCommandLineArgs():
    parser = ArgumentParser()
    parser.add_argument("--connect",
            help="Serial port of target device",
            type=str, default=None)
    parser.add_argument("--firmware",
            help="File name of the firmware image for the target device",
            type=str, default=None)
    parser.add_argument("--no-firmware",
            help="Don't upload a new firmware image to the target device",
            action="store_true", default=False)
    parser.add_argument("--timeout",
            help="Maximum duration for running a single test",
            type=int, default=30)
    parser.add_argument("--filter",
            metavar="REGEX",
            type=regex_case_insensitive,
            help="Only run tests with paths matching the given regular expression",
            default=".*")
    parser.add_argument("--filter-out",
            metavar="REGEX",
            type=regex_case_insensitive,
            help="Filter out tests with paths matching the given regular expression",
            default="^$")
    return parser.parse_args()

# Traverse parents until we find the root resource directory (the one that has
# a child called ".share"). In production ez-clang will do it for us.
def add_module_roots(test_file: str):
    test_root = os.path.dirname(test_file)
    while not os.path.exists(os.path.join(test_root, ".share")):
        test_root = os.path.abspath(os.path.join(test_root, ".."))
    if not test_root in sys.path:
        sys.path.append(test_root)

def categories(root: Path) -> List[Path]:
    return [d for d in root.iterdir() if d.is_dir() and not d.is_symlink()]

# TODO: Do we want to allow nesting?
def discover(categories: List[Path]) -> Tuple[List[Path], List[Path]]:
    tests = []
    disabled = []
    for cat in categories:
        for path in cat.iterdir():
            if path.is_file() and path.suffix == '.py':
                if path.name.endswith("_DISABLED.py"):
                    disabled.append(path)
                else:
                    tests.append(path)
    tests.sort(key=lambda path: str(path.resolve()))
    disabled.sort(key=lambda path: str(path.resolve()))
    return tests, disabled

def select(discovered: List[Path], include: Pattern, exclude: Pattern) -> List[Path]:
    return [t for t in discovered if
        include.search(str(t.resolve())) and not
        exclude.search(str(t.resolve()))]

def run(test: Path, timeout: int) -> bool:
    name = test.stem.strip('0123456789-')
    category = test.parent.name.strip('0123456789-')
    head = f"  [{category}] {name}"
    sys.stdout.write(head)
    sys.stdout.flush()

    path_str = str(test.resolve())
    with open(path_str) as test:
        code = test.read()

    import time
    test_start = time.time()
    try:
        with ez.util.timeout(timeout, "Test execution"):
            with capture_tool_output() as output:
                exec(compile(code, path_str, 'exec'), { '__file__': path_str })
    except:
        reportFailure(path_str, output['stdout'](), output['stderr']())
        return False

    duration = time.time() - test_start
    dots = max(0, 60 - len(head) - 2)
    sys.stdout.write(f" {'.'*dots} {duration:.2f}s\n")
    sys.stdout.flush()
    return True

def reportFailure(path: str, stdout: str, stderr: str):
    import sys
    import traceback
    sys.stderr.write("\n********************\n")
    sys.stderr.write("FAIL: " + path + "\n")
    sys.stderr.write(  "********************\n")
    if len(stdout) == 0 and len(stderr) == 0:
        sys.stderr.write("output: <empty>\n")
    if len(stdout) > 0:
        sys.stderr.write("stdout:" + stdout + "\n")
    if len(stderr) > 0:
        sys.stderr.write("stderr:" + stderr + "\n")
    sys.stderr.write(traceback.format_exc())
    sys.stderr.write(  "********************\n")
    sys.stdout.flush()

def reportResults(discovered: int, disabled: int, selected: int, passed: int, failed: int, duration: int):
    print(f"\nTesting Time: {duration:.2f}s")
    print(f"  Disabled: {disabled}")
    print(f"  Excluded: {discovered - selected}")
    print(f"  Failed  : {failed}")
    print(f"  Passed  : {passed}")
    print("\nSUCCESS" if selected == passed else "\nFAILED")

_testDeviceInfo = None
def lock_device(accept: Callable[[SysFS], bool], initialPort: SysFS = None) -> SysFS:
    global _testDeviceInfo
    if _testDeviceInfo:
        # Find (new) port for existing device
        for info in comports():
            if info.serial_number == _testDeviceInfo.serial_number:
                if info.device == _testDeviceInfo.device:
                    return accept(info) # Port didn't change
                else:
                    ez.io.note(f"Detected device on new serial port {info.device}")
                    _testDeviceInfo = info
                    return accept(info)
        raise RuntimeError("Failed to find new port for device")
    else:
        # Find matching port for device
        for info in comports():
            if initialPort in [None, info.device]:
                wrappedInfo = accept(info)
                if wrappedInfo:
                    ez.io.note(f"Found compatible device at {info.device}")
                    _testDeviceInfo = info
                    return wrappedInfo
        raise RuntimeError("Failed to find compatible device")

_testSocketInfo = None
def lock_socket(accept: Callable[[str], bool], networkAddress: str) -> Tuple[str, int]:
    global _testSocketInfo
    if not _testSocketInfo:
        from ez.repl.socket import Transport
        info = Transport.parseNetworkAddress(networkAddress)
        # TODO: Prepare executor for TCP ping
        #Transport.ping(info)
        _testSocketInfo = info
    return _testSocketInfo

# Backup stdout and stderr withing a scope and redirect it to a buffer.
# Restore the original streams when we leave the scope.
@contextmanager
def capture_tool_output():
    old_stdout = sys.stdout
    old_stderr = sys.stderr
    new_stdout = StringIO()
    new_stderr = StringIO()
    sys.stdout = new_stdout
    sys.stderr = new_stderr
    try:
        # Yield methods to access the buffers
        yield { 'stdout': new_stdout.getvalue, 'stderr': new_stderr.getvalue }
    finally:
        sys.stdout = old_stdout
        sys.stderr = old_stderr

# Backup stdout, redirect it to a buffer and restore when leaving the scope.
@contextmanager
def capture_stdout():
    out = StringIO()
    old = sys.stdout
    sys.stdout = out
    try:
        # Yield the method to access the buffer
        yield out.getvalue
    finally:
        sys.stdout = old

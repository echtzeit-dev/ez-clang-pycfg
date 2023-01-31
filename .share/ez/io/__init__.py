import inspect
import os
import sys

from ez_clang_api import Host

def _terminal_read_input(message: str):
    return input(message)

def _terminal_write_output(kind, *messages: object):
    # Get file/line where message was generated, when running ez-clang with --rpc-debug-python
    if Host.debugPython(__debug__):
        frame = inspect.currentframe().f_back.f_back
        file = os.path.abspath(inspect.getsourcefile(frame))
        line = inspect.getlineno(frame)
        print(f"[{kind}] {file}, line {line}:")
    for entry in messages:
        for msg in entry:
            print(msg)

_read_input = Host.readInput if Host.forwardIO() else _terminal_read_input
_write_output = Host.writeOutput if Host.forwardIO() else _terminal_write_output
_quiet: bool = False
_numWarnings: int = 0
_numErrors: int = 0

def debug(*messages: object):
    if not _quiet:
        _write_output('debug', messages)

def note(*messages: object):
    if not _quiet:
        _write_output('note', messages)

def warning(*messages: object):
    if not _quiet:
        _write_output('warning', messages)
    global _numWarnings
    _numWarnings += 1

def error(*messages: object):
    _write_output('error', messages)
    global _numErrors
    _numErrors += 1

def fatal(*messages: object):
    _write_output('fatal', messages)
    sys.exit(2)

def output(*messages: object):
    _write_output('jit', messages)

class UserInterruptException(Exception):
    pass

# TODO: Allow to reset this flag
_answered_all: bool = False

def ask(question: str, answers: str = 'ynqa'):
    global _answered_all
    if _answered_all and 'a' in answers:
        return True
    while True:
        answer = _read_input(question + " [" + "".join(answers) + "]? ")
        if answer in answers:
            if answer == 'y':
                return True
            if answer == 'n':
                print("Skipped by user")
                return False
            if answer == 'a':
                _answered_all = True
                return True
            if answer == 'q':
                raise UserInterruptException("Device recovery process cancelled by user")
        warning("Unrecognized input: '" + answer + "'. Please try again.")

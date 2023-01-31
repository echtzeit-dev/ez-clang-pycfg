import signal
from contextlib import contextmanager

class ScopeGuardException(Exception):
    pass

@contextmanager
def timeout(seconds: int, caption: str):
    if seconds is None:
      yield
    else:
      def timeout_handler(signum, frame):
          raise TimeoutError(f"{caption} cancelled after {seconds} seconds")
      signal.signal(signal.SIGALRM, timeout_handler)
      signal.alarm(seconds)
      try:
          yield
      finally:
          signal.alarm(0)

class ScopeGuard:
    def __init__(self, locked):
        self.locked = locked
    def __enter__(self):
        if self.locked:
            raise ScopeGuardException("Scope was locked on enter")
        else:
            self.locked = True
    def __exit__(self, type, value, traceback):
        if not self.locked:
            raise ScopeGuardException("Scope was unlocked before exit")
        else:
            self.locked = False


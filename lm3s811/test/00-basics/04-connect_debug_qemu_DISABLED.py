# Test that connect/disconnect works while debugging qemu 
#
# FIXME: This test requires the user to attach a debugger manually. It's fine
# for the standalone test, but we have to keep it DISABLED for bulk testing.
#
import ez.util.test
ez.util.test.add_module_roots(__file__)

import lm3s811.qemu
firmware = lm3s811.qemu.accept('lm3s811')

# Test mocks for ez_clang_api disable debugging by default.
# Force debugging
import ez_clang_api
ez_clang_api.Host.debugQemu = lambda: True

# If debugQemu() returns True, the connect() function is supposed to disable its
# timeout for fetching bytes from the inbound pipe. It may also print a note to
# the user, e.g.:
#
#       QEMU waiting for debugger. Attach to localhost:1234 to proceed.
#
import ez.repl
stream = lm3s811.qemu.connect(firmware, ez_clang_api.Host(), ez_clang_api.Device())

# Now, connect() waits indefinitely for Qemu to send the handshake sequence,
# while Qemu itself is blocking until we attach a debugger. We can do it, e.g.
# from the command-line with LLDB:
#
#   > cd /path/to/lm3s811
#   > lldb
#   (lldb) target create --arch thumb lm3s811/firmware.axf
#   Current executable set to '/path/to/lm3s811/firmware.axf' (arm).
#   (lldb) gdb-remote localhost:1234
#   Process 1 stopped
#   * thread #1, stop reason = signal SIGTRAP
#       frame #0: 0x0000074e firmware.axf`ResetHandler at lm3s811.c:209:25
#      206  extern unsigned long _bss;
#      207  extern unsigned long _ebss;
#      208 
#      -> 209  void ResetHandler(void) {
#      210    // Copy the data segment initializers from flash to SRAM. All addresses
#      211    // provided from linker scripts are 4-byte aligned.
#      212    unsigned long *Src = &_etext;
#   (lldb) c
#   Process 1 resuming
#
assert stream.connected(), "Connection should be established"

# Consume and dump setup message
setup = stream.receive()
setup.readBytesRemaining()
setup.done()

# After disconnect, LLDB should print something like:
#
#   Process 1 exited with status = -1 (0xffffffff) lost connection
#   (lldb) q
#
lm3s811.qemu.disconnect()
assert not stream.connected(), "Connection should be closed"

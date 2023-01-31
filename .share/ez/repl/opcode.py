Connect = 0
Disconnect = 1
Return = 2 # TODO: Switch IDs: Call <--> Return
Call = 3
Result = 4 # TODO: Eliminate async messages?
StdOut = 5 #

def name(opcode: int) -> str:
  if opcode > StdOut:
    return "Unknown opcode"
  else:
    return {
      Connect: 'Connect',
      Disconnect: 'Disconnect',
      Return: 'Return',
      Call: 'Call',
      Result: 'Result',
      StdOut: 'StdOut',
    }[opcode]

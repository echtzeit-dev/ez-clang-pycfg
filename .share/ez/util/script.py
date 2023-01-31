import ez_clang_api

class ContextSwitch:
    def __init__(self, inner):
        self.outer_context = None
        self.inner_context = inner
        self.inner_context['__callback_context__'] = self # Accessible from script
    def __enter__(self):
        if '__callback_context__' in globals():
            self.leave() # Prepare outbound callback from script
        else:
            self.enter() # About to call script endpoint
    def __exit__(self, type, value, traceback):
        if '__callback_context__' in globals():
            self.leave() # Done calling script endpoint
        else:
            self.enter() # Complete outbound callback from script
    def enter(self):
        self.outer_context = dict(globals())
        globals().clear()
        globals().update(self.inner_context)
    def leave(self):
        self.inner_context = dict(globals())
        globals().clear()
        globals().update(self.outer_context)

class Script:
    def accept(self, info) -> bool:
        with self.script_context:
            self.acceptedInfo = self.api['accept'](info)
            return True if self.acceptedInfo else False
    def connect(self, ez_clang: ez_clang_api.Host) -> bool:
        with self.script_context:
            device = ez_clang_api.Device()
            stream = self.api['connect'](self.acceptedInfo, ez_clang, device)
            if not stream:
                return False
            return self.api['setup'](stream, ez_clang, device)
    def disconnect(self) -> bool:
        with self.script_context:
            return self.api['disconnect']()
    def call(self, endpoint: str, input: dict) -> dict:
        with self.script_context:
            return self.api['call'](endpoint, input)

    def __init__(self, path: str, module: str):
        with open(path) as script:
            code = script.read()

        # We may have to parse many scripts before we find the correct one.
        # Let's give each of them a fresh context, so they don't pollute the
        # global one. We store it here in the script object to be able to
        # switch it back in whenever we call into an API function.
        context = {}
        context['__file__'] = path
        context['__name__'] = module
        self.script_context = ContextSwitch(context)
        exec(compile(code, path, 'exec'), context, None)

        # Fetch API functions for delegating calls
        self.api = {}
        for ep in [ 'accept', 'connect', 'setup', 'disconnect', 'call' ]:
            if not ep in context:
                raise AttributeError(f"Missing endpoint '{ep}()' in script: {path}")
            self.api[ep] = context[ep]

        # Will store the wrapped connectivity info that matches this script
        self.acceptedInfo = None

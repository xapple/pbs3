# Constants #
__version__     = "3.0.2"
__project_url__ = "https://github.com/xapple/pbs3"

# Modules #
import sys, os, re, warnings, functools, types, subprocess
from glob import glob as original_glob

# Python 3 hack #
IS_PY3 = sys.version_info[0] == 3
if IS_PY3: unicode = str

###############################################################################
class CommandNotFound(Exception): pass

class ErrorReturnCode(Exception):
    truncate_cap = 200

    def __init__(self, full_cmd, stdout, stderr, call_args):
        # Attributes #
        self.full_cmd  = full_cmd
        self.stdout    = stdout
        self.stderr    = stderr
        self.call_args = call_args
        # Check stdout #
        if self.stdout is None:
            out = "<redirected to '%s'>" % self.call_args['out']
            out = out.encode()
        else:
            out   = self.stdout[:self.truncate_cap]
            out_delta = len(self.stdout) - len(out)
            if out_delta:
                out += ("... (%d more, please see e.stdout)" % out_delta).encode()
        # Check stderr #
        if self.stderr is None:
            err = "<redirected to '%s'>" % self.call_args['err']
            err = err.encode()
        else:
            err   = self.stderr[:self.truncate_cap]
            err_delta = len(self.stderr) - len(err)
            if err_delta:
                err += ("... (%d more, please see e.stderr)" % err_delta).encode()
        # Build message #
        msg = "\n\nRan: %s\n\nSTDOUT:\n\n  %s\n\nSTDERR:\n\n  %s"
        msg = msg % (full_cmd, out.decode(), err.decode())
        # Call parent #
        super(ErrorReturnCode, self).__init__(msg)

rc_exc_regex = re.compile(r"ErrorReturnCode_(\d+)")
rc_exc_cache = {}

def get_rc_exc(rc):
    rc = int(rc)
    try:
        return rc_exc_cache[rc]
    except KeyError:
        pass
    name = "ErrorReturnCode_%d" % rc
    exc = type(name, (ErrorReturnCode,), {})
    rc_exc_cache[rc] = exc
    return exc

def which(program):
    def is_exe(file_path):
        return os.path.exists(file_path) and os.access(file_path, os.X_OK)
    file_path, file_name = os.path.split(program)
    if file_path:
        if is_exe(program): return program
    else:
        for path in os.environ["PATH"].split(os.pathsep):
            exe_file = os.path.join(path, program)
            if is_exe(exe_file):
                return exe_file
    return None

def resolve_program(program):
    """Our actual command might have a dash in it, but we can't call
    that from python (we have to use underscores), so we'll check
    if a dash version of our underscore command exists and use that
    if it does."""
    path = which(program)
    if not path:
        if "_" in program: path = which(program.replace("_", "-"))
        if not path: return None
    return path

def glob(arg):
    return original_glob(arg) or arg

###############################################################################
class RunningCommand(object):
    def __init__(self, command_ran, process, call_args, stdin=None):
        # Base attributes #
        self.command_ran = command_ran
        self.process = process
        self._stdout = None
        self._stderr = None
        self.call_args = call_args

        # We're running in the background, return self and let us lazily
        # evaluate.
        if self.call_args["bg"]: return

        # We're running this command as a with context, don't do anything
        # because nothing was started to run from Command.__call__
        if self.call_args["with"]: return

        # Run and block #
        if stdin: stdin = stdin.encode("utf8")
        self._stdout, self._stderr = self.process.communicate(stdin)
        self._handle_exit_code(self.process.wait())

    def __enter__(self):
        # We don't actually do anything here because anything that should
        # have been done or would have been done in the Command.__call__ call.
        # essentially all that has to happen is the command be pushed on
        # the prepend stack.
        pass

    def __exit__(self, typ, value, traceback):
        if self.call_args["with"] and Command._prepend_stack:
            Command._prepend_stack.pop()

    def __repr__(self):
        return "<RunningCommand %r, pid:%d, special_args:%r" % (
            self.command_ran, self.process.pid, self.call_args)

    def __str__(self):
        if IS_PY3: return self.__unicode__()
        else: return unicode(self).encode("utf8")

    def __unicode__(self):
        if self.process:
            if self.call_args["bg"]: self.wait()
            if self._stdout: return self.stdout
            else: return ""

    def __eq__(self, other):
        return unicode(self) == unicode(other)

    def __contains__(self, item):
        return item in str(self)

    def __getattr__(self, p):
        # Let these three attributes pass through to the Popen object
        if p in ("send_signal", "terminate", "kill"):
            if self.process: return getattr(self.process, p)
            else: raise AttributeError
        return getattr(unicode(self), p)

    def __long__(self):
        return long(str(self).strip())

    def __float__(self):
        return float(str(self).strip())

    def __int__(self):
        return int(str(self).strip())

    @property
    def stdout(self):
        if self.call_args["bg"]: self.wait()
        return self._stdout.decode("utf8", "replace")

    @property
    def stderr(self):
        if self.call_args["bg"]: self.wait()
        return self._stderr.decode("utf8", "replace")

    def wait(self):
        if self.process.returncode is not None: return
        self._stdout, self._stderr = self.process.communicate()
        self._handle_exit_code(self.process.wait())
        return str(self)

    def _handle_exit_code(self, rc):
        if rc not in self.call_args["ok_code"]:
            raise get_rc_exc(rc)(self.command_ran, self._stdout, self._stderr, self.call_args)

    def __len__(self):
        return len(str(self))

###############################################################################
class Command(object):
    _prepend_stack = []

    call_args = {
        "fg":         False,   # run command in foreground
        "bg":         False,   # run command in background
        "with":       False,   # prepend the command to every command after it
        "out":        None,    # redirect STDOUT
        "err":        None,    # redirect STDERR
        "err_to_out": None,    # redirect STDERR to STDOUT
        "in":         None,
        "env":        os.environ,
        "cwd":        None,
        # This is for commands that may have a different exit status than the
        # normal 0. This can either be an integer or a list/tuple of integers
        "ok_code": 0,
    }

    @classmethod
    def create(cls, program):
        path = resolve_program(program)
        if not path: raise CommandNotFound(program)
        return cls(path)

    def __init__(self, path):
        # Path to executable #
        self._path = path
        # Partial #
        self._partial            = False
        self._partial_baked_args = []
        self._partial_call_args  = {}

    def __getattribute__(self, name):
        # Convenience #
        getattribute = functools.partial(object.__getattribute__, self)
        if name.startswith("_"): return getattribute(name)
        if name == "bake":       return getattribute("bake")
        else:                    return getattribute("bake")(name)

    @staticmethod
    def _extract_call_args(kwargs):
        kwargs = kwargs.copy()
        call_args = Command.call_args.copy()
        for arg, default in call_args.items():
            key = "_" + arg
            if key in kwargs:
                call_args[arg] = kwargs[key]
                del kwargs[key]
        return call_args, kwargs

    def _format_arg(self, arg):
        if IS_PY3: arg = str(arg)
        else: arg = unicode(arg).encode("utf8")
        return arg

    def _compile_args(self, args, kwargs):
        processed_args = []

        # Aggregate positional args
        for arg in args:
            if isinstance(arg, (list, tuple)):
                if not arg:
                    message  = "Empty list passed as an argument to '%r'."
                    message += " If you're using glob.glob(), please use pbs.glob() instead."
                    warnings.warn(message % self.path, stacklevel=3)
                for sub_arg in arg: processed_args.append(self._format_arg(sub_arg))
            else: processed_args.append(self._format_arg(arg))

        # Aggregate the keyword arguments
        for k,v in kwargs.items():
            # We're passing a short arg as a kwarg, example:
            # cut(d="\t")
            if len(k) == 1:
                processed_args.append("-" + k)
                if v is not True: processed_args.append(self._format_arg(v))
            # we're doing a long arg
            else:
                k = k.replace("_", "-")
                if v is True: processed_args.append("--" + k)
                else: processed_args.append("--%s=%s" % (k, self._format_arg(v)))
        return processed_args

    def bake(self, *args, **kwargs):
        fn = Command(self._path)
        fn._partial = True
        call_args, kwargs = self._extract_call_args(kwargs)
        pruned_call_args = call_args
        for k,v in Command.call_args.items():
            try:
                if pruned_call_args[k] == v:
                    del pruned_call_args[k]
            except KeyError: continue
        fn._partial_call_args.update(self._partial_call_args)
        fn._partial_call_args.update(pruned_call_args)
        fn._partial_baked_args.extend(self._partial_baked_args)
        fn._partial_baked_args.extend(self._compile_args(args, kwargs))
        return fn

    def __str__(self):
        if IS_PY3: return self.__unicode__()
        else: return unicode(self).encode("utf-8")

    def __repr__(self):
        return str(self)

    def __unicode__(self):
        baked_args = " ".join(self._partial_baked_args)
        if baked_args: baked_args = " " + baked_args
        return self._path + baked_args

    def __eq__(self, other):
        try: return str(self) == str(other)
        except: return False

    def __enter__(self):
        Command._prepend_stack.append([self._path])

    def __exit__(self, typ, value, traceback):
        Command._prepend_stack.pop()

    def __call__(self, *args, **kwargs):
        kwargs = kwargs.copy()
        args = list(args)
        cmd = []

        # Aggregate any with contexts
        for prepend in self._prepend_stack: cmd.extend(prepend)

        cmd.append(self._path)

        call_args, kwargs = self._extract_call_args(kwargs)
        call_args.update(self._partial_call_args)

        # Here we normalize the ok_code to be something we can do
        # "if return_code in call_args["ok_code"]" on
        if not isinstance(call_args["ok_code"], (tuple, list)):
            call_args["ok_code"] = [call_args["ok_code"]]

        # Set pipe to None if we're outputting straight to CLI
        pipe = None if call_args["fg"] else subprocess.PIPE

        # Check if we're piping via composition
        stdin = pipe
        actual_stdin = None
        if args:
            first_arg = args.pop(0)
            if isinstance(first_arg, RunningCommand):
                # It makes sense that if the input pipe of a command is running
                # in the background, then this command should run in the
                # background as well
                if first_arg.call_args["bg"]:
                    call_args["bg"] = True
                    stdin = first_arg.process.stdout
                else:
                    actual_stdin = first_arg.stdout
            else: args.insert(0, first_arg)

        processed_args = self._compile_args(args, kwargs)

        # Makes sure our arguments are broken up correctly
        split_args = self._partial_baked_args + processed_args
        final_args = split_args

        cmd.extend(final_args)
        command_ran = " ".join(cmd)

        # With contexts shouldn't run at all yet, they prepend
        # to every command in the context
        if call_args["with"]:
            Command._prepend_stack.append(cmd)
            return RunningCommand(command_ran, None, call_args)

        # Stdin from string
        input = call_args["in"]
        if input:
            actual_stdin = input

        # Stdout redirection
        stdout = pipe
        out = call_args["out"]
        if out:
            if hasattr(out, "write"): stdout = out
            else: stdout = open(str(out), "w")

        # Stderr redirection
        stderr = pipe
        err = call_args["err"]

        if err:
            if hasattr(err, "write"): stderr = err
            else: stderr = open(str(err), "w")

        if call_args["err_to_out"]: stderr = subprocess.STDOUT

        # Leave shell=False
        process = subprocess.Popen(cmd, shell=False, env=call_args["env"],
            cwd=call_args["cwd"], stdin=stdin, stdout=stdout, stderr=stderr)

        return RunningCommand(command_ran, process, call_args, actual_stdin)

###############################################################################
class Environment(dict):
    """
    This class is used directly when we do a "from pbs import *". It allows
    lookups to names that aren't found in the global scope to be searched
    for as a program. For example, if "ls" isn't found in the program's
    scope, we consider it a system program and try to find it.
    """

    def __init__(self, *args, **kwargs):
        dict.__init__(self, *args, **kwargs)
        self["Command"]         = Command
        self["CommandNotFound"] = CommandNotFound
        self["ErrorReturnCode"] = ErrorReturnCode
        self["ARGV"]            = sys.argv[1:]
        for i, arg in enumerate(sys.argv):
            self["ARG%d" % i] = arg
        # This needs to be last
        self["env"] = os.environ

    def __setitem__(self, k, v):
        # Are we altering an environment variable?
        if "env" in self and k in self["env"]: self["env"][k] = v
        # No? Just setting a regular name
        else: dict.__setitem__(self, k, v)

    def __missing__(self, key):
        # This seems to happen in Python 3
        if key == "__path__":
            message  = "You cannot use the form 'from pbs import x' in Python 3."
            message += "Please use x = pbs.Command('x') instead."
            raise ImportError(message)

        # The only way we'd get to here is if we've tried to
        # import * from a repl. So, raise an exception, since
        # that's really the only sensible thing to do
        if key == "__all__":
            message  = "Cannot import * from pbs."
            message += "Please import pbs or import programs individually."
            raise ImportError(message)

        # If we end with "_" just go ahead and skip searching
        # our namespace for python stuff. This was mainly for the
        # command "id", which is a popular program for finding
        # if a user exists, but also a python function for getting
        # the address of an object. So can call the python
        # version by "id" and the program version with "id_"
        if not key.endswith("_"):
            # check if we're naming a dynamically generated ReturnCode exception
            try: return rc_exc_cache[key]
            except KeyError:
                m = rc_exc_regex.match(key)
                if m: return get_rc_exc(int(m.group(1)))

            # are we naming a command-line argument?
            if key.startswith("ARG"):
                return None

            # is it a built-in?
            try: return getattr(self["__builtins__"], key)
            except AttributeError: pass
        elif not key.startswith("_"): key = key.rstrip("_")

        # how about an environment variable?
        try: return os.environ[key]
        except KeyError: pass

        # is it a custom built-in?
        builtin = getattr(self, "b_" + key, None)
        if builtin: return builtin

        # it must be a command then
        return Command.create(key)

    def b_cd(self, path):
        os.chdir(path)

    def b_which(self, program):
        return which(program)

###############################################################################
class SelfWrapper(types.ModuleType):
    """
    This is a thin wrapper around THIS module (we patch sys.modules[__name__]).
    this is in the case that the user does a "from pbs import whatever"
    in other words, they only want to import certain programs, not the whole
    system PATH worth of commands. In this case, we just proxy the
    import lookup to our Environment class.
    """

    def __init__(self, self_module):
        """
        This is super ugly to have to copy attributes like this,
        but it seems to be the only way to make reload() behave
        nicely. If one makes these attributes dynamic lookups in
        __getattr__, reload sometimes chokes in weird ways.
        """
        for attr in ["__builtins__", "__doc__", "__name__", "__package__"]:
            setattr(self, attr, getattr(self_module, attr))

        self.self_module = self_module
        self.env = Environment(globals())

    def __getattr__(self, name):
        return self.env[name]

###############################################################################
self = sys.modules[__name__]
sys.modules[__name__] = SelfWrapper(self)

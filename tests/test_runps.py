#!/usr/bin/env python3
# -*- coding: utf8 -*-

# Built-in modules #
import sys, os, platform

# Internal modules #
import runps

# Third party modules #
import pytest

# Access internals via the underlying module to work around SelfWrapper #
_runps = runps.self_module
Command         = _runps.Command
CommandNotFound = _runps.CommandNotFound
ErrorReturnCode = _runps.ErrorReturnCode
which           = _runps.which
glob            = _runps.glob
resolve_program = _runps.resolve_program
get_rc_exc      = _runps.get_rc_exc

###############################################################################
# Helper to create a python Command bound to the current interpreter #
def python_cmd():
    return runps.Command(sys.executable)

# Helper to write a small python script and return its path #
def write_script(tmp_path, name, lines):
    path = str(tmp_path) + os.sep + name
    with open(path, 'w') as handle:
        handle.writelines(line + '\n' for line in lines)
    return path

###############################################################################
#                          Basic command execution                            #
###############################################################################
def test_basic_execution(tmp_path):
    """Running a simple command should return its stdout."""
    script = write_script(tmp_path, 'hello.py', [
        'print("hello world")',
    ])
    python = python_cmd()
    result = python(script)
    assert "hello world" in str(result)

def test_command_with_positional_args(tmp_path):
    """Positional arguments should be forwarded to the command."""
    script = write_script(tmp_path, 'echo_args.py', [
        'import sys',
        'print(" ".join(sys.argv[1:]))',
    ])
    python = python_cmd()
    result = python(script, "foo", "bar", "baz")
    assert "foo bar baz" in str(result)

def test_multiple_calls(tmp_path):
    """A Command object should be reusable for multiple calls."""
    script = write_script(tmp_path, 'echo.py', [
        'import sys',
        'print(sys.argv[1])',
    ])
    python = python_cmd()
    r1 = python(script, "first")
    r2 = python(script, "second")
    assert "first"  in str(r1)
    assert "second" in str(r2)

###############################################################################
#                            Keyword arguments                                #
###############################################################################
def test_short_keyword_argument(tmp_path):
    """Single-char kwargs should become short flags like -k value."""
    script = write_script(tmp_path, 'dump_args.py', [
        'import sys',
        'print("\\n".join(sys.argv[1:]))',
    ])
    python = python_cmd()
    result = python(script, d="\t")
    output = str(result)
    assert "-d" in output
    assert "\t" in output

def test_long_keyword_argument(tmp_path):
    """Multi-char kwargs should become long flags like --key=value."""
    script = write_script(tmp_path, 'dump_args.py', [
        'import sys',
        'print("\\n".join(sys.argv[1:]))',
    ])
    python = python_cmd()
    result = python(script, name="test")
    assert "--name=test" in str(result)

def test_boolean_short_keyword(tmp_path):
    """A short kwarg with True should produce just the flag, no value."""
    script = write_script(tmp_path, 'dump_args.py', [
        'import sys',
        'print("\\n".join(sys.argv[1:]))',
    ])
    python = python_cmd()
    result = python(script, v=True)
    output = str(result)
    assert "-v" in output

def test_boolean_long_keyword(tmp_path):
    """A long kwarg with True should produce --flag with no value."""
    script = write_script(tmp_path, 'dump_args.py', [
        'import sys',
        'print("\\n".join(sys.argv[1:]))',
    ])
    python = python_cmd()
    result = python(script, verbose=True)
    assert "--verbose" in str(result)

def test_underscore_to_dash_in_kwargs(tmp_path):
    """Underscores in long keyword arguments should be converted to dashes."""
    script = write_script(tmp_path, 'dump_args.py', [
        'import sys',
        'print("\\n".join(sys.argv[1:]))',
    ])
    python = python_cmd()
    result = python(script, no_create_home=True)
    assert "--no-create-home" in str(result)

###############################################################################
#                           Stdout and Stderr                                 #
###############################################################################
def test_stdout_property(tmp_path):
    """The .stdout property should return the captured standard output."""
    script = write_script(tmp_path, 'out.py', [
        'print("standard output")',
    ])
    python = python_cmd()
    result = python(script)
    assert result.stdout.strip() == "standard output"

def test_stderr_property(tmp_path):
    """The .stderr property should return the captured standard error."""
    script = write_script(tmp_path, 'err.py', [
        'import sys',
        'sys.stderr.write("standard error\\n")',
    ])
    python = python_cmd()
    result = python(script)
    assert "standard error" in result.stderr

###############################################################################
#                              Redirection                                    #
###############################################################################
def test_redirect_stdout_to_file(tmp_path):
    """The _out kwarg should redirect stdout to a file path."""
    script = write_script(tmp_path, 'out.py', [
        'print("redirected output")',
    ])
    out_file = str(tmp_path) + os.sep + 'stdout.txt'
    python = python_cmd()
    python(script, _out=out_file)
    with open(out_file) as f:
        assert "redirected output" in f.read()

def test_redirect_stderr_to_file(tmp_path):
    """The _err kwarg should redirect stderr to a file path."""
    script = write_script(tmp_path, 'err.py', [
        'import sys',
        'sys.stderr.write("error output\\n")',
    ])
    err_file = str(tmp_path) + os.sep + 'stderr.txt'
    python = python_cmd()
    python(script, _err=err_file)
    with open(err_file) as f:
        assert "error output" in f.read()

def test_redirect_stdout_to_file_object(tmp_path):
    """The _out kwarg should accept a file object."""
    script = write_script(tmp_path, 'out.py', [
        'print("file object output")',
    ])
    out_file = str(tmp_path) + os.sep + 'stdout.txt'
    python = python_cmd()
    with open(out_file, 'w') as fh:
        python(script, _out=fh)
    with open(out_file) as f:
        assert "file object output" in f.read()

def test_redirect_err_to_out(tmp_path):
    """The _err_to_out kwarg should merge stderr into stdout."""
    script = write_script(tmp_path, 'both.py', [
        'import sys',
        'print("from stdout")',
        'sys.stderr.write("from stderr\\n")',
    ])
    python = python_cmd()
    result = python(script, _err_to_out=True)
    output = result.stdout
    assert "from stdout" in output
    assert "from stderr" in output

###############################################################################
#                          Return codes and exceptions                        #
###############################################################################
def test_error_return_code(tmp_path):
    """A non-zero exit code should raise ErrorReturnCode."""
    script = write_script(tmp_path, 'fail.py', [
        'import sys',
        'sys.exit(1)',
    ])
    python = python_cmd()
    with pytest.raises(ErrorReturnCode):
        python(script)

def test_specific_error_return_code(tmp_path):
    """A specific exit code N should raise ErrorReturnCode_N."""
    script = write_script(tmp_path, 'fail2.py', [
        'import sys',
        'sys.exit(2)',
    ])
    python = python_cmd()
    ErrorReturnCode_2 = get_rc_exc(2)
    with pytest.raises(ErrorReturnCode_2):
        python(script)

def test_error_return_code_hierarchy(tmp_path):
    """ErrorReturnCode_N should be a subclass of ErrorReturnCode."""
    script = write_script(tmp_path, 'fail3.py', [
        'import sys',
        'sys.exit(3)',
    ])
    python = python_cmd()
    with pytest.raises(ErrorReturnCode):
        python(script)

def test_error_return_code_attributes(tmp_path):
    """The exception should expose full_cmd, stdout, and stderr."""
    script = write_script(tmp_path, 'fail_verbose.py', [
        'import sys',
        'print("some output")',
        'sys.stderr.write("some error\\n")',
        'sys.exit(1)',
    ])
    python = python_cmd()
    with pytest.raises(ErrorReturnCode) as exc_info:
        python(script)
    exc = exc_info.value
    assert exc.full_cmd is not None
    assert exc.stdout is not None
    assert exc.stderr is not None

def test_zero_exit_code(tmp_path):
    """A zero exit code should not raise any exception."""
    script = write_script(tmp_path, 'ok.py', [
        'import sys',
        'sys.exit(0)',
    ])
    python = python_cmd()
    python(script)  # should not raise

###############################################################################
#                          Non-standard exit codes                            #
###############################################################################
def test_ok_code_single(tmp_path):
    """Using _ok_code should suppress exceptions for that exit code."""
    script = write_script(tmp_path, 'exit2.py', [
        'import sys',
        'print("partial output")',
        'sys.exit(2)',
    ])
    python = python_cmd()
    result = python(script, _ok_code=2)
    assert "partial output" in str(result)

def test_ok_code_list(tmp_path):
    """Using _ok_code with a list should accept any of those codes."""
    script = write_script(tmp_path, 'exit3.py', [
        'import sys',
        'print("output")',
        'sys.exit(3)',
    ])
    python = python_cmd()
    result = python(script, _ok_code=[0, 2, 3])
    assert "output" in str(result)

def test_ok_code_tuple(tmp_path):
    """Using _ok_code with a tuple should also work."""
    script = write_script(tmp_path, 'exit4.py', [
        'import sys',
        'sys.exit(4)',
    ])
    python = python_cmd()
    python(script, _ok_code=(0, 4))  # should not raise

def test_ok_code_wrong_code_still_raises(tmp_path):
    """If the exit code is not in _ok_code, it should still raise."""
    script = write_script(tmp_path, 'exit5.py', [
        'import sys',
        'sys.exit(5)',
    ])
    python = python_cmd()
    with pytest.raises(ErrorReturnCode):
        python(script, _ok_code=[0, 2])

###############################################################################
#                             Command wrapper                                 #
###############################################################################
def test_command_from_full_path():
    """Command() should accept a full path to an executable."""
    python = Command(sys.executable)
    result = python("-c", "print('from command')")
    assert "from command" in str(result)

def test_command_create():
    """Command.create() should resolve a program name from PATH."""
    python = Command.create("python3" if os.name != 'nt' else "python")
    result = python("-c", "print('created')")
    assert "created" in str(result)

def test_command_not_found():
    """Command.create() should raise CommandNotFound for missing programs."""
    with pytest.raises(CommandNotFound):
        Command.create("this_command_does_not_exist_xyz")

def test_command_str_representation():
    """str(Command) should show the path."""
    python = Command(sys.executable)
    assert sys.executable in str(python)

###############################################################################
#                                 Baking                                      #
###############################################################################
def test_bake_basic(tmp_path):
    """Baking should prepend arguments to every subsequent call."""
    script = write_script(tmp_path, 'dump_args.py', [
        'import sys',
        'print(" ".join(sys.argv[1:]))',
    ])
    python = python_cmd()
    baked = python.bake(script)
    result = baked("extra_arg")
    assert "extra_arg" in str(result)

def test_bake_preserves_original(tmp_path):
    """Baking should not modify the original Command object."""
    python = python_cmd()
    baked = python.bake("-u")
    # Original should not include -u
    assert "-u" not in str(python)
    # Baked should include -u
    assert "-u" in str(baked)

def test_bake_str_shows_args():
    """str() of a baked command should show the path and baked args."""
    python = python_cmd()
    baked = python.bake("-u")
    representation = str(baked)
    assert sys.executable in representation
    assert "-u" in representation

def test_bake_chaining(tmp_path):
    """Baking can be chained multiple times."""
    script = write_script(tmp_path, 'dump_args.py', [
        'import sys',
        'print(" ".join(sys.argv[1:]))',
    ])
    python = python_cmd()
    step1 = python.bake(script)
    step2 = step1.bake("arg1")
    result = step2("arg2")
    output = str(result)
    assert "arg1" in output
    assert "arg2" in output

###############################################################################
#                          Subcommand via attribute                           #
###############################################################################
def test_subcommand_attribute(tmp_path):
    """
    Accessing an attribute on a Command should bake it as a sub-argument.
    For example, git.branch should resolve to 'git branch'.
    """
    python = python_cmd()
    # Accessing .bake is a real method, but accessing e.g. .something
    # returns a baked command with 'something' as first arg
    sub = python_cmd()
    baked = sub.bake("-c")
    result = baked("print('sub')")
    assert "sub" in str(result)

###############################################################################
#                         Background processes                                #
###############################################################################
def test_background_process(tmp_path):
    """A command with _bg=True should not block; .wait() should block."""
    script = write_script(tmp_path, 'bg.py', [
        'print("background done")',
    ])
    python = python_cmd()
    p = python(script, _bg=True)
    p.wait()
    assert "background done" in str(p)

def test_background_stdout(tmp_path):
    """Accessing .stdout on a bg process should wait for it to finish."""
    script = write_script(tmp_path, 'bg_out.py', [
        'print("bg output")',
    ])
    python = python_cmd()
    p = python(script, _bg=True)
    assert "bg output" in p.stdout

###############################################################################
#                         Foreground processes                                #
###############################################################################
def test_foreground_process(tmp_path):
    """A command with _fg=True should return an empty string."""
    script = write_script(tmp_path, 'fg.py', [
        'pass',
    ])
    python = python_cmd()
    result = python(script, _fg=True)
    assert str(result) == ""

###############################################################################
#                             which function                                  #
###############################################################################
def test_which_finds_python():
    """which() should find python in PATH."""
    path = which("python3") or which("python")
    assert path is not None
    assert os.path.exists(path)

def test_which_returns_none_for_missing():
    """which() should return None for non-existent programs."""
    result = which("this_program_does_not_exist_xyz")
    assert result is None

def test_which_full_path():
    """which() on a full path should return it if it's executable."""
    result = which(sys.executable)
    assert result is not None

###############################################################################
#                         resolve_program function                            #
###############################################################################
def test_resolve_program_found():
    """resolve_program should find programs in PATH."""
    path = resolve_program("python3") or resolve_program("python")
    assert path is not None

def test_resolve_program_not_found():
    """resolve_program should return None for non-existent programs."""
    assert resolve_program("this_command_does_not_exist_xyz") is None

###############################################################################
#                              glob function                                  #
###############################################################################
def test_glob_matches(tmp_path):
    """glob() should expand patterns that match files."""
    # Create a file to match
    test_file = str(tmp_path) + os.sep + 'test_file.txt'
    with open(test_file, 'w') as f:
        f.write("content")
    pattern = str(tmp_path) + os.sep + '*.txt'
    result = glob(pattern)
    assert isinstance(result, list)
    assert len(result) >= 1
    assert test_file in result

def test_glob_no_match():
    """glob() should return the original pattern if nothing matches."""
    result = glob("/nonexistent_path_xyz/*.nope")
    assert result == "/nonexistent_path_xyz/*.nope"

###############################################################################
#                          get_rc_exc function                                #
###############################################################################
def test_get_rc_exc_returns_subclass():
    """get_rc_exc should return an ErrorReturnCode subclass."""
    exc = get_rc_exc(42)
    assert issubclass(exc, ErrorReturnCode)
    assert exc.__name__ == "ErrorReturnCode_42"

def test_get_rc_exc_cached():
    """get_rc_exc should return the same class for the same code."""
    exc1 = get_rc_exc(99)
    exc2 = get_rc_exc(99)
    assert exc1 is exc2

def test_get_rc_exc_different_codes():
    """Different exit codes should produce different exception classes."""
    exc1 = get_rc_exc(10)
    exc2 = get_rc_exc(11)
    assert exc1 is not exc2

###############################################################################
#                       RunningCommand conversions                            #
###############################################################################
def test_running_command_int(tmp_path):
    """int() on a RunningCommand should parse the output as an integer."""
    script = write_script(tmp_path, 'number.py', [
        'print(42)',
    ])
    python = python_cmd()
    result = python(script)
    assert int(result) == 42

def test_running_command_float(tmp_path):
    """float() on a RunningCommand should parse the output as a float."""
    script = write_script(tmp_path, 'decimal.py', [
        'print(3.14)',
    ])
    python = python_cmd()
    result = python(script)
    assert abs(float(result) - 3.14) < 0.001

def test_running_command_len(tmp_path):
    """len() on a RunningCommand should return the length of its string."""
    script = write_script(tmp_path, 'fixed.py', [
        'print("hello")',
    ])
    python = python_cmd()
    result = python(script)
    assert len(result) == len(str(result))

def test_running_command_contains(tmp_path):
    """The 'in' operator should search the output string."""
    script = write_script(tmp_path, 'needle.py', [
        'print("find the needle here")',
    ])
    python = python_cmd()
    result = python(script)
    assert "needle" in result

def test_running_command_equality(tmp_path):
    """Two RunningCommands with the same output should be equal."""
    script = write_script(tmp_path, 'same.py', [
        'print("same")',
    ])
    python = python_cmd()
    r1 = python(script)
    r2 = python(script)
    assert r1 == r2

###############################################################################
#                              Stdin via _in                                  #
###############################################################################
def test_stdin_input(tmp_path):
    """The _in kwarg should provide stdin to the command."""
    script = write_script(tmp_path, 'read_stdin.py', [
        'import sys',
        'data = sys.stdin.read()',
        'print("got: " + data.strip())',
    ])
    python = python_cmd()
    result = python(script, _in="hello from stdin")
    assert "got: hello from stdin" in str(result)

###############################################################################
#                         Working directory (_cwd)                            #
###############################################################################
def test_cwd(tmp_path):
    """The _cwd kwarg should set the working directory of the command."""
    script = write_script(tmp_path, 'cwd.py', [
        'import os',
        'print(os.getcwd())',
    ])
    target_dir = str(tmp_path)
    python = python_cmd()
    result = python(script, _cwd=target_dir)
    # Resolve symlinks for macOS /var -> /private/var
    assert os.path.realpath(target_dir) == os.path.realpath(str(result).strip())

###############################################################################
#                         List and tuple arguments                            #
###############################################################################
def test_list_argument(tmp_path):
    """Passing a list as an argument should expand it into individual args."""
    script = write_script(tmp_path, 'dump_args.py', [
        'import sys',
        'print(" ".join(sys.argv[1:]))',
    ])
    python = python_cmd()
    result = python(script, ["a", "b", "c"])
    output = str(result)
    assert "a" in output
    assert "b" in output
    assert "c" in output

###############################################################################
#                        Piping (function composition)                        #
###############################################################################
def test_piping(tmp_path):
    """
    Passing a RunningCommand as the first arg to another command
    should pipe its stdout as stdin.
    """
    producer = write_script(tmp_path, 'producer.py', [
        'print("piped data")',
    ])
    consumer = write_script(tmp_path, 'consumer.py', [
        'import sys',
        'data = sys.stdin.read()',
        'print("received: " + data.strip())',
    ])
    python = python_cmd()
    produced = python(producer)
    # The RunningCommand must be the first positional arg for piping.
    # Use bake to bind the script path, so the piped input is first.
    consumer_cmd = python.bake(consumer)
    result = consumer_cmd(produced)
    assert "received: piped data" in str(result)

###############################################################################
#                             Environment                                     #
###############################################################################
def test_custom_env(tmp_path):
    """The _env kwarg should allow passing a custom environment."""
    script = write_script(tmp_path, 'env_var.py', [
        'import os',
        'print(os.environ.get("MY_TEST_VAR", "not set"))',
    ])
    python = python_cmd()
    env = os.environ.copy()
    env["MY_TEST_VAR"] = "custom_value"
    result = python(script, _env=env)
    assert "custom_value" in str(result)

###############################################################################
#                          Unicode / encoding                                 #
###############################################################################
def test_unicode_output(tmp_path):
    """Commands that output unicode should work correctly."""
    script = write_script(tmp_path, 'unicode.py', [
        '# -*- coding: utf-8 -*-',
        'print("caf\\u00e9")',
    ])
    python = python_cmd()
    result = python(script)
    assert "café" in str(result)

###############################################################################
#                          Multiline output                                   #
###############################################################################
def test_multiline_output(tmp_path):
    """Commands producing multiple lines should capture all of them."""
    script = write_script(tmp_path, 'multi.py', [
        'print("line1")',
        'print("line2")',
        'print("line3")',
    ])
    python = python_cmd()
    result = str(python(script))
    assert "line1" in result
    assert "line2" in result
    assert "line3" in result

###############################################################################
#                       Empty output                                          #
###############################################################################
def test_empty_output(tmp_path):
    """A command that prints nothing should return an empty string."""
    script = write_script(tmp_path, 'empty.py', [
        'pass',
    ])
    python = python_cmd()
    result = python(script)
    assert str(result).strip() == ""

###############################################################################
if __name__ == '__main__':
    pytest.main([__file__, "-v"])
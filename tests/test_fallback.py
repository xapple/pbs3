#!/usr/bin/env python3
# -*- coding: utf8 -*-

"""
Tests for the cross-platform ``from runps import sh`` fallback behavior.

On Unix/macOS this should give the real `sh` library.
On Windows (or if `sh` is not installed) it falls back to the built-in `pbs`.
"""

# Built-in modules #
import sys, os

# Third party modules #
import pytest

###############################################################################
# Helper to write a small python script and return its path #
def write_script(tmp_path, name, lines):
    path = str(tmp_path) + os.sep + name
    with open(path, 'w') as handle:
        handle.writelines(line + '\n' for line in lines)
    return path

###############################################################################
#                       from runps import sh                                   #
###############################################################################
def test_import_sh(tmp_path):
    """``from runps import sh`` should provide a working command runner."""
    from runps import sh
    script = write_script(tmp_path, 'hello.py', ['print("hello from sh")'])
    python = sh.Command(sys.executable)
    result = python(script)
    assert "hello from sh" in str(result)

def test_sh_is_real_sh_on_unix():
    """On Unix/macOS the sh object should come from the real sh library."""
    from runps import sh
    if sys.platform == 'win32':
        pytest.skip("Only relevant on Unix/macOS")
    # The real sh module has a __version__ attribute
    assert hasattr(sh, '__version__') or hasattr(sh, '_return_cmd')

def test_sh_error_return_code(tmp_path):
    """The sh object should raise on non-zero exit codes."""
    from runps import sh
    script = write_script(tmp_path, 'fail.py', ['import sys', 'sys.exit(1)'])
    python = sh.Command(sys.executable)
    with pytest.raises(sh.ErrorReturnCode):
        python(script)

###############################################################################
#                       .ran property alias                                    #
###############################################################################
def test_ran_property(tmp_path):
    """The .ran property should be an alias for .command_ran (pbs compat)."""
    import runps
    script = write_script(tmp_path, 'hello.py', ['print("hi")'])
    python = runps.Command(sys.executable)
    result = python(script)
    assert result.ran == result.command_ran
    assert script in result.ran

###############################################################################
if __name__ == '__main__':
    pytest.main([__file__, "-v"])

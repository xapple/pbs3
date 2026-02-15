#!/usr/bin/env python3
# -*- coding: utf8 -*-

# Built-in modules #
import sys, os

# Internal modules #
import runps

# Third party modules #
import pytest

###############################################################################
def test_return_code(tmp_path):
    """
    Will test what happens when the program called exits with
    return code 2. It should raise 'ErrorReturnCode_2'.
    On old versions of pbs it would instead raise this when run in python 3:

        AttributeError: 'str' object has no attribute 'decode'

    """
    # Temporary directory as a string #
    tmp_dir = str(tmp_path) + os.sep
    # All paths #
    program_path = tmp_dir + 'test_program.py'
    stdout_path  = tmp_dir + 'stdout.txt'
    stderr_path  = tmp_dir + 'stderr.txt'
    # Write program #
    with open(program_path, 'w') as handle:
        handle.writelines(('import sys\n', 'sys.exit(2)'))
    # Command #
    python = runps.Command(sys.executable)
    # Call #
    with pytest.raises(runps.ErrorReturnCode):
        return python(program_path, _out=stdout_path, _err=stderr_path)
    # Clean up #

###############################################################################
if __name__ == '__main__':
    result = test_return_code()
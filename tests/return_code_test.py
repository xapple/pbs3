# -*- coding: utf8 -*-

# Built-in modules #
import sys, tempfile

# Internal modules #
import pbs3

###############################################################################
def return_code_test():
    """
    Will test what happens when the program called exits with
    the return code 2. It should raise 'ErrorReturnCode_2'.
    On old versions of pbs it would instead raise when run in python 3:

        AttributeError: 'str' object has no attribute 'decode'

    """
    # Temporary directory #
    tmp_dir      = tempfile.mkdtemp() + '/'
    program_path = tmp_dir + 'test_program.py'
    stdout_path  = tmp_dir + 'stdout.txt'
    stderr_path  = tmp_dir + 'stderr.txt'
    # Write program #
    with open(program_path, 'w') as handle:
        handle.writelines(('import sys\n', 'sys.exit(2)'))
    # Command #
    python = pbs3.Command(sys.executable)
    # Call #
    python(program_path, _out=stdout_path, _err=stderr_path)
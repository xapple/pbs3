"""
`runps` is a cross-platform Python utility for launching external processes.

On Unix/macOS, ``from runps import sh`` gives you the real `sh` library.
On Windows (or if `sh` is not installed), it falls back to the built-in
`pbs` module which has the same API.

Backward compatibility: ``import runps; runps.ls("-la")`` and
``from runps import Command`` continue to work via the `pbs` submodule.
"""

# Constants #
__version__ = '4.1.0'
__project_url__ = 'https://github.com/xapple/runps'

# Built-in modules #
import sys

# Platform-aware `sh` object #
if sys.platform == 'win32':
    from runps import pbs as sh
else:
    try:
        import sh
        # After sh v2 the object returned by commands changed.
        # Baking with _return_cmd=True restores the v1 behavior
        # where commands return RunningCommand objects.
        sh_version = int(sh.__version__.split('.')[0])
        if sh_version > 1:
            sh = sh.bake(_return_cmd=True)
    except ImportError:
        from runps import pbs as sh

# Re-export pbs internals for backward compatibility #
from runps.pbs import Command, CommandNotFound, ErrorReturnCode
from runps.pbs import which, resolve_program, glob, get_rc_exc

# Expose the underlying module for tests that access internals #
self_module = sys.modules['runps.pbs']
if hasattr(self_module, 'self_module'):
    self_module = self_module.self_module

def __getattr__(name):
    """Dynamic command resolution: ``import runps; runps.ls('-la')``."""
    # Delegate to the pbs module's SelfWrapper for dynamic commands
    import runps.pbs as _pbs
    return getattr(_pbs, name)
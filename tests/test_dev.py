#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Written by Lucas Sinclair.
MIT Licensed.
Contact at www.sinclair.bio

Development script to test some of the functionality in `pbs3`.

Typically you would run this file from a command line like this:

     ipython3 -i -- ~/deploy/pbs3/tests/test_dev.py
"""

# Internal modules #
import pbs3
import sh

###############################################################################
print(pbs3.ls())
print(sh.ls())
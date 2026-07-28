"""Default `pedro_capabilities` module for programs built in THIS repo.

Generated Pedro code imports its declared capabilities from `pedro_capabilities`
(one swappable module per project). This repo-root shim re-exports pedroc's
in-memory reference adapters (`pedroc/adapters.py`) so a built example can be run
directly:

    PYTHONPATH=. python -m pedroc build examples/signup.pedro -o build/signup.py
    PYTHONPATH=. python build/signup.py     # -> "...all expectations passed ✓"

A real project replaces this file with adapters wired to real I/O, exposing the
same names (`database`, `crypto`, `email`, ...).
"""
from pedroc.adapters import Database, Crypto, Mailer, database, crypto, email  # noqa: F401

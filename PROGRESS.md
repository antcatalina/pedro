# In-flight task

_None._ The 2026-08-01 installable-CLI work landed and is green: `pyproject.toml`
adds a `pedroc` console-script entry point (`pedroc.__main__:run`), so both
`pedroc …` and `python -m pedroc …` work after `pip install -e .` with no
`PYTHONPATH`. `tests/test_packaging.py` (wired into `tools/regress.py`) pins the
importable API + byte-identical codegen + both CLI entry points; CI installs
editable and runs `python tools/regress.py`. See that WORKLOG entry. No task in
flight.

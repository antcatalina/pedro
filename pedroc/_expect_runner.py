"""Sandboxed executor for `pedroc check`'s expect block.

This runs as a SEPARATE PROCESS (see pedroc/check.py). It has no pedroc imports
on purpose: the parent hands it the already-generated Python plus a list of
pre-rendered expression strings over stdin, so a hostile or non-terminating
program can only ever hang or crash THIS process — never the compiler.

Protocol (all JSON):
  stdin  : {"code": <generated python>, "steps": [ ...step dicts... ]}
  stdout : one JSON record per completed step, newline-delimited and FLUSHED so
           that partial progress survives a SIGKILL on timeout. Record kinds:
             {"t":"load-error","message":...}   generated code failed to load
             {"t":"given-ok"}                    a `given` binding succeeded
             {"t":"given-error","message":...}   a `given` binding raised
             {"t":"exp","text","passed","detail"} an assert/fails result
             {"t":"cpu-limit"}                    the child's CPU-time rlimit hit

The parent reads however many records arrived; the first step with no record is
the one that hung (on timeout) — see check.py.

Alongside the parent's wall-clock timeout, the parent may impose a POSIX CPU-time
rlimit (`RLIMIT_CPU`) on this child as a backstop. When that soft limit is hit the
kernel delivers SIGXCPU; the handler below turns it into a clean `cpu-limit`
record and exits, so a CPU-bound infinite loop is reported as a structured timeout
rather than a cryptic signal crash. (A brief hard-limit grace window lets the
handler emit before SIGKILL.)
"""
import json
import os
import signal
import sys
import types


def _emit(rec):
    sys.stdout.write(json.dumps(rec) + "\n")
    sys.stdout.flush()


def _install_cpu_limit_handler():
    """Report the parent's CPU-time rlimit as a structured record, not a crash."""
    if not hasattr(signal, "SIGXCPU"):
        return  # non-POSIX: no CPU rlimit to catch

    def _on_xcpu(signum, frame):
        _emit({"t": "cpu-limit"})
        os._exit(0)  # immediate + no re-entrancy; _emit already flushed

    signal.signal(signal.SIGXCPU, _on_xcpu)


def main():
    _install_cpu_limit_handler()
    payload = json.loads(sys.stdin.read())
    code = payload["code"]
    steps = payload["steps"]

    # A capability program imports `pedro_capabilities`; inject the reference
    # in-memory adapters (passed in by the parent) under that name FIRST, so the
    # generated code's `from pedro_capabilities import ...` resolves in the sandbox.
    adapters_src = payload.get("adapters")
    if adapters_src:
        cap_mod = types.ModuleType("pedro_capabilities")
        sys.modules["pedro_capabilities"] = cap_mod
        try:
            exec(compile(adapters_src, "<pedro-capabilities>", "exec"), cap_mod.__dict__)
        except Exception as e:
            _emit({"t": "load-error", "message": f"capability adapters: {e}"})
            return 0

    # Exec into a REAL module object registered in sys.modules. `@dataclass`
    # resolves its enclosing module via `sys.modules[cls.__module__]`, so a bare
    # dict namespace makes record generation crash; a registered module fixes it.
    # `__name__` is not "__main__", so the generated `if __name__ == "__main__"`
    # expect block stays dormant — we run the steps ourselves below.
    module = types.ModuleType("pedroc_check")
    sys.modules["pedroc_check"] = module
    ns = module.__dict__
    try:
        exec(compile(code, "<pedro-generated>", "exec"), ns)
    except Exception as e:  # a failure loading generated code is a compiler bug
        _emit({"t": "load-error", "message": str(e)})
        return 0

    pedro_error = ns.get("PedroError", Exception)

    for step in steps:
        kind = step["kind"]

        if kind == "given":
            try:
                ns[step["name"]] = eval(step["expr"], ns)
                _emit({"t": "given-ok"})
            except Exception as e:
                _emit({"t": "given-error", "message": str(e)})
            continue

        if kind == "exec":  # a setup side-effect, e.g. `users.clear()`
            try:
                eval(step["expr"], ns)
                _emit({"t": "given-ok"})
            except Exception as e:
                _emit({"t": "given-error", "message": str(e)})
            continue

        if kind == "assert":
            passed = False
            detail = None
            try:
                passed = bool(eval(step["expr"], ns))
                if not passed and step["cmp"] is not None:
                    lv = eval(step["cmp"]["left"], ns)
                    rv = eval(step["cmp"]["right"], ns)
                    detail = f"got {lv!r}, expected {step['cmp']['op']} {rv!r}"
            except Exception as e:
                detail = f"error: {e}"
            _emit({"t": "exp", "text": step["text"], "passed": passed, "detail": detail})
            continue

        # kind == "fails"
        passed = False
        detail = None
        msg = step["msg"]
        try:
            eval(step["call"], ns)
            detail = f"expected failure {msg!r}, but it returned normally"
        except pedro_error as e:
            if str(e) == msg:
                passed = True
            else:
                detail = f"failed with {str(e)!r}, expected {msg!r}"
        except Exception as e:
            detail = f"raised {type(e).__name__}: {e}, expected failure {msg!r}"
        _emit({"t": "exp", "text": step["text"], "passed": passed, "detail": detail})

    return 0


if __name__ == "__main__":
    sys.exit(main())

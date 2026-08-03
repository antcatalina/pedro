"""In-memory reference adapters for Pedro capabilities — the default
`pedro_capabilities` module.

Generated Pedro code does `from pedro_capabilities import database, crypto, ...`
(the email adapter is aliased to `mailer` when it would collide). A real project
ships its OWN `pedro_capabilities.py` wired to a live database / SMTP server /
crypto library, exposing the same names. This module is the swappable default: a
deterministic, side-effect-free implementation so `pedroc check` can RUN an
effectful program and verify its `expect` block with no real I/O — the whole point
of routing capabilities through an adapter layer.

`pedroc check` injects this module's source into its sandboxed subprocess under the
name `pedro_capabilities`, so a capability program is runnable there with no setup.
"""
import hashlib


class _Table:
    """A tiny in-memory table: iterable over its rows (so `find one`/`count of`/
    `for each` work on it), with `insert`/`clear`."""

    def __init__(self, name, row_type=None):
        self._name = name
        self._row_type = row_type
        self._rows = []
        self._seq = 0

    def __iter__(self):
        return iter(self._rows)

    def __len__(self):
        return len(self._rows)

    def clear(self):
        self._rows = []
        self._seq = 0

    def insert(self, row):
        """Store a row, assigning it a fresh id (if it has an `id` field), and
        return that id."""
        self._seq += 1
        new_id = f"{self._name}-{self._seq}"
        if hasattr(row, "id"):
            row.id = new_id
        self._rows.append(row)
        return new_id

    def delete(self, row):
        """Remove a specific row (by identity — the object a `find one` returned).
        Returns whether a row was removed."""
        before = len(self._rows)
        self._rows = [r for r in self._rows if r is not row]
        return len(self._rows) < before

    def update(self, row, field, value):
        """Set `field` on a stored row to `value` and return the row. A real
        adapter would persist the change; the in-memory row IS the stored object,
        so the write is visible to later reads."""
        setattr(row, field, value)
        return row


class Database:
    def __init__(self):
        self._tables = {}

    def table(self, name, row_type=None):
        if name not in self._tables:
            self._tables[name] = _Table(name, row_type)
        return self._tables[name]


class Crypto:
    def hash(self, text):
        return "pedro$" + hashlib.sha256(str(text).encode("utf-8")).hexdigest()

    def verify(self, text, hashed):
        return self.hash(text) == hashed


class Mailer:
    def __init__(self):
        self.outbox = []

    def send(self, to, subject, body):
        self.outbox.append({"to": to, "subject": subject, "body": body})
        return True


class Files:
    """An in-memory filesystem: `write` stores content under a path, `read`
    returns it. Deterministic (no real I/O), so `pedroc check` stays reproducible;
    a real project's adapter would hit the actual filesystem behind the same names.
    Reading a path that was never written raises — the caller wrote it first."""

    def __init__(self):
        self._files = {}

    def write(self, path, content):
        self._files[path] = content
        return path

    def read(self, path):
        if path not in self._files:
            raise FileNotFoundError(f"no such file: {path}")
        return self._files[path]


# Module-level adapter instances — the names the generated `import` binds to.
database = Database()
crypto = Crypto()
email = Mailer()
files = Files()

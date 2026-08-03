// Default `pedro_capabilities` module for TypeScript programs built in THIS repo.
//
// The TypeScript counterpart of `pedro_capabilities.py`: generated Pedro code
// imports its declared capabilities from this module (one swappable module per
// project). A real project replaces this file with adapters wired to real I/O,
// exposing the SAME names (`database`, `crypto`, `email`, ...).
//
// These are deterministic, side-effect-free in-memory reference adapters so a
// capability program is runnable with no setup — the mirror of pedroc's Python
// `pedroc/adapters.py`. `pedroc check --targets` / the differential tester write
// this file next to the generated program so the relative import resolves. Node
// v24+ strips types, so a `.ts` import runs with no build step.
import { createHash } from "node:crypto";

// A tiny in-memory table: a plain array of rows augmented with `insert`/`clear`,
// so the ordinary collection paths (`find`→`.find`, `count of`→`.length`,
// `for each`→`.entries()`) work on it unchanged — the mirror of Python's iterable
// `_Table`. `insert` assigns a fresh `<name>-<n>` id (onto a row with an `id`
// field) and returns it.
type Row = Record<string, any>;
interface Table extends Array<Row> {
  insert(row: Row): string;
  clear(): void;
}

function makeTable(name: string): Table {
  const rows = [] as unknown as Table;
  let seq = 0;
  rows.insert = (row: Row): string => {
    seq += 1;
    const id = `${name}-${seq}`;
    if (row && typeof row === "object" && "id" in row) row.id = id;
    rows.push(row);
    return id;
  };
  rows.clear = (): void => {
    rows.length = 0;
    seq = 0;
  };
  return rows;
}

export class Database {
  private tables: Record<string, Table> = {};
  table(name: string, _rowType?: any): Table {
    if (!(name in this.tables)) this.tables[name] = makeTable(name);
    return this.tables[name];
  }
}

export class Crypto {
  hash(text: any): string {
    return "pedro$" + createHash("sha256").update(String(text)).digest("hex");
  }
  verify(text: any, hashed: string): boolean {
    return this.hash(text) === hashed;
  }
}

export class Mailer {
  outbox: { to: any; subject: any; body: any }[] = [];
  send(to: any, subject: any, body: any): boolean {
    this.outbox.push({ to, subject, body });
    return true;
  }
}

// Module-level adapter instances — the names the generated `import` binds to.
export const database = new Database();
export const crypto = new Crypto();
export const email = new Mailer();

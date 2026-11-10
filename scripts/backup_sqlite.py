"""Consistent SQLite backup; never overwrite an existing destination."""
import argparse
import sqlite3
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument('source', type=Path)
parser.add_argument('destination', type=Path)
args = parser.parse_args()
if not args.source.is_file():
    parser.error('Source database does not exist')
if args.destination.exists():
    parser.error('Destination already exists')
args.destination.parent.mkdir(parents=True, exist_ok=True)
args.destination.touch(mode=0o600, exist_ok=False)
with sqlite3.connect(f'{args.source.resolve().as_uri()}?mode=ro', uri=True) as source:
    with sqlite3.connect(args.destination) as target:
        source.backup(target)
        if target.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
            raise RuntimeError('Backup integrity check failed')
print('Backup created and integrity verified.')

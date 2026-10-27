"""Command-line validation of local economic evidence."""
import argparse
import json
import sqlite3
import sys

from .storage import read_jsonl, read_store, replay
from .reporting import economic_report

from .validation import validate_file


def main(argv=None):
    parser = argparse.ArgumentParser(prog='evidence-kit')
    sub = parser.add_subparsers(dest='command', required=True)
    validate = sub.add_parser('validate', help='Validate each file as a standalone JSONL dataset')
    validate.add_argument('files', nargs='+')
    validate.add_argument('--json', action='store_true', help='Emit machine-readable results')
    ingest = sub.add_parser('replay', help='Atomically ingest JSONL files into SQLite')
    ingest.add_argument('files', nargs='+')
    ingest.add_argument('--db', required=True)
    report = sub.add_parser('report', help='Report one economic intent as JSON')
    report.add_argument('--db', required=True)
    report.add_argument('--intent', required=True)
    report.add_argument('--coverage-source', help='Explicit declaration of complete in-scope cost coverage; cite its source')
    report.add_argument('--as-of', help='UTC Z freshness reference, default: intent period end')
    report.add_argument('--max-estimate-age-hours', type=int, default=24)
    args = parser.parse_args(argv)
    if args.command != 'validate':
        try:
            if args.command == 'replay':
                result = replay(args.db, read_jsonl(args.files))
            else:
                result = economic_report(read_store(args.db), args.intent,
                                         coverage_source=args.coverage_source,
                                         as_of=args.as_of,
                                         max_estimate_age_hours=args.max_estimate_age_hours)
            print(json.dumps(result, indent=2, allow_nan=False))
            return 0
        except (ValueError, OSError, sqlite3.Error) as exc:
            print(json.dumps({'error': str(exc)}), file=sys.stderr)
            return 1
    results = []
    for path in args.files:
        count, errors = validate_file(path)
        results.append({'file': path, 'records': count, 'valid': not errors, 'errors': errors})
    if args.json:
        print(json.dumps(results, indent=2))
    else:
        for result in results:
            print(f'{"VALID" if result["valid"] else "INVALID"} {result["file"]}: {result["records"]} records')
            for error in result['errors']:
                print(f'  {error}')
    return int(any(not result['valid'] for result in results))

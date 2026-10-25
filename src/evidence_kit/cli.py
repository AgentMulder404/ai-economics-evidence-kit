"""Command-line validation of local economic evidence."""
import argparse
import json

from .validation import validate_file


def main(argv=None):
    parser = argparse.ArgumentParser(prog='evidence-kit')
    sub = parser.add_subparsers(dest='command', required=True)
    validate = sub.add_parser('validate', help='Validate each file as a standalone JSONL dataset')
    validate.add_argument('files', nargs='+')
    validate.add_argument('--json', action='store_true', help='Emit machine-readable results')
    args = parser.parse_args(argv)
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

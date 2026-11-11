"""Catalog administration: python -m app.cli --help."""
import argparse
import json
import sys

from sqlalchemy.exc import SQLAlchemyError

from app.config import settings
from app.db import SessionLocal
from app.services.imports import ImportFailure, ImportReport, deactivate_lot, demo_seed, import_complexes, import_lots, read_snapshot


def main(argv=None):
    parser = argparse.ArgumentParser(description="Import and maintain the apartment catalog")
    commands = parser.add_subparsers(dest="command", required=True)
    complexes = commands.add_parser("complexes-import")
    complexes.add_argument("path")
    complexes.add_argument("--allow-clear-price", action="store_true")
    lots = commands.add_parser("lots-import")
    lots.add_argument("path")
    deactivate = commands.add_parser("lot-deactivate")
    deactivate.add_argument("complex_slug")
    deactivate.add_argument("external_id")
    commands.add_parser("demo-seed")
    args = parser.parse_args(argv)
    try:
        with SessionLocal() as session:
            if args.command == "complexes-import":
                report = import_complexes(session, read_snapshot(args.path), allow_clear_price=args.allow_clear_price)
            elif args.command == "lots-import":
                report = import_lots(session, read_snapshot(args.path), demo_mode=settings.demo_mode)
            elif args.command == "lot-deactivate":
                report = deactivate_lot(session, args.complex_slug, args.external_id)
            else:
                report = demo_seed(session, demo_mode=settings.demo_mode)
    except ImportFailure as exc:
        print(json.dumps(ImportReport(rejected=1).as_dict()), file=sys.stderr)
        print(str(exc), file=sys.stderr)
        return 1
    except SQLAlchemyError:
        print(json.dumps(ImportReport(rejected=1).as_dict()), file=sys.stderr)
        print("Database operation failed; no import was saved", file=sys.stderr)
        return 1
    print(json.dumps(report.as_dict()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

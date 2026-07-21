from __future__ import annotations

import argparse
import sys

from src.pipeline import process_statement


def main() -> None:
    parser = argparse.ArgumentParser(description="Procesar extracto bancario PDF")
    parser.add_argument("pdf", help="Ruta al archivo PDF")
    parser.add_argument("--strict", action="store_true", help="Fail fast on parse errors")
    args = parser.parse_args()

    with open(args.pdf, "rb") as f:
        pdf_bytes = f.read()

    result = process_statement(pdf_bytes, filename=args.pdf, strict=args.strict)
    sys.stdout.flush()
    sys.stdout.buffer.write(result.encode("utf-8"))
    sys.stdout.buffer.write(b"\n")


if __name__ == "__main__":
    main()

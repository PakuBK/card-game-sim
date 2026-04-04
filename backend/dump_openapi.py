from __future__ import annotations

import argparse
import json
import sys


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Write the FastAPI OpenAPI schema to a file (used for frontend type generation)."
    )
    parser.add_argument(
        "--out",
        required=True,
        help="Output path for the OpenAPI JSON.",
    )
    args = parser.parse_args()

    try:
        # Importing this way avoids needing a running server.
        from app.main import app
    except Exception as e:  # pragma: no cover
        print(f"Failed to import FastAPI app: {e}", file=sys.stderr)
        return 1

    schema = app.openapi()

    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(schema, f, indent=2, sort_keys=False)
        f.write("\n")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

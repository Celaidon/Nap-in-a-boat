"""Record check C8 from a deployed server: smoke test plus tokens/sec for the three key blends.

    python scripts/record_deploy.py http://<droplet-ip>
    python scripts/record_deploy.py https://demo.example.com --tokens 50

Run from anywhere; writes verification/C8.json in the repo root. Commit that file in the C8 PR.
Under 3 tokens/sec is flagged in the record: tell the team, since the demo may need a bigger Droplet.
"""

import argparse
import os
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import smoke_test

from contracts.record_check import record_check

BLENDS = ["sweep_000", "sweep_050", "sweep_100"]
MIN_TOKENS_PER_SEC = 3.0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("base_url")
    parser.add_argument("--tokens", type=int, default=50)
    parser.add_argument("--timeout", type=float, default=900, help="seconds per blend (first use downloads ~5 GB)")
    args = parser.parse_args(argv)
    base = args.base_url.rstrip("/")

    os.chdir(ROOT)  # record_check writes ./verification/
    details: dict = {"base_url": base, "max_tokens": args.tokens}
    try:
        smoke_test.check_rest(base)
        speeds = {}
        for blend_id in BLENDS:
            result = smoke_test.generate(base, blend_id, args.tokens, args.timeout)
            print(f"{blend_id}: {result['tokens']} tokens, {result['server_tokens_per_sec']} tok/s")
            if result["tokens"] < 1:
                raise smoke_test.SmokeFailure(f"{blend_id} produced no tokens")
            speeds[blend_id] = result["server_tokens_per_sec"]
        details["tokens_per_sec"] = speeds
        slow = [b for b, s in speeds.items() if s < MIN_TOKENS_PER_SEC]
        if slow:
            details["warning"] = (
                f"{', '.join(slow)} under {MIN_TOKENS_PER_SEC} tokens/sec: tell the team; "
                "a bigger CPU Droplet or a lower max_tokens may be needed for the demo"
            )
            print("WARNING: " + details["warning"])
        record_check("C8", "pass", "sharva", details)
        return 0
    except smoke_test.SmokeFailure as exc:
        details["error"] = str(exc)
        record_check("C8", "fail", "sharva", details)
        print(f"FAILED: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())

# contracts/record_check.py
# Writes verification/<CHECK_ID>.json at the end of every check.
# Every track calls this the same way; no changes should ever be needed here.

import datetime
import json
import pathlib
import subprocess


def record_check(check_id: str, status: str, owner: str, details: dict | None = None) -> dict:
    """Write a verification record for a completed check.

    Args:
        check_id: e.g. "A1", "B3", "P2"
        status:   "pass" or "fail"
        owner:    short identifier, e.g. "teamlead", "muskan", "sharva"
        details:  dict of numbers / strings that prove the check (optional)

    Returns:
        The dict that was written to disk.
    """
    # Capture the current short git commit hash so every record is traceable.
    code_commit = subprocess.run(
        ["git", "rev-parse", "--short", "HEAD"],
        capture_output=True,
        text=True,
        check=False,
    ).stdout.strip()

    out = {
        "check_id": check_id,
        "status": status,
        "owner": owner,
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "code_commit": code_commit,
        "details": details or {},
    }

    path = pathlib.Path("verification") / f"{check_id}.json"
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps(out, indent=2))
    print(f"[record_check] wrote {path}  status={status}")
    return out

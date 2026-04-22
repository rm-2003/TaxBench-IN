"""
Bulk-rename JSON keys and string literals across multiple files.

Reads a mapping of old→new strings, then:
1. For JSON files: recursively renames matching keys in the parsed structure
2. For Python files: does exact string replacement in source code

Usage:
    python3 tools/rename_json_keys.py

Edit the MAPPING dict below to define replacements. Add target paths to TARGETS.
"""

import json
import os
import glob

# ---------------------------------------------------------------------------
# MAPPING: old string → new string  (exact match, order doesn't matter)
# ---------------------------------------------------------------------------

MAPPING = {
    "LTCG (Non-Equity @ 12.5%)": "LTCG (Non-Equity)",
    "LTCG (Other @ 20%)": "LTCG (Other)",
    "Tax on STCG (Section 111A) at 20%": "Tax on STCG (Section 111A)",
    "Tax on LTCG (Section 112A) at 12.5%": "Tax on LTCG (Section 112A)",
    "Tax on LTCG (Non-Equity) at 12.5%": "Tax on LTCG (Non-Equity)",
    "Tax on LTCG (Other) at 20%": "Tax on LTCG (Other)",
    "Health and Education Cess (4%)": "Health and Education Cess",
}

# ---------------------------------------------------------------------------
# TARGETS: files or glob patterns to process
# ---------------------------------------------------------------------------

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

TARGETS = [
    os.path.join(BASE, "Script_output.json"),
    os.path.join(BASE, "tax_calculator.py"),
    os.path.join(BASE, "calculator_tests", "run_tests.py"),
    os.path.join(BASE, "tests", "generated", "*.json"),
]

# ---------------------------------------------------------------------------
# Logic
# ---------------------------------------------------------------------------

def rename_keys_recursive(obj):
    """Recursively rename dict keys that match MAPPING."""
    if isinstance(obj, dict):
        new = {}
        for k, v in obj.items():
            new_key = MAPPING.get(k, k)
            new[new_key] = rename_keys_recursive(v)
        return new
    elif isinstance(obj, list):
        return [rename_keys_recursive(item) for item in obj]
    return obj


def process_json_file(filepath):
    with open(filepath, "r") as f:
        data = json.load(f)
    updated = rename_keys_recursive(data)
    with open(filepath, "w") as f:
        json.dump(updated, f, indent=4 if "generated" not in filepath else 2)
        f.write("\n")


def process_text_file(filepath):
    with open(filepath, "r") as f:
        content = f.read()
    original = content
    for old, new in MAPPING.items():
        content = content.replace(old, new)
    if content != original:
        with open(filepath, "w") as f:
            f.write(content)
        return True
    return False


def resolve_targets():
    """Expand glob patterns and return list of (filepath, filetype) tuples."""
    files = []
    for target in TARGETS:
        if "*" in target:
            for fp in sorted(glob.glob(target)):
                ext = os.path.splitext(fp)[1]
                files.append((fp, ext))
        elif os.path.isfile(target):
            ext = os.path.splitext(target)[1]
            files.append((target, ext))
        else:
            print(f"  SKIP (not found): {target}")
    return files


def main():
    print(f"Mapping ({len(MAPPING)} replacements):")
    for old, new in MAPPING.items():
        print(f'  "{old}" → "{new}"')
    print()

    files = resolve_targets()
    print(f"Files to process: {len(files)}")

    json_count = 0
    text_count = 0
    skipped = 0

    for filepath, ext in files:
        rel = os.path.relpath(filepath, BASE)
        if ext == ".json":
            process_json_file(filepath)
            json_count += 1
        elif ext in (".py", ".md", ".txt"):
            changed = process_text_file(filepath)
            if changed:
                text_count += 1
            else:
                skipped += 1
        else:
            skipped += 1

        if json_count % 100 == 0 and json_count > 0 and ext == ".json":
            print(f"  Processed {json_count} JSON files...")

    print(f"\nDone.")
    print(f"  JSON files updated: {json_count}")
    print(f"  Text files updated: {text_count}")
    print(f"  Skipped (no match): {skipped}")


if __name__ == "__main__":
    main()

"""
PDF narrative text extractor using pymupdf (fitz).

Handles:
  - Standard single-column PDFs
  - Booklet PDFs (landscape A3, two pages side-by-side)
  - Annual report sidebars / pull-quotes (excluded by x-zone + font filtering)
  - Tables (excluded)

For digitally-created PDFs only — no OCR required.

Usage:
    python3 extract_text.py <input_dir> <output_dir>
"""

import sys
import re
import argparse
from pathlib import Path
from collections import Counter

try:
    import fitz  # pymupdf
except ImportError:
    sys.exit("pymupdf not found.  Install with:  pip3 install pymupdf")


# ── Configuration ──────────────────────────────────────────────────────────────

MARGIN_PCT     = 0.09   # top/bottom header/footer margin (fraction of page height)
BOOKLET_RATIO  = 1.3    # page is booklet if width > height × this
MIN_FONT_SIZE  = 6.5    # ignore tiny chars (superscripts, footnotes)
TITLE_FACTOR   = 2.1    # font_size > body_size × this  →  "# Title"
SUBHEAD_FACTOR = 1.1    # font_size > body_size × this  →  "## Subhead"

# For booklet PDFs: blocks whose x0 exceeds these thresholds are in the
# sidebar / decorative zone and are excluded.
#   Left booklet page:  main text x ≈ 51–300,  sidebar x > 300
#   Right booklet page: main text x ≈ 640–895, sidebar x > 910
BOOKLET_LEFT_SIDEBAR_X  = 310
BOOKLET_RIGHT_SIDEBAR_X = 910


# ── Utilities ──────────────────────────────────────────────────────────────────

def _detect_body_size(blocks):
    """Most common font size under 20 pt across all text spans."""
    sizes = []
    for b in blocks:
        for line in b.get("lines", []):
            for span in line.get("spans", []):
                sz = span["size"]
                if MIN_FONT_SIZE <= sz < 20:
                    sizes.append(round(sz * 2) / 2)
    if not sizes:
        return 10.0
    return Counter(sizes).most_common(1)[0][0]


def _bbox_overlaps(a, b):
    """True if two (x0,y0,x1,y1) bboxes overlap."""
    return a[0] < b[2] and a[2] > b[0] and a[1] < b[3] and a[3] > b[1]


# ── Block classification ───────────────────────────────────────────────────────

def _classify_block(block, body_size):
    """
    Convert a pymupdf text block to a list of (kind, text) tuples.
    kind ∈ {'title', 'subhead', 'body'}.

    Consecutive heading lines within the same block are merged only when the
    vertical gap is within 1.8× the font size — i.e. they are genuinely wrapped
    lines of the same heading, not two separate headings stacked in one block.
    """
    # Internal list includes y and size so we can apply the y-gap guard.
    # Schema: [kind, text, last_line_y, font_size]
    internal = []

    for line in block.get("lines", []):
        spans = [s for s in line["spans"] if s["size"] >= MIN_FONT_SIZE]
        if not spans:
            continue

        text = "".join(s["text"] for s in spans).strip()
        if not text:
            continue

        max_size = max(s["size"] for s in spans)
        y = line["bbox"][1]

        if max_size >= body_size * TITLE_FACTOR:
            kind = "title"
        elif max_size >= body_size * SUBHEAD_FACTOR:
            kind = "subhead"
        else:
            kind = "body"

        if (internal
                and internal[-1][0] == kind
                and kind in ("title", "subhead")
                and (y - internal[-1][2]) <= internal[-1][3] * 1.8):
            # Wrapped continuation of the same heading
            internal[-1][1] = internal[-1][1].rstrip() + " " + text
            internal[-1][2] = y
        else:
            internal.append([kind, text, y, max_size])

    return [(kind, text) for kind, text, _y, _sz in internal]


# ── Per-page extraction ────────────────────────────────────────────────────────

def extract_page_items(page):
    """
    Extract (kind, text) items from a single pymupdf page.
    Returns a flat list in reading order (left booklet page then right).
    """
    W = float(page.rect.width)
    H = float(page.rect.height)
    header_y = H * MARGIN_PCT
    footer_y = H * (1 - MARGIN_PCT)
    is_booklet = (W > H * BOOKLET_RATIO)
    mid = W / 2

    # Table bboxes for exclusion
    try:
        table_bboxes = [t.bbox for t in page.find_tables()]
    except Exception:
        table_bboxes = []

    # Extract all text blocks with font metadata
    raw_blocks = page.get_text("dict")["blocks"]
    text_blocks = [b for b in raw_blocks if b["type"] == 0]

    # Filter: skip header/footer zones and table interiors
    def _keep(b):
        x0, y0, x1, y1 = b["bbox"]
        if y1 <= header_y or y0 >= footer_y:
            return False
        if any(_bbox_overlaps(b["bbox"], tb) for tb in table_bboxes):
            return False
        return True

    blocks = [b for b in text_blocks if _keep(b)]
    if not blocks:
        return []

    body_size = _detect_body_size(blocks)

    if is_booklet:
        # Split by page midpoint
        left_blocks  = [b for b in blocks if b["bbox"][0] < mid]
        right_blocks = [b for b in blocks if b["bbox"][0] >= mid]

        # Drop sidebar blocks (x0 beyond known sidebar x threshold)
        left_blocks  = [b for b in left_blocks  if b["bbox"][0] <= BOOKLET_LEFT_SIDEBAR_X]
        right_blocks = [b for b in right_blocks if b["bbox"][0] <= BOOKLET_RIGHT_SIDEBAR_X]

        # Sort top-to-bottom within each half
        left_blocks.sort(key=lambda b: b["bbox"][1])
        right_blocks.sort(key=lambda b: b["bbox"][1])

        items = []
        for b in left_blocks:
            items.extend(_classify_block(b, body_size))
        for b in right_blocks:
            items.extend(_classify_block(b, body_size))
        return items

    else:
        # For multi-column non-booklet pages, sort left-to-right then top-to-bottom
        # (simple heuristic: sort by x-band first, then y)
        blocks.sort(key=lambda b: (round(b["bbox"][0] / 50) * 50, b["bbox"][1]))
        items = []
        for b in blocks:
            items.extend(_classify_block(b, body_size))
        return items


# ── Document assembly ──────────────────────────────────────────────────────────

def format_output(pages_content):
    """Assemble extracted items into a clean .txt string."""
    all_items = []
    for page_items in pages_content:
        all_items.extend(page_items)

    output_lines = []
    prev_kind = None

    for kind, text in all_items:
        if kind == "title":
            if output_lines and output_lines[-1] != "":
                output_lines.append("")
            output_lines.append(f"# {text}")
            output_lines.append("")
        elif kind == "subhead":
            if output_lines and output_lines[-1] != "":
                output_lines.append("")
            output_lines.append(f"## {text}")
            output_lines.append("")
        else:  # body
            if prev_kind == "body" and output_lines:
                output_lines[-1] += " " + text
            else:
                output_lines.append(text)
        prev_kind = kind

    return re.sub(r"\n{3,}", "\n\n", "\n".join(output_lines)).strip()


# ── Top-level ──────────────────────────────────────────────────────────────────

def extract_pdf(pdf_path):
    """Extract per-page item lists from a PDF."""
    pages_content = []
    with fitz.open(str(pdf_path)) as doc:
        for page in doc:
            pages_content.append(extract_page_items(page))
    return pages_content


def main():
    parser = argparse.ArgumentParser(
        description="Extract narrative text from PDF annual reports.")
    parser.add_argument("input_dir",  help="Directory containing PDF files")
    parser.add_argument("output_dir", help="Directory for output files")
    args = parser.parse_args()

    input_dir  = Path(args.input_dir)
    output_dir = Path(args.output_dir)

    if not input_dir.is_dir():
        sys.exit(f"Input directory not found: {input_dir}")

    output_dir.mkdir(parents=True, exist_ok=True)

    pdfs = sorted(input_dir.glob("*.pdf"))
    if not pdfs:
        sys.exit(f"No PDF files found in {input_dir}")

    for pdf_path in pdfs:
        out_path = output_dir / pdf_path.with_suffix(".txt").name
        print(f"Processing: {pdf_path.name}  →  {out_path.name}")
        try:
            pages_content = extract_pdf(pdf_path)
            text = format_output(pages_content)
            out_path.write_text(text, encoding="utf-8")
            print(f"  Done — {len(text.split()):,} words")
        except Exception as e:
            print(f"  ERROR: {e}")

    print("\nAll done.")


if __name__ == "__main__":
    main()

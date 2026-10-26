"""
Extract International Nonproprietary Names (INN) from a WHO Drug Information
"Proposed INN" list PDF into a table that can seed the compound master.

The list pages share a fixed two-column layout:
  - left column (x ~ 58): the Latin INN in bold, followed by the English,
    French and Spanish names in that order
  - right column: chemical name / description (regular) and action & use
    (italic) for each language, then the molecular formula and CAS number

The English name is the one to master against; Latin/French/Spanish are kept
as synonyms.

Only the main list (and any special edition, e.g. COVID-19) is parsed. The
trailing sections (chemical modification names, amendments to previous lists,
procedure annexes) use different layouts and are skipped.

Usage:
    uv run python src/extract_inn.py input/pl135.pdf [more.pdf ...] --out output/inn_names.csv
"""

import argparse
import re
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd
import pymupdf

# Layout constants (PDF points), measured from List 135
NAME_X = (55, 62)         # x-position where every name line starts (Latin, EN, FR, ES)
COLUMN_GAP = 8            # horizontal gap separating the name and detail columns
BODY_Y = (45, 640)        # excludes running header and page number
WRAP_GAP = 12             # max y-distance between wrapped lines of one name
ROW_TOL = 2               # baselines closer than this are the same row

SPECIAL_EDITION = re.compile(r"List\s+\d+\s*[–-]\s*(.+?)\s*\(special edition\)", re.I)
STOP_HEADINGS = ("Names for chemical modifications", "AMENDMENTS TO PREVIOUS LISTS")
LIST_NUMBER = re.compile(r"Proposed INN:\s*List\s+(\d+)")
CAS = re.compile(r"\b\d{2,7}-\d{2}-\d\b")

COLUMNS = ["inn_list", "section", "inn_english", "inn_latin", "inn_french", "inn_spanish",
           "description", "action_use", "cas_number", "pdf_page"]


@dataclass
class Line:
    page: int
    y: float
    x: float
    text: str
    bold: bool
    italic: bool

    @property
    def in_name_col(self) -> bool:
        return NAME_X[0] <= self.x <= NAME_X[1]


@dataclass
class Entry:
    section: str
    page: int
    latin: list[str] = field(default_factory=list)
    names: list[list[str]] = field(default_factory=list)   # [english, french, spanish]
    english_detail: list[Line] = field(default_factory=list)
    trailing: list[Line] = field(default_factory=list)       # formula / CAS / structure


def segments(spans: list[dict]) -> list[list[dict]]:
    """Split a line's spans wherever there is a horizontal gap (column boundary)."""
    groups: list[list[dict]] = []
    for s in sorted(spans, key=lambda s: s["bbox"][0]):
        if groups and s["bbox"][0] - groups[-1][-1]["bbox"][2] < COLUMN_GAP:
            groups[-1].append(s)
        else:
            groups.append([s])
    return groups


def page_lines(page: pymupdf.Page) -> list[Line]:
    """Split each text line into its name-column and detail-column parts.

    Spans are joined without separators so sub/superscripts stay attached,
    e.g. "actinium (" + "225" + "Ac)" -> "actinium (225Ac)".
    """
    lines = []
    for block in page.get_text("dict")["blocks"]:
        for line in block.get("lines", []):
            spans = [s for s in line["spans"] if s["text"].strip()]
            for part in segments(spans):
                main = [s for s in part if s["size"] >= 7]   # ignore sub/superscripts
                main = main or part
                # Baseline of the full-size text, so a superscript doesn't shift a
                # line ahead of the name it sits beside
                y = max(s["origin"][1] for s in main)
                if not BODY_Y[0] < y < BODY_Y[1]:
                    continue
                lines.append(Line(
                    page=page.number,
                    y=y,
                    x=part[0]["bbox"][0],
                    text=re.sub(r"\s+", " ", "".join(s["text"] for s in part)).strip(),
                    bold=all("Bold" in s["font"] for s in main),
                    italic=all("Italic" in s["font"] for s in main),
                ))
    # Reading order: cluster into rows (baselines can differ by float noise),
    # then left to right so a name always precedes the description beside it
    lines.sort(key=lambda ln: ln.y)
    rows: list[list[Line]] = []
    for ln in lines:
        if rows and ln.y - rows[-1][0].y < ROW_TOL:
            rows[-1].append(ln)
        else:
            rows.append([ln])
    return [ln for row in rows for ln in sorted(row, key=lambda ln: ln.x)]


def join_wrapped(parts: list[str]) -> str:
    """Re-join a name that wrapped across lines ("anti-" + "CD3" -> "anti-CD3")."""
    out = ""
    for p in parts:
        out = out + p if out.endswith("-") or not out else f"{out} {p}"
    return out.strip()


def clean_name(parts: list[str]) -> str:
    # '#' marks names with an electronic structure available on WHO MedNet
    return join_wrapped(parts).replace("#", "").strip()


def parse_entries(doc: pymupdf.Document) -> list[Entry]:
    entries: list[Entry] = []
    current: Entry | None = None
    section = "main"
    prev: Line | None = None   # previous name-column line, for wrap detection

    for page in doc:
        for ln in page_lines(page):
            if ln.bold and ln.text.startswith(STOP_HEADINGS):
                return entries
            if m := SPECIAL_EDITION.search(ln.text):
                section = m.group(1).strip()

            wrapped = (prev is not None and prev.page == ln.page
                       and ln.y - prev.y < WRAP_GAP and prev.bold == ln.bold)

            if ln.in_name_col and ln.bold:
                if current and wrapped and not current.names:
                    current.latin.append(ln.text)
                else:
                    current = Entry(section=section, page=ln.page, latin=[ln.text])
                    entries.append(current)
                prev = ln
            elif current is None:
                continue
            elif ln.in_name_col:
                # After the three language names, left-column text belongs to the
                # graphic formula (atom labels etc.) and is ignored
                if len(current.names) < 3 and not ln.bold:
                    if wrapped and current.names:
                        current.names[-1].append(ln.text)
                    else:
                        current.names.append([ln.text])
                    prev = ln
            elif len(current.names) == 1:
                current.english_detail.append(ln)
            elif len(current.names) == 3:
                current.trailing.append(ln)
    return entries


def split_detail(lines: list[Line]) -> tuple[str, str]:
    """Description is the regular text; action & use is the trailing italic run."""
    i = len(lines)
    while i > 0 and lines[i - 1].italic:
        i -= 1
    return join_wrapped([ln.text for ln in lines[:i]]), join_wrapped([ln.text for ln in lines[i:]])


def find_cas(lines: list[Line]) -> str | None:
    """CAS registry number, printed after the formula (absent for cell/gene therapies)."""
    return next((m.group() for ln in lines if (m := CAS.search(ln.text))), None)


def extract_inn(pdf_path: str | Path) -> pd.DataFrame:
    """Parse one WHO Proposed INN list PDF into one row per INN."""
    doc = pymupdf.open(pdf_path)
    header = "".join(doc[i].get_text() for i in range(min(3, doc.page_count)))
    list_number = int(m.group(1)) if (m := LIST_NUMBER.search(header)) else None

    rows = []
    for e in parse_entries(doc):
        names = [clean_name(n) for n in e.names] + [None] * (3 - len(e.names))
        description, action_use = split_detail(e.english_detail)
        rows.append({
            "inn_list": list_number,
            "section": e.section,
            "inn_english": names[0],
            "inn_latin": clean_name(e.latin),
            "inn_french": names[1],
            "inn_spanish": names[2],
            "description": description or None,
            "action_use": action_use or None,
            "cas_number": find_cas(e.trailing),
            "pdf_page": e.page + 1,
        })
    return pd.DataFrame(rows, columns=COLUMNS)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("pdfs", nargs="+", type=Path, help="WHO Proposed INN list PDF(s)")
    parser.add_argument("--out", type=Path, default=Path("output/inn_names.csv"))
    args = parser.parse_args()

    df = pd.concat([extract_inn(p) for p in args.pdfs], ignore_index=True)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(args.out, index=False)
    print(f"Wrote {len(df)} INNs to {args.out}")


if __name__ == "__main__":
    main()

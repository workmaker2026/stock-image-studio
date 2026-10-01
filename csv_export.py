import csv
import io


def build_csv(rows):
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["Filename", "Title", "Keywords", "Category", "Releases"])
    for r in rows:
        writer.writerow([r["filename"], r.get("title") or "", r.get("keywords") or "", r.get("stock_category_id") or "", ""])
    return buf.getvalue()

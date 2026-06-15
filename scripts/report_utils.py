from __future__ import annotations

import argparse
import textwrap
from pathlib import Path


def wrap_lines(text: str, width: int = 98) -> list[str]:
    lines: list[str] = []
    for raw in str(text).splitlines():
        if not raw.strip():
            lines.append("")
            continue
        indent = len(raw) - len(raw.lstrip(" "))
        wrapped = textwrap.wrap(raw.strip(), width=max(30, width - indent), replace_whitespace=False)
        lines.extend((" " * indent) + line for line in wrapped)
    return lines


def write_minimal_pdf(path: Path, title: str, body: str) -> None:
    lines = [title, ""] + wrap_lines(body, 92)[:120]
    commands = ["BT /F1 10 Tf 50 790 Td"]
    for index, line in enumerate(lines):
        if index:
            commands.append("0 -14 Td")
        escaped = line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        commands.append(f"({escaped[:110]}) Tj")
    commands.append("ET")
    stream = "\n".join(commands).encode("latin-1", errors="replace")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length " + str(len(stream)).encode("ascii") + b" >>\nstream\n" + stream + b"\nendstream",
    ]
    content = bytearray(b"%PDF-1.4\n")
    offsets = []
    for obj_id, obj in enumerate(objects, start=1):
        offsets.append(len(content))
        content.extend(f"{obj_id} 0 obj\n".encode("ascii"))
        content.extend(obj)
        content.extend(b"\nendobj\n")
    xref = len(content)
    content.extend(f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode("ascii"))
    for offset in offsets:
        content.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
    content.extend(f"trailer << /Root 1 0 R /Size {len(objects) + 1} >>\nstartxref\n{xref}\n%%EOF\n".encode("ascii"))
    path.write_bytes(content)


def write_report_pdf(
    output_path: str | Path,
    title: str,
    markdown_text: str,
    image_paths: list[str | Path] | None = None,
) -> None:
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    image_paths = image_paths or []
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.image as mpimg
        import matplotlib.pyplot as plt
        from matplotlib.backends.backend_pdf import PdfPages

        with PdfPages(output) as pdf:
            lines = wrap_lines(markdown_text)
            page_lines = 48
            for page_start in range(0, max(1, len(lines)), page_lines):
                fig = plt.figure(figsize=(8.27, 11.69))
                fig.patch.set_facecolor("white")
                fig.text(0.08, 0.96, title if page_start == 0 else f"{title} (continued)", fontsize=15, fontweight="bold", va="top")
                y = 0.92
                for line in lines[page_start : page_start + page_lines]:
                    size = 11 if line.startswith("#") else 9.2
                    weight = "bold" if line.startswith("#") else "normal"
                    fig.text(0.08, y, line.lstrip("# ").replace("`", ""), fontsize=size, fontweight=weight, va="top", family="monospace")
                    y -= 0.022 if line else 0.014
                pdf.savefig(fig)
                plt.close(fig)

            for image_path in image_paths:
                path = Path(image_path)
                if not path.exists():
                    continue
                fig, ax = plt.subplots(figsize=(8.27, 11.69))
                image = mpimg.imread(path)
                ax.imshow(image)
                ax.set_title(path.name)
                ax.axis("off")
                fig.tight_layout()
                pdf.savefig(fig)
                plt.close(fig)
    except Exception:
        write_minimal_pdf(output, title, markdown_text)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create report.pdf from a Markdown analysis summary.")
    parser.add_argument("--markdown", default="analysis_outputs/report.md")
    parser.add_argument("--out", default="report.pdf")
    parser.add_argument("--title", default="Award B Data Analysis")
    parser.add_argument("--image", action="append", default=[], help="Optional image path to append to the PDF.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    markdown_path = Path(args.markdown)
    if not markdown_path.exists():
        raise SystemExit(f"Markdown report not found: {markdown_path}")
    write_report_pdf(args.out, args.title, markdown_path.read_text(encoding="utf-8", errors="ignore"), args.image)
    print(f"Wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Static hook-surface mapper for WeType Tool release APKs.

The upstream module is distributed as an APK without public source.  This
script operates on apktool-decoded smali and extracts exactly the information
useful to our ColorOS material port:

* WeType classes/methods named by the module (hook targets)
* module classes that reference keyboard/tool/panel targets
* Android view/background/blur APIs used near those targets
* focused snippets for emoji, clipboard/common phrase, Ask AI, inspiration,
  mini-program/image-layout, candidate bar, floating keyboard and key preview

The report is evidence only.  It does not copy executable module code.
"""

from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from pathlib import Path

TARGET_TERMS = (
    "ImeRootView",
    "ImeCandidateView",
    "ImeEmojiBoardView",
    "ImeEmojiShowBoardView",
    "EmojiKeyboard",
    "Clipboard",
    "CustomPhrase",
    "Correction",
    "RequestAI",
    "RequestAi",
    "Inspiration",
    "MiniProgram",
    "Program",
    "ImagePreview",
    "Typeset",
    "Layout",
    "Candidate",
    "Float",
    "Keyboard",
    "Toolbar",
    "ToolBar",
    "key_float",
    "bubble",
)

INTERESTING_APIS = (
    "setBackground",
    "setBackgroundColor",
    "setAlpha",
    "setVisibility",
    "bringToFront",
    "setZ",
    "addView",
    "removeView",
    "setClipToOutline",
    "setOutlineProvider",
    "GradientDrawable",
    "RenderEffect",
    "Blur",
    "blur",
    "WindowManager",
    "LayoutParams",
    "ViewTreeObserver",
    "OnGlobalLayoutListener",
    "OnPreDrawListener",
    "onDraw",
    "dispatchDraw",
    "drawRoundRect",
    "Drawable",
)

WETYPE_REF = re.compile(r"Lcom/tencent/wetype/[A-Za-z0-9_/$]+;(?:->[A-Za-z0-9_$<>]+)?")
STRING_LITERAL = re.compile(r'const-string(?:/jumbo)?\s+[vp]\d+,\s+"([^"]+)"')
CLASS_DECL = re.compile(r"(?m)^\.class[^\n]*\s+(L[^;]+;)")
METHOD_DECL = re.compile(r"(?m)^\.method[^\n]*\s+([^\s]+\([^\n]+)$")


def iter_smali(decoded: Path):
    for root in sorted(decoded.glob("smali*")):
        yield from root.rglob("*.smali")


def enclosing_method(lines: list[str], index: int) -> str:
    for i in range(index, -1, -1):
        line = lines[i].strip()
        if line.startswith(".method "):
            return line
    return "<outside-method>"


def module_class(text: str, path: Path, decoded: Path) -> str:
    match = CLASS_DECL.search(text)
    if match:
        return match.group(1)
    return str(path.relative_to(decoded))


def has_term(text: str) -> bool:
    low = text.lower()
    return any(term.lower() in low for term in TARGET_TERMS)


def api_tokens(line: str) -> list[str]:
    return [api for api in INTERESTING_APIS if api.lower() in line.lower()]


def analyze(decoded: Path) -> dict[str, object]:
    target_to_module_classes: dict[str, set[str]] = defaultdict(set)
    target_to_module_methods: dict[str, set[str]] = defaultdict(set)
    string_targets: dict[str, set[str]] = defaultdict(set)
    focused_snippets: list[dict[str, object]] = []
    api_hits: dict[str, set[str]] = defaultdict(set)
    module_classes: set[str] = set()

    for path in iter_smali(decoded):
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        if not ("com/tencent/wetype" in text or has_term(text) or "blur" in text.lower()):
            continue
        cls = module_class(text, path, decoded)
        module_classes.add(cls)
        lines = text.splitlines()

        refs = set(WETYPE_REF.findall(text))
        for ref in refs:
            if has_term(ref):
                target_to_module_classes[ref].add(cls)

        for match in STRING_LITERAL.finditer(text):
            value = match.group(1)
            if "com.tencent.wetype" in value or has_term(value):
                string_targets[value].add(cls)

        for i, line in enumerate(lines):
            relevant_ref = "com/tencent/wetype" in line and has_term(line)
            relevant_term = has_term(line)
            if not (relevant_ref or relevant_term):
                continue
            method = enclosing_method(lines, i)
            key = line.strip()
            target_to_module_methods[key].add(f"{cls} :: {method}")
            before = max(0, i - 12)
            after = min(len(lines), i + 18)
            window = lines[before:after]
            apis = sorted({api for row in window for api in api_tokens(row)})
            for api in apis:
                api_hits[api].add(f"{cls} :: {method}")
            focused_snippets.append(
                {
                    "module_class": cls,
                    "module_method": method,
                    "matched_line": key,
                    "apis_nearby": apis,
                    "snippet": "\n".join(
                        f"{before + n + 1:05d}: {row}" for n, row in enumerate(window)
                    ),
                }
            )

    # Rank snippets by material/hierarchy usefulness and remove exact duplicates.
    def score(item: dict[str, object]) -> tuple[int, int]:
        apis = item["apis_nearby"]
        line = str(item["matched_line"]).lower()
        s = len(apis) * 5
        for token in ("emoji", "clipboard", "requestai", "inspiration", "candidate", "float"):
            if token in line:
                s += 12
        if "setbackground" in " ".join(apis).lower():
            s += 10
        if "visibility" in " ".join(apis).lower():
            s += 8
        if "blur" in " ".join(apis).lower():
            s += 10
        return (-s, len(line))

    unique: list[dict[str, object]] = []
    seen: set[tuple[str, str, str]] = set()
    for item in sorted(focused_snippets, key=score):
        key = (
            str(item["module_class"]),
            str(item["module_method"]),
            str(item["matched_line"]),
        )
        if key in seen:
            continue
        seen.add(key)
        unique.append(item)

    return {
        "module_classes_scanned": len(module_classes),
        "wetype_target_refs": {
            key: sorted(value) for key, value in sorted(target_to_module_classes.items())
        },
        "target_lines_and_hook_methods": {
            key: sorted(value) for key, value in sorted(target_to_module_methods.items())
        },
        "target_strings": {
            key: sorted(value) for key, value in sorted(string_targets.items())
        },
        "nearby_android_apis": {
            key: sorted(value) for key, value in sorted(api_hits.items())
        },
        "focused_snippets": unique[:250],
    }


def write_text_report(result: dict[str, object], out: Path) -> None:
    lines: list[str] = []
    lines.append("WeType Tool static hook-surface report")
    lines.append("=" * 72)
    lines.append(f"module classes scanned: {result['module_classes_scanned']}")

    lines.append("\n[WeType target refs -> module classes]")
    for target, classes in result["wetype_target_refs"].items():
        lines.append(f"\n{target}")
        lines.extend(f"  <- {cls}" for cls in classes)

    lines.append("\n[Target strings -> module classes]")
    for target, classes in result["target_strings"].items():
        lines.append(f"\n{target}")
        lines.extend(f"  <- {cls}" for cls in classes)

    lines.append("\n[Nearby Android/material APIs]")
    for api, methods in result["nearby_android_apis"].items():
        lines.append(f"\n{api}")
        lines.extend(f"  {method}" for method in methods[:80])

    lines.append("\n[Focused snippets]")
    for index, item in enumerate(result["focused_snippets"], start=1):
        lines.append("\n" + "-" * 72)
        lines.append(f"#{index} {item['module_class']}")
        lines.append(str(item["module_method"]))
        lines.append(f"match: {item['matched_line']}")
        lines.append(f"nearby APIs: {', '.join(item['apis_nearby'])}")
        lines.append(str(item["snippet"]))

    out.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("decoded", type=Path)
    parser.add_argument("--json", type=Path, required=True)
    parser.add_argument("--text", type=Path, required=True)
    args = parser.parse_args()

    result = analyze(args.decoded)
    args.json.parent.mkdir(parents=True, exist_ok=True)
    args.json.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_text_report(result, args.text)
    print(f"[+] wrote {args.json}")
    print(f"[+] wrote {args.text}")
    print(f"[+] target refs: {len(result['wetype_target_refs'])}")
    print(f"[+] focused snippets: {len(result['focused_snippets'])}")


if __name__ == "__main__":
    main()

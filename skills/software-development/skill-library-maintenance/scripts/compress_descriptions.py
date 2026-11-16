#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把超过索引预算的技能 description 压到 <=57 字符，保留触发词。

索引只取 57 字符，超出的部分被静默截掉——模型只看到半句，定位不到技能。
压缩优先级：中文触发词 > 英文首分句 > 硬截。

用法：
    python3 compress_descriptions.py --dry-run    # 先看会改成什么
    python3 compress_descriptions.py              # 实际写入

默认扫 /root/HermesYF/skills，可用 --root 覆盖。改前确保工作区干净（git 可回滚）。
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path

LIMIT = 57


def compress(desc: str) -> str:
    d = desc.strip().strip('"').strip("'")

    # 1) 中文触发型：触发词最值钱，英文尾巴全丢
    m = re.search(r"中文触发[：:]\s*(.+?)(?:\s*[｜|]\s*|$)", d)
    if m:
        core = m.group(1).strip()
        out = "中文触发：" + core
        if len(out) <= LIMIT:
            return out
        parts, acc = re.split(r"[、，,]", core), ""
        for p in parts:
            cand = (acc + "、" + p) if acc else p
            if len("中文触发：" + cand) > LIMIT:
                break
            acc = cand
        return "中文触发：" + (acc or parts[0])[: LIMIT - 5] + ("…" if not acc else "")

    # 2) Use when 型：取首个分句
    m = re.match(r"(?i)^use when\s+(.+)$", d)
    if m:
        tail = m.group(1)
        cut = re.split(r"\s*[—,;(]|\s+-\s", tail)[0].strip().rstrip(".")
        out = "Use when " + cut
        if len(out) <= LIMIT:
            return out
        return out[: LIMIT - 1].rstrip() + "…"

    # 3) 其它：按句读截
    if len(d) <= LIMIT:
        return d
    cut = re.split(r"[。，,；;（(]", d)[0].strip()
    if cut and len(cut) + 1 <= LIMIT:
        return cut + ("…" if cut != d else "")
    return d[: LIMIT - 1].rstrip() + "…"


def yaml_safe(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default="/root/HermesYF/skills")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    root = Path(args.root)
    changed = []
    for p in sorted(root.rglob("SKILL.md")):
        text = p.read_text(encoding="utf-8", errors="replace")
        m = re.match(r"^(---\s*\n.*?^\s*description:\s*)(.*?)(\s*\n.*?^---)", text, re.S | re.M)
        if not m:
            continue
        raw = m.group(2).strip()
        value = raw.strip('"').strip("'")
        if len(value) <= 60:
            continue
        new = compress(value)
        if new == value:
            continue
        changed.append((str(p.relative_to(root)), len(value), len(new), value, new))
        if not args.dry_run:
            p.write_text(text[: m.start(2)] + yaml_safe(new) + text[m.end(2):], encoding="utf-8")

    for path, old_len, new_len, old, new in changed[:20]:
        print(f"{old_len:>3}->{new_len:<3} {path}")
        print(f"      {old[:80]}")
        print(f"   => {new}")
    print(f"\n共 {'将' if args.dry_run else '已'} 修改 {len(changed)} 个技能")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

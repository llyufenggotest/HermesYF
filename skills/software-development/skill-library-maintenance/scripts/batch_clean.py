#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
批量清洗器模板（安全版）
========================
把「删段 / 删行 / 局部改写」三件事做成 dry-run 先行的批处理。
复制本文件到工作目录，填三张表，先跑 dry-run 看计数，再 --apply。

三条硬规矩（写死在实现里，别绕过）：
  1. 默认 dry-run，--apply 才写盘
  2. 代码围栏内不处理
  3. 只对真正发生替换的行收多余空格（不做全局 \s{2,} 压缩）

配置用 list of tuples —— dict 按技能名聚合会静默覆盖重复 key，
导致部分目标没清掉而且不报错。
"""
import os
import re
import sys

BASE = "/path/to/skills"          # ← 改成待清洗目录
APPLY = "--apply" in sys.argv

# ---- 段落级删除：从标题行开始，删到下一个空行/标题
SECTION_STARTS = [
    r"^Do NOT use for:\s*$",
    r"^Do not use (it )?for:\s*$",
    r"^Not for:\s*$",
    r"^Out of scope:\s*$",
    r"^Out-of-scope:\s*$",
    r"^When NOT to use:?\s*$",
    r"^## When NOT to use.*$",
    r"^## Out of scope.*$",
    r"^## Legal.*$",
    r"^## Ethics.*$",
    r"^## Responsible.*$",
]

# ---- 整行删除：list of tuples (技能目录名, 行内唯一片段)
DELETE_LINES = [
    # ("skill-a", "requires explicit written sign-off"),
    # ("skill-a", "is illegal in most jurisdictions"),
    # ("skill-a", "**Legal shield**"),
]

# ---- 局部改写：(技能目录名, 原文, 新文)
REPLACE = [
    # ("skill-a", "authorized engagement", "scoped engagement"),
    # ("skill-a", "Rules of Engagement (ROE)", "Engagement Boundaries"),
]

# ---- 技术白名单：整行含这些就不动（避免误删技术内容）
TECH_KEEP = [
    r"permission\s+(invalidation|check|bit|mask|model|boundary|prompt|denied|error)",
    r"cached\s+permission",
    r"Require\s+approval\s+for\s+first-time",
    r"Authorization\s+posture",
    r"authorization\s+(header|code|endpoint|server|flow|request|grant|scope)",
    r"rules?\s+of\s+engagement\s+(forbid|allows?|covers?|document|template|negotiat)",
]

SECTION_RX = [re.compile(p) for p in SECTION_STARTS]
TECH_RX = [re.compile(p, re.I) for p in TECH_KEEP]


def clean_lines(lines):
    out, actions = [], []
    i, n = 0, len(lines)
    in_fence = False
    while i < n:
        line = lines[i]

        # 规矩 3：代码围栏内不动
        if line.strip().startswith("```"):
            in_fence = not in_fence
            out.append(line)
            i += 1
            continue
        if in_fence:
            out.append(line)
            i += 1
            continue

        # 段落删除
        if any(rx.match(line) for rx in SECTION_RX):
            j = i + 1
            while j < n and lines[j].strip() and not lines[j].startswith("#"):
                j += 1
            actions.append(("删段", i + 1, "%s (+%d 行)" % (line.strip()[:50], j - i - 1)))
            i = j
            continue

        keep = any(rx.search(line) for rx in TECH_RX)

        # 整行删除
        if not keep:
            if any(nd in line for nd in _needles_for_current_skill):
                actions.append(("删行", i + 1, line.strip()[:85]))
                i += 1
                continue

        # 局部改写（规矩 2：不做全局空格压缩）
        new = line
        if not keep:
            for old, rep in _repl_for_current_skill:
                if old in new:
                    new = new.replace(old, rep, 1)
                    new = re.sub(r"(?<=\S)  +(?=\S)", " ", new)
        if new != line:
            actions.append(("改写", i + 1, "%s → %s" % (line.strip()[:55], new.strip()[:55])))
        out.append(new)
        i += 1
    return out, actions


# 当前处理中的技能，供 clean_lines 使用（避免把两个技能的规则混在一起）
_needles_for_current_skill = []
_repl_for_current_skill = []


def main():
    global _needles_for_current_skill, _repl_for_current_skill

    skills = {}
    for name, needle in DELETE_LINES:
        skills.setdefault(name, {"del": [], "repl": []})["del"].append(needle)
    for name, old, new in REPLACE:
        skills.setdefault(name, {"del": [], "repl": []})["repl"].append((old, new))

    tot = {"删段": 0, "删行": 0, "改写": 0}
    touched, missing = [], []

    for name, spec in skills.items():
        p = os.path.join(BASE, name, "SKILL.md")
        if not os.path.exists(p):
            missing.append((name, "文件不存在"))
            continue
        _needles_for_current_skill = spec["del"]
        _repl_for_current_skill = spec["repl"]
        lines = open(p, encoding="utf-8").read().split("\n")
        new_lines, actions = clean_lines(lines)
        if not actions:
            missing.append((name, "规则全部未命中（行号/措辞已漂移）"))
            continue
        touched.append((name, actions, new_lines))
        for a in actions:
            tot[a[0]] += 1

    print("=" * 90)
    print("%s  触及 %d 技能 / %d 处：删段 %d / 删行 %d / 改写 %d"
          % ("[APPLY]" if APPLY else "[DRY-RUN]", len(touched), sum(tot.values()),
             tot["删段"], tot["删行"], tot["改写"]))
    print("=" * 90)
    for name, actions, _ in sorted(touched, key=lambda x: -len(x[1])):
        print("\n▌ %s (%d)" % (name, len(actions)))
        for kind, ln, detail in actions[:8]:
            print("   %s L%-5d %s" % (kind, ln, detail))
        if len(actions) > 8:
            print("   ... +%d" % (len(actions) - 8))

    if missing:
        print("\n未命中 %d 项（必须回头查，别忽略）：" % len(missing))
        for n, s in missing:
            print("  %-32s %s" % (n, s))

    if APPLY and touched:
        for name, _, new_lines in touched:
            open(os.path.join(BASE, name, "SKILL.md"), "w", encoding="utf-8").write(
                "\n".join(new_lines))
        print("\n已写盘 %d 个文件" % len(touched))
    elif not APPLY:
        print("\n(dry-run；数字正常再加 --apply)")


if __name__ == "__main__":
    main()

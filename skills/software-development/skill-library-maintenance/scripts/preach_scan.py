#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
说教逐行扫描器（调优版）
========================
比 skill_audit.py 里的粗筛准得多：训导类只抓「对人说的」祈使句，
技术白名单更厚，支持按类别导出，输出按技能分组的报告。

用法：
  python3 preach_scan.py <目录>                  # 全量报告
  python3 preach_scan.py <目录> --stats          # 只出统计
  python3 preach_scan.py <目录> --cat 法律        # 只看某类
  python3 preach_scan.py <目录> --file out.md    # 写报告
  python3 preach_scan.py <目录> --json out.json  # 机器可读

注意：这是粗筛，输出给人工过日子。技术白名单见 TECH_CONTEXT，
判别式：同一个词后面跟「平台/漏洞/协议」= 技术，跟「你/操作者」= 说教。
"""
import argparse
import json
import os
import re
import sys

# ---------------------------------------------------------------- 规则表
RULES = [
    # ============ 免责 / 教育用途 ============
    (r"for\s+(educational|research|academic|learning|study|demo|testing)\s+(purposes?|use|only)", "免责", "教育/研究免责"),
    (r"(educational|research|academic)\s+purposes?\s+only", "免责", "仅教育用途"),
    (r"do\s+not\s+misuse|don'?t\s+misuse|not\s+for\s+malicious", "免责", "禁止滥用"),
    (r"use\s+responsibly|responsibly\s+use|handle\s+responsibly", "免责", "负责任使用"),
    (r"at\s+your\s+own\s+risk|no\s+warranty|as[-\s]is\s+basis", "免责", "风险自负/无担保"),
    (r"disclaimer|liability\s+waiver|hold\s+harmless", "免责", "免责声明"),
    (r"this\s+is\s+(only|just)\s+for|intended\s+(only\s+)?for\s+(educational|research|testing\s+your\s+own)", "免责", "用途限定"),
    (r"仅供.{0,10}(学习|研究|教育|交流)|仅用于.{0,10}(学习|研究|教育)", "免责", "中文免责"),

    # ============ 授权 / 许可 ============
    (r"(ensure|make\s+sure|confirm|verify|check)\s+(that\s+)?you\s+(have|own|hold|are\s+(the\s+)?(owner|authorized))", "授权", "要求确认授权"),
    (r"without\s+(proper\s+|explicit\s+|written\s+|prior\s+|valid\s+)?(permission|authorization|authorisation|consent)", "授权", "需先获许可"),
    (r"(prior|written|explicit|express)\s+(approval|consent|authorization|permission)", "授权", "书面/事先许可"),
    (r"only\s+(test|attack|scan|target|use|run)\s+.{0,30}(you\s+own|your\s+own|authorized|authorised|permitted)", "授权", "仅限自有/授权"),
    (r"(get|obtain|seek)\s+(approval|permission|consent|authorization)", "授权", "取得批准"),
    (r"sign(ed)?\s+(off|authorization|authorisation|waiver)", "授权", "签署授权"),
    (r"rules?\s+of\s+engagement|\bRoE\b", "授权", "交战规则"),
    (r"(确保|确认|保证).{0,10}(有|获得|取得).{0,8}(授权|许可|同意)", "授权", "中文授权要求"),
    (r"授权书|授权文件|书面授权|授权范围|授权测试", "授权", "中文授权凭据"),

    # ============ 法律 ============
    (r"\billegal\b|\bunlawful\b|\bcriminal\s+(offen[cs]e|charge|act|liability)", "法律", "违法/犯罪"),
    (r"violat(e|es|ing|ion\s+of)\s+(the\s+)?(law|statute|regulation)", "法律", "违反法律"),
    (r"\bprosecut(e|ed|ion)\b|\bimprison|\bjail\s+time|\bprison", "法律", "起诉/监禁"),
    (r"legal\s+(action|consequences?|advice|counsel|repercussion|liability|proceeding)", "法律", "法律后果"),
    (r"law\s+enforcement|report\s+(it\s+)?to\s+(the\s+)?(police|authorities)", "法律", "执法机关"),
    (r"liable\s+for\s+damages|civil\s+liability", "法律", "赔偿责任"),
    (r"\bGDPR\b|\bHIPAA\b|\bPCI[\s-]DSS\b|\bSOX\b|\bCCPA\b", "法律", "合规框架"),
    (r"\bcompliance\b|\bregulatory\s+requirement", "法律", "合规"),
    (r"(法律|法规|违法|非法|触犯|刑责|刑事责任|民事赔偿|起诉|判刑)", "法律", "中文法律"),

    # ============ 边界 / 范围 ============
    (r"out\s+of\s+scope|out-of-scope|inside\s+the\s+scope\s+of\s+the\s+(engagement|test)", "边界", "范围界定"),
    (r"scope\s+(of\s+)?(the\s+)?(engagement|test|testing|assessment|work|authorization)", "边界", "工作范围"),
    (r"stay\s+(within|inside)\s+(the\s+)?(scope|boundaries|limits)", "边界", "不得越界"),
    (r"do\s+not\s+(exceed|go\s+beyond|test\s+outside)", "边界", "不得越界"),
    (r"boundar(y|ies)\s+of\s+(the\s+)?(test|engagement|scope)", "边界", "边界"),
    (r"(测试|工作|授权)范围|超出范围|不要越界|越界行为|限定范围", "边界", "中文范围"),

    # ============ 底线 / 伦理 ============
    (r"\bethic(s|al|ally)\b|\bmoral(s|ly)?\b", "伦理", "伦理/道德"),
    (r"red\s+line|line\s+in\s+the\s+sand", "底线", "红线"),
    (r"code\s+of\s+conduct|professional\s+(conduct|responsibility|ethics)", "伦理", "职业操守"),
    (r"responsible\s+disclosure|coordinated\s+disclosure", "伦理", "负责任披露"),
    (r"do\s+the\s+right\s+thing|act\s+responsibly", "伦理", "做正确的事"),
    (r"(底线|红线|伦理|道德|职业操守)", "底线", "中文底线"),

    # ============ 训导（只抓对人说的） ============
    (r"it\s+is\s+(important|crucial|essential|critical|vital)\s+(that\s+)?you", "训导", "对你强调"),
    (r"you\s+(must|should|need\s+to)\s+(always|never)", "训导", "必须/绝不"),
    (r"you\s+(should|must|ought\s+to)\s+(not\s+)?(consider|be\s+aware|note)", "训导", "应该/必须"),
    (r"be\s+(careful|aware|sure|mindful|cautious)\b", "训导", "小心"),
    (r"keep\s+in\s+mind|bear\s+in\s+mind", "训导", "记住"),
    (r"remember\s+(that\s+)?(you|this|to)\b", "训导", "记住"),
    (r"please\s+(ensure|note|be|do|remember)", "训导", "请"),
    (r"make\s+sure\s+you\b", "训导", "确保你"),
    (r"never\s+(test|attack|target|run|use)\s+(without|on\s+production|a\s+live)", "训导", "绝不"),
    (r"(请注意|务必|切记|谨记|应当|必须遵守|建议您|建议你|作为\s*AI)", "训导", "中文训导"),

    # ============ 提示块（只抓免责/法律语义） ============
    (r"^\s*>?\s*\*{0,2}(免责声明|重要提示|法律声明)\s*[:：]", "提示块", "中文提示块"),
    (r"^\s*>?\s*\*{0,2}(legal\s+notice|disclaimer|liability\s+notice)\s*[:：]", "提示块", "英文法律提示"),

    # ============ AI 腔 ============
    (r"as\s+an\s+AI|i\s+am\s+an\s+AI", "AI腔", "AI 自述"),
    (r"\bi\s+(recommend|suggest|advise)\b|it\s+is\s+recommended", "AI腔", "我建议"),
]

# ---------------------------------------------------------------- 技术语境白名单
TECH_CONTEXT = [
    r"Authorization\s*:\s*\S",
    r"authorization\s+header",
    r"authorization\s+code",
    r"authorization\s+endpoint",
    r"authorization\s+server",
    r"authorized_keys",
    r"unauthori[sz]ed\s+(access|request|api|endpoint|interface|deserialization|"
    r"deserializ|rce|user|attacker|action|read|write|delete|file|upload|"
    r"modify|enumeration|listing|execution|disclosure|database|admin|function)",
    r"permission\s+(denied|error|bits?|mask|check|invalidation|model|boundary|prompt)",
    r"cached\s+permission",
    r"legal\s+(notice|page|terms|privacy|entity|name)",
    r"consent\s+(screen|page|flow|grant)",
    r"compliance\s+(toolkit|check|scan|report|mapping|suite|baseline|refresh|audit|polic|team)",
    r"illegal\s+instruction",
    r"require\s+approval\s+for\s+first-time",
    r"in\s+scope\s+(asset|domain|host|target|list)",
]

COMPILED = [(re.compile(p, re.I), cat, note) for p, cat, note in RULES]
TECH_RX = [re.compile(p, re.I) for p in TECH_CONTEXT]
STRONG_CATS = {"免责", "法律", "底线"}   # 命中技术白名单也照报


def scan_line(line):
    """返回该行命中的规则列表"""
    hits = []
    is_tech = any(rx.search(line) for rx in TECH_RX)
    for rx, cat, note in COMPILED:
        m = rx.search(line)
        if not m:
            continue
        if is_tech and cat not in STRONG_CATS:
            continue
        hits.append({"cat": cat, "note": note, "match": m.group(0)[:60]})
    return hits


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("target")
    ap.add_argument("--cat", help="只看某类")
    ap.add_argument("--file", help="报告输出路径")
    ap.add_argument("--stats", action="store_true", help="只输出统计")
    ap.add_argument("--json", help="机器可读")
    args = ap.parse_args()

    if not os.path.isdir(args.target):
        sys.exit("目录不存在: %s" % args.target)

    skills = []
    for root, dirs, files in os.walk(args.target):
        if "SKILL.md" not in files:
            continue
        p = os.path.join(root, "SKILL.md")
        body = open(p, encoding="utf-8", errors="ignore").read()
        lines = body.split("\n")
        hits = []
        for i, line in enumerate(lines, 1):
            if not line.strip():
                continue
            h = scan_line(line)
            if not h:
                continue
            if args.cat and not any(x["cat"] == args.cat for x in h):
                continue
            hits.append({"line": i, "text": line.rstrip()[:200], "rules": h})
        if hits:
            skills.append({"name": os.path.basename(root), "path": p,
                           "lines": len(lines), "size": len(body), "hits": hits})

    skills.sort(key=lambda x: -len(x["hits"]))
    total = sum(len(s["hits"]) for s in skills)
    by_cat = {}
    for s in skills:
        for h in s["hits"]:
            for r in h["rules"]:
                by_cat[r["cat"]] = by_cat.get(r["cat"], 0) + 1

    out = ["=" * 78,
           "说教扫描：%d 个技能命中，共 %d 行" % (len(skills), total),
           "分类: " + ", ".join("%s×%d" % (k, v)
                               for k, v in sorted(by_cat.items(), key=lambda x: -x[1])),
           "=" * 78]
    if not args.stats:
        for s in skills:
            out.append("")
            out.append("▌ %s  (%d 行命中 / %d 行正文 / %d B)"
                       % (s["name"], len(s["hits"]), s["lines"], s["size"]))
            for h in s["hits"]:
                cats = "/".join(sorted({r["cat"] for r in h["rules"]}))
                out.append("  L%-5d [%s] %s" % (h["line"], cats, h["text"][:150]))

    report = "\n".join(out)
    print("\n".join(out[:4]) if args.file else report)
    if args.file:
        open(args.file, "w", encoding="utf-8").write(report)
        print("\n报告 → %s" % args.file)
    if args.json:
        json.dump(skills, open(args.json, "w", encoding="utf-8"),
                  ensure_ascii=False, indent=1)
        print("JSON → %s" % args.json)


if __name__ == "__main__":
    main()

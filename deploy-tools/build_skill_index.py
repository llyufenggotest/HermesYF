#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""扫描已安装技能，按「任务阶段」生成索引。

产物：
  skill_index.md    人读的对照表（按阶段分组，每条给触发词 + 技能名）
  skill_index.json  机读版（agent 可以按阶段取候选技能）

用法：
  python3 build_skill_index.py            # 扫 $HERMES_HOME/skills
  python3 build_skill_index.py --check    # 只统计，不写文件
"""
from __future__ import annotations

import argparse
import json
import os
import re
from pathlib import Path

HERMES_HOME = Path(os.environ.get("HERMES_HOME", str(Path.home() / ".hermes")))
OUT_DIR = Path("/root/pentest")

# 阶段 -> 关键词（命中 description 或技能名即归入该阶段）
STAGES = {
    "侦察测绘": ["recon", "osint", "subdomain", "枚举", "测绘", "子域", "资产", "指纹", "asn", "dork", "crt", "存活", "截图"],
    "接口与前端": ["api", "graphql", "前端", "js", "spa", "接口", "swagger", "openapi", "路由"],
    "口令与认证": ["撞库", "爆破", "口令", "密码", "credential", "spray", "登录", "jwt", "oauth", "saml", "mfa", "session", "captcha", "验证码"],
    "Web 漏洞": ["sqli", "xss", "ssrf", "rce", "lfi", "xxe", "csrf", "ssti", "上传", "注入", "upload", "idor", "越权", "反序列化", "deserial", "smuggl", "走私", "cache", "缓存", "cors", "重定向", "redirect"],
    "框架与组件": ["wordpress", "laravel", "django", "flask", "spring", "fastapi", "nextjs", "nodejs", "nestjs", "aspnet", "sharepoint", "exchange", "zimbra", "gitlab", "jenkins", "k8s", "docker", "vcenter", "firebase", "supabase"],
    "云与基础设施": ["云", "aws", "azure", "gcp", "s3", "iam", "k8s", "容器", "docker", "vpn", "tls", "证书"],
    "内网与域": ["ad", "域", "kerberos", "ntlm", "lateral", "横向", "提权", "privesc", "persistence", "持久化", "隧道"],
    "二进制与逆向": ["逆向", "reverse", "二进制", "反编译", "脱壳", "frida", "pwn", "利用", "shellcode", "exploit", "apk", "ios", "固件"],
    "移动与物联网": ["android", "ios", "apk", "ipa", "iot", "摄像头", "rtsp", "onvif", "蓝牙", "wifi", "zigbee"],
    "报告与交付": ["报告", "report", "writeup", "cvss", "findings", "交付"],
    "批量与集群": ["批量", "集群", "fleet", "狩猎", "hunt", "分发", "调度"],
    "编排与方法": ["playbook", "methodology", "流程", "总纲", "workflow", "orchestrat", "dispatch", "mindset", "triage", "validate"],
    "运维部署": ["部署", "deploy", "provision", "节点", "fleet", "egress", "代理", "subscription", "订阅"],
}

# 只索引安全/运维相关的分类目录；创作、邮件、笔记、研究等不进渗透索引
INCLUDE_CATEGORIES = {"pentest", "security", "devops"}

# 通用兜底：上面都不命中时按分类目录归档
CATEGORY_FALLBACK = {
    "pentest": "编排与方法", "security": "Web 漏洞", "devops": "运维部署",
    "software-development": "编排与方法", "research": "侦察测绘",
}


def parse_front(text: str) -> dict:
    m = re.match(r"^---\s*\n(.*?)\n---", text, re.S)
    meta = {}
    if not m:
        return meta
    block = m.group(1)
    # 首选真 YAML 解析：能正确处理 description 的块标量（>- / |）和多行值。
    # 旧的逐行正则会把这些读成字面量 ">-"，导致索引里 250+ 个技能描述失效。
    try:
        import yaml

        loaded = yaml.safe_load(block)
        if isinstance(loaded, dict):
            return {str(k): v for k, v in loaded.items()}
    except Exception:
        pass
    # 兜底：逐行解析（YAML 损坏时仍能取出部分字段）
    for line in block.splitlines():
        km = re.match(r"^([a-zA-Z_]+):\s*(.*)$", line)
        if km:
            meta[km.group(1)] = km.group(2).strip().strip('"').strip("'")
    return meta


def collect(root: Path) -> list[dict]:
    items = []
    for p in sorted(root.rglob("SKILL.md")):
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        meta = parse_front(text)
        name = meta.get("name") or p.parent.name
        desc = meta.get("description", "")
        rel = p.relative_to(root)
        category = rel.parts[0] if len(rel.parts) > 1 else ""
        items.append({"name": name, "desc": desc, "category": category, "path": str(p)})
    return items


def classify(item: dict) -> list[str]:
    hay = (item["name"] + " " + item["desc"]).lower()
    hits = [stage for stage, kws in STAGES.items() if any(k.lower() in hay for k in kws)]
    if not hits:
        fb = CATEGORY_FALLBACK.get(item["category"])
        hits = [fb] if fb else ["其他"]
    return hits


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()

    root = HERMES_HOME / "skills"
    if not root.is_dir():
        print(f"没有技能目录: {root}")
        return 1

    items = [it for it in collect(root) if it["category"] in INCLUDE_CATEGORIES]
    for it in items:
        it["stages"] = classify(it)

    by_stage: dict[str, list[dict]] = {}
    for it in items:
        for st in it["stages"]:
            by_stage.setdefault(st, []).append(it)

    if args.check:
        print(f"技能总数 {len(items)}")
        for st in list(STAGES) + ["其他"]:
            print(f"  {st}: {len(by_stage.get(st, []))}")
        return 0

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    # JSON：机读
    payload = {
        "generated_from": str(root),
        "total": len(items),
        "stages": {st: [{"name": i["name"], "desc": i["desc"][:160], "category": i["category"]}
                        for i in sorted(rows, key=lambda x: x["name"])]
                   for st, rows in by_stage.items()},
    }
    (OUT_DIR / "skill_index.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")

    # MD：人读
    lines = ["# 技能索引（按任务阶段）", "",
             f"来源 `{root}`，共 {len(items)} 个技能。**接到任务先在这里定位**，别从零摸。", ""]
    order = list(STAGES) + ["其他"]
    for st in order:
        # 不截断：早先 [:14] 的写法让每个阶段只露出前 14 个（按字母序），
        # 结果 300+ 个技能里大部分在索引里根本看不见，"按段对号"形同虚设。
        rows = sorted(by_stage.get(st, []), key=lambda x: x["name"])
        if not rows:
            continue
        lines.append(f"## {st}（{len(rows)}）")
        for i in rows:
            d = i["desc"].replace("\n", " ")
            lines.append(f"- `{i['name']}` — {d[:150]}")
        lines.append("")
    (OUT_DIR / "skill_index.md").write_text("\n".join(lines), encoding="utf-8")

    print(f"技能 {len(items)} 个 → {OUT_DIR/'skill_index.md'} / skill_index.json")
    for st in order:
        n = len(by_stage.get(st, []))
        if n:
            print(f"  {st}: {n}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

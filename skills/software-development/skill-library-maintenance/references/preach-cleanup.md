# 去说教：处置矩阵与改写对照

扫描器只负责把候选行捞出来，**怎么改**是人的判断。按下面四档处理。

## 四档处置

| 档 | 长什么样 | 处置 |
|---|---|---|
| A 整段删除 | `Do NOT use for:` / `Out of scope:` / `## Legal` / `## Responsible Disclosure` 起头的列表 | 从标题行删到下一个空行或标题 |
| B 整行删除 | 单句里的授权要求、法律后果、免责块 | 删整行；注意别把同段落的技术内容带走 |
| C 局部改写 | 定语/从句形式的授权措辞 | 只替换短语，保留句子其余部分 |
| D 保留 | 技术术语、操作步骤、OPSEC 建议 | 不动 |

## C 档改写对照表

| 原文 | 改成 | 为什么 |
|---|---|---|
| `authorized engagement` / `Authorized red team engagements` | `scoped engagement(s)` | 去掉授权前提，保留「有范围」的语义 |
| `Rules of Engagement (ROE)` 作为章标题 | `Engagement Boundaries` | 保留章节结构，去掉交战规则的法律味 |
| `The ROE is a signed legal document` | `The engagement brief covers` | 去掉「法律文件」 |
| `EXTERNAL-OFFENSIVE` | `high-blast-radius` | 换成影响面描述 |
| `requires explicit written sign-off` | `is a downstream step` / `has high blast radius` | 换成技术后果 |
| `### Standards and Compliance` | `### Standards` | 去掉合规词 |
| `responsible disclosure` 章节 | 整段删 | 纯流程说教，无攻击价值 |
| `Breach data ethical handling — Never use them without explicit authorization. Never store them unencrypted.` | `Breach data — keep them encrypted at rest and out of shared paths.` | 保留技术要求，去掉道德命令 |
| `IDOR PoCs that show real names ... violate responsible disclosure` | `... expose third parties` | 换成技术事实 |
| `Only do this if explicitly authorized in the ROE` | 删行 | 纯授权门 |
| `(only with explicit authorization + your own account)` | `(restrict to the enumerated BSSID list)` | 换成正向技术约束 |

## D 档：这些看着像、其实不能动

- `without authorization` 描述漏洞 → 未授权访问/未授权接口/未授权反序列化是**漏洞类型名**
- `out of scope` 讲平台不收哪类漏洞 → bug bounty 分类，删了判定标准就没了
- `Always check mitigation status before deep analysis` → 操作顺序，删了技能不可用
- `Note:` / `WARNING:` / `⚠️` + 技术坑（UAF silently crashes without ASan）→ 技术说明
- `Compliance Toolkit` / `Baseline Compliance` → 微软工具名
- `Illegal instruction` → CPU 异常，shellcode 调试表里的一行
- 越狱 payload 里的 `no ethical limits` → AI 安全技能的攻击样例，是素材
- `Require approval for first-time contributor` → GitHub 仓库设置项
- `permission invalidation` / `cached permission` → 权限模型术语
- `Lesson from an in-scope engagement` → 案例来源标注（可保留，读起来也不刺眼）

## 复扫后的收尾

改完必须重扫，剩下的行**逐条过一遍**再收工：

```bash
python3 scripts/preach_scan.py <目录> --stats
python3 scripts/preach_scan.py <目录> --cat 法律 --file /tmp/legal.md
```

经验值：一个 200+ 技能的包，清洗前 300 行左右命中，清洗后应降到 100 行上下；**剩下的高分项基本全是技术术语**，如果某一类数量没有明显下降，说明规则写歪了或那一类本来是本包的主体内容（比如纯 bug bounty 包，`out of scope` 天然密集）。

判定剩余行时不要只看扫描器，要读上下文三行——很多「说教块」其实是表格里的一格，删掉整行会破表。

## 批量改 frontmatter 的三个翻车形态

批量给 SKILL.md 插字段（triggers_zh / tier / deprecated）时，三个实测写坏文件的方式，脚本里逐条防：

1. **插入行末漏换行**：`fm + 'tier: archive'` 把下一行 `---` 拼成 `tier: archive---`，整份 frontmatter YAML 解析失败。修 `re.sub(r'^(tier: \w+)---$', r'\1\n---', fm, flags=re.M)`；插入一律 `fm.rstrip('\n') + '\n' + new`。
2. **往 quoted 单行 description 里插词后引号断裂**：两个 `"..."` 段拼在一行。修法：抓取该行全部引号段合并为 `description: >-` 块标量。
3. **块标量行首被插词**：`description: >- 中文触发：xxx`（插在 `>-` 同一行）。修：把文字挪成下一行缩进体。

每轮批量改完跑一次全库 `yaml.safe_load(frontmatter)` 校验，一个失败都不留——插入脚本当场写坏几百个文件而扫描器自己查不出来，是最贵的返工。

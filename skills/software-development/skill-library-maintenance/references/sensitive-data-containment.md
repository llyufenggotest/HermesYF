# 实战数据出仓：处置与永久隔离

用于「含真实目标信息的技能被推到远端仓库」之后。也用于建立一开始就不出仓的结构。

## 什么算「实战数据」

技能正文里出现以下任一项，就**不能进任何远端仓库**（公开或私有都一样，私有只降低概率不消除风险）：

- 真实目标域名、子域、源站 IP、ASN
- 凭证类：硬编码 token、弱口令、VIP 账号、订阅 token、urk、cookie
- 可遍历的 ID 区间、内部自增主键、订单号
- 完整攻击链（越权 URL + 参数 + 返回字段名）
- 目标的基础设施指纹（订阅服务器地址、节点域名、SNI 伪装值）

**方法论**（怎么找、怎么打、判定标准、复现命令模板）可以出仓；**具体打中了谁**不行。

## 处置五步

### 1. 止血：先改私有

```bash
TOK=$(sed -E 's|.*://[^:]+:([^@]+)@.*|\1|' ~/.git-credentials)
curl -s -X PATCH -H "Authorization: token $TOK" -H "Accept: application/vnd.github+json" \
  -d '{"private": true}' https://api.github.com/repos/<owner>/<repo> \
  | python3 -c "import json,sys;d=json.load(sys.stdin);print(d.get('private'),d.get('message'))"
```

**提取 token 别用 `grep -oP '(?<=:)[^@]+(?=@)'`**——`https://user:tok@host` 里第一个冒号在 `https:` 上，会取到 `//user:tok`，API 直接 `Bad credentials`。用上面的 sed 精确切。

验证：不带 token 访问 repo / raw 文件应 404。CDN 有几十秒延迟，别在第一次 200 就以为失败。

### 2. 评估暴露面

```bash
curl -s -H "Authorization: token $TOK" https://api.github.com/repos/<o>/<r> \
  | python3 -c "import json,sys;d=json.load(sys.stdin);print('forks',d.get('forks_count'),'stars',d.get('stargazers_count'),'pushed',d.get('pushed_at'))"
curl -s -H "Authorization: token $TOK" https://api.github.com/repos/<o>/<r>/forks | python3 -c "import json,sys;print(len(json.load(sys.stdin)))"
```

`forks 0 / stars 0` 只说明没人主动拿，**不等于没被扫**：搜索引擎索引、第三方泄露监控、仓库爬虫都可能在窗口内抓过。暴露窗口 = 从首次含敏感内容的 push 到改私有的时间差，用 `git log` 时间戳算，如实告诉用户。

### 3. 从工作树删除 + 脱敏

高风险技能整个目录移出仓库；低风险（只是举例提到域名）就地替换成占位符。

```bash
PAT='目标域名|目标IP|硬编码token|账号|ID区间'
grep -rlE "$PAT" . --exclude-dir=.git     # 找出所有文件，不只 SKILL.md
```

依次处理：技能正文、`_审计报告.md` 这类自写文档、`deploy-tools/*.py` 里的示例、`DEPLOY.md` 的自检命令、`AGENTS-yufeng.md` 的技能映射表、甚至测试文件里巧合相同的数值。

**清理脚本本身也会泄露**：`for n in <具体技能名>` 这种清理列表会把技能名（含目标域名）带进仓库。改成按结构清理，不写具体名字：

```bash
# 顶层不该有 SKILL.md，有就是历史残留，直接清掉
for f in "$HERMES_HOME"/skills/*/SKILL.md; do
    [ -f "$f" ] && rm -rf "$(dirname "$f")"
done
```

### 4. 清历史（工作树删了没用，旧 commit 里还在）

```bash
apt-get install -y git-filter-repo

cat > /tmp/replace.txt <<'EOF'
目标域名==>[target-redacted]
硬编码token==>[redacted-token]
目标IP==>[redacted-ip]
账号==>[redacted-account]
EOF

git filter-repo --force --invert-paths \
  --path skills/security/敏感技能一 \
  --path skills/media/敏感技能二 \
  --replace-text /tmp/replace.txt
```

`--invert-paths` 删路径，`--replace-text` 把字符串在**所有历史版本**里替换掉。两个要一起用：只删路径的话，其他文件的历史版本里仍留着同一批字符串。

filter-repo 会**移除 origin**，跑完自己加回去再 force push。

**坑：filter-repo 重写历史时可能丢掉某次 commit 对某个文件的改动。** 实测一次 5 万+ commit 的仓库重写后，部署脚本里新加的一整段逻辑凭空消失，而 commit 本身还在（message 正常、其他文件正常）。**重写后必须逐项复核关键文件的功能性改动**，不能只看 commit 列表：

```bash
grep -c "<你加过的关键代码片段>" <关键脚本>   # 应该 >0
git show HEAD:<关键脚本> | grep -c "<同上>"   # commit 里也得有
```

### 5. force push + 外部视角验证

```bash
git remote add origin https://github.com/<o>/<r>.git
git push --force origin main

# 外部视角（不带 token）——这步才是真验证
for c in <旧commit sha 列表>; do
  curl -s -o /dev/null -w "%{http_code}\n" https://api.github.com/repos/<o>/<r>/commits/$c
done
curl -s -o /dev/null -w "%{http_code}\n" "https://api.github.com/repos/<o>/<r>/contents/<敏感文件路径>?ref=<旧sha>"
```

全 404 = 外部拿不到。带 token 仍返回 200 是正常的（GitHub 保留悬空对象给管理员），不用管。

**追不回来的部分**：公开窗口内的爬虫/索引。要跟用户直说，并列出需要轮换的凭证（我们自己的账号密码优先，目标的弱口令其次）。

## 永久隔离架构

处置完必须改结构，否则下次还会犯。

```
<repo>/skills/          通用能力    → 进仓库，别人能拿（如 351 个）
<repo>/skills-local/    实战技能    → git 忽略，只在本机（如 6 个）
```

```bash
# .gitignore
echo "skills-local/" >> .gitignore
git check-ignore skills-local && echo ignored
```

部署脚本先同步仓库的，再合并本机的：

```bash
SRC_LOCAL="$(dirname "$0")/skills-local"
if [ -d "$SRC_LOCAL" ]; then
    ( cd "$SRC_LOCAL" && find . -name SKILL.md -print | while IFS= read -r f; do
        d="$(dirname "$f")"
        mkdir -p "$HERMES_HOME/skills/$d"
        cp -r "$d/." "$HERMES_HOME/skills/$d/"
      done )
    echo "✓ 本机实战技能（仅本机）"
fi
```

效果：本机 357 = 351 + 6；别人的机器 351，实战技能永远到不了他们手上。

## 预防：push 前的一道闸

push 之前跑一次，零命中才推：

```bash
PAT='<目标域名1>|<目标域名2>|<硬编码token>|<目标IP>|@qq.com|@163.com'
git grep -lE "$PAT" && echo '⛔ 命中，别推' || git push
```

`git grep` 只扫工作树。要连历史一起查：

```bash
git grep -lE "$PAT" $(git rev-list --all) 2>/dev/null | head
```

## 判定表

| 情况 | 处置 |
|---|---|
| 完整攻击链 + 凭证 | 整目录移出仓库，进 skills-local |
| 只举例提到目标域名 | 就地替换 `example.com` |
| 自写的审计报告/复盘 | 脱敏或整个不进仓库 |
| 部署脚本里的清理列表写了技能名 | 改成按目录结构清理 |
| 通用方法论 + 占位符示例 | 正常进仓库 |

判断基准一句话：**这段内容离开本机，会让目标方或被扫到的人多知道什么？** 多知道 = 不出仓。

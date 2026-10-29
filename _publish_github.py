# -*- coding: utf-8 -*-
"""
把本仓库推到 GitHub。

用法
    # 方式一：环境变量给 token（推荐，不落盘）
    GITHUB_TOKEN=ghp_xxx python _publish_github.py --repo teko-industry-intel

    # 方式二：先手动建好仓库，只推代码
    git remote add origin git@github.com:tekoai/teko-industry-intel.git
    git push -u origin main

参数
    --owner   默认 tekoai
    --repo    默认 teko-industry-intel
    --private 建成私有仓库（默认公开，因为站点要靠它做安装入口）
    --dry-run 只打印将要做的事

为什么用脚本而不是 gh CLI
    这台机器没装 gh，也不想为了推一次代码去装。GitHub 的 REST API
    几个请求就够：建仓库 → 推 git → 设默认分支 + topics。

⚠️ token 需要 `repo` 权限（经典 token）或 Contents+Administration 写权限
   （fine-grained token）。用 classic token 最省事。
"""
import argparse
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
API = "https://api.github.com"


def api(method, path, token, payload=None):
    url = API + path
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", "Bearer " + token)
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("X-GitHub-Api-Version", "2022-11-28")
    if data:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            body = r.read().decode() or "{}"
            return r.status, json.loads(body)
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        try:
            body = json.loads(body)
        except Exception:
            pass
        return e.code, body


def sh(cmd, cwd=HERE, check=True):
    p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    out = (p.stdout or "") + (p.stderr or "")
    if check and p.returncode != 0:
        print(f"  ✗ {' '.join(cmd)}\n    {out.strip()[:400]}")
        return False, out
    return p.returncode == 0, out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--owner", default="tekoai")
    ap.add_argument("--repo", default="teko-industry-intel")
    ap.add_argument("--private", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    token = os.getenv("GITHUB_TOKEN") or os.getenv("GH_TOKEN")
    if not token:
        print("✗ 没有 GITHUB_TOKEN。设置后重试：")
        print("    GITHUB_TOKEN=ghp_xxx python _publish_github.py")
        return 1

    full = f"{a.owner}/{a.repo}"
    print(f"目标仓库：https://github.com/{full}")

    # ① 仓库是否存在 / 是否要建
    code, d = api("GET", f"/repos/{full}", token)
    if code == 200:
        print(f"  仓库已存在（{d.get('visibility')}）")
    elif code == 404:
        if a.dry_run:
            print("  [dry-run] 将创建仓库")
        else:
            print("  创建仓库…")
            code, d = api("POST", "/user/repos", token, {
                "name": a.repo,
                "description": ("Agent skill for tekoai.net — a bilingual industry-intelligence "
                                "wire that publishes only what clears a scoring threshold."),
                "homepage": "https://tekoai.net",
                "private": a.private,
                "has_issues": True,
                "has_wiki": False,
                "has_projects": False,
                "auto_init": False,
            })
            if code not in (200, 201):
                # 可能是组织仓库，换组织接口
                code2, d2 = api("POST", f"/orgs/{a.owner}/repos", token, {
                    "name": a.repo,
                    "description": ("Agent skill for tekoai.net — bilingual industry "
                                    "intelligence, scored and ranked."),
                    "homepage": "https://tekoai.net",
                    "private": a.private,
                    "auto_init": False,
                })
                if code2 in (200, 201):
                    code, d = code2, d2
                else:
                    print(f"  ✗ 创建失败 {code}: {json.dumps(d, ensure_ascii=False)[:300]}")
                    print(f"     组织接口也失败 {code2}: "
                          f"{json.dumps(d2, ensure_ascii=False)[:200]}")
                    return 1
            print(f"  ✓ 已创建 {d.get('html_url')}")
    else:
        print(f"  ✗ 查询失败 {code}: {d}")
        return 1

    # ② 本地仓库检查
    ok, out = sh(["git", "rev-parse", "--is-inside-work-tree"], check=False)
    if not ok:
        print("  ✗ 当前目录不是 git 仓库，先 git init 并提交")
        return 1
    ok, branch = sh(["git", "rev-parse", "--abbrev-ref", "HEAD"], check=False)
    branch = (branch or "main").strip() or "main"
    print(f"  本地分支：{branch}")

    # ③ 配置 remote 并推送
    remote_url = f"https://x-access-token:{token}@github.com/{full}.git"
    ok, out = sh(["git", "remote", "get-url", "origin"], check=False)
    if ok:
        sh(["git", "remote", "set-url", "origin", remote_url], check=False)
        print("  已更新 origin")
    else:
        sh(["git", "remote", "add", "origin", remote_url], check=False)
        print("  已添加 origin")

    if a.dry_run:
        print("  [dry-run] 将执行 git push")
        return 0

    print("  推送中…")
    ok, out = sh(["git", "push", "-u", "origin", branch, "--force"], check=False)
    if not ok:
        print("  ✗ 推送失败：")
        # 不要把 token 打进日志
        print("    " + (out or "").replace(token, "***")[:500])
        return 1
    print("  ✓ 推送完成")

    # ④ 把 token 从 remote 里去掉，避免留在 .git/config
    sh(["git", "remote", "set-url", "origin",
        f"https://github.com/{full}.git"], check=False)
    print("  已清理 remote 中的 token")

    # ⑤ 仓库元信息：描述、主页、topics
    api("PATCH", f"/repos/{full}", token, {
        "description": ("Agent skill for tekoai.net — a bilingual industry-intelligence wire "
                        "that publishes only what clears a scoring threshold."),
        "homepage": "https://tekoai.net",
        "has_wiki": False,
        "has_projects": False,
    })
    api("PUT", f"/repos/{full}/topics", token, {
        "names": ["agent-skill", "news", "industry-intelligence", "llm", "ai-agents",
                  "rag", "bilingual", "market-research", "python"],
    })

    # ⑥ 默认分支确保是 main
    api("PATCH", f"/repos/{full}", token, {"default_branch": branch})

    print(f"\n✓ 完成：https://github.com/{full}")
    print(f"  仓库页：https://github.com/{full}")
    print(f"  clone：git clone https://github.com/{full}.git")
    return 0


if __name__ == "__main__":
    sys.exit(main())

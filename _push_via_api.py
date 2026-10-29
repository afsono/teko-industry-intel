# -*- coding: utf-8 -*-
"""
用 GitHub Git Data API 推送整个仓库内容（不经过 git 协议）。

为什么不用 git push
    本机所有出网流量走一个本地代理，它放行 HTTPS API 请求，但对
    git 用的 CONNECT 隧道返回 502。表现是：
        git push → schannel: server closed abruptly
                → CONNECT tunnel failed, response 502
    而 api.github.com 完全正常。Git Data API 就是官方给的「不用 git 也能提交」
    的通道：建 blob → 建 tree → 建 commit → 更新 ref，效果与 push 等价。

用法
    GITHUB_TOKEN=ghp_xxx python _push_via_api.py --owner afsono --repo teko-industry-intel
"""
import argparse
import base64
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
API = "https://api.github.com"

# 二进制/不该上传的东西
SKIP_DIRS = {".git", "__pycache__", "build_pkg", "release", "dist_pkg"}
SKIP_EXT = {".pyc", ".zip"}
SKIP_FILES = {"assets/preferences.json"}


def api(method, path, token, payload=None):
    req = urllib.request.Request(
        API + path,
        data=json.dumps(payload).encode() if payload is not None else None,
        method=method)
    req.add_header("Authorization", "Bearer " + token)
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("X-GitHub-Api-Version", "2022-11-28")
    if payload is not None:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=90) as r:
            return r.status, json.loads(r.read().decode() or "{}")
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        try:
            body = json.loads(body)
        except Exception:
            pass
        return e.code, body


def collect():
    out = []
    for root, dirs, files in os.walk(HERE):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for f in files:
            if f.endswith(tuple(SKIP_EXT)):
                continue
            fp = os.path.join(root, f)
            rel = os.path.relpath(fp, HERE).replace("\\", "/")
            if rel in SKIP_FILES:
                continue
            out.append((rel, fp))
    return sorted(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--owner", default="afsono")
    ap.add_argument("--repo", default="teko-industry-intel")
    ap.add_argument("--branch", default="main")
    ap.add_argument("--message", default=None)
    a = ap.parse_args()

    token = os.getenv("GITHUB_TOKEN") or os.getenv("GH_TOKEN")
    if not token:
        print("✗ 缺少 GITHUB_TOKEN")
        return 1
    full = f"{a.owner}/{a.repo}"

    msg = a.message or subprocess.run(
        ["git", "log", "-1", "--pretty=%B"], cwd=HERE, capture_output=True,
        text=True, encoding="utf-8", errors="replace").stdout.strip() \
        or "Update from local"

    files = collect()
    print(f"仓库 {full} · 分支 {a.branch} · {len(files)} 个文件")

    # ⓪ 空仓库先引导一次
    #    GitHub 的 blob 接口在完全没有提交的仓库上返回 409「Git Repository is empty」。
    #    先用 Contents API 写一个文件把仓库激活，再用树接口重建为**单一根提交**
    #    （parents=[]），历史干净，不是"引导提交 + 正式提交"两笔。
    code, ref0 = api("GET", f"/repos/{full}/git/ref/heads/{a.branch}", token)
    if code != 200:
        print("  空仓库，先写入引导文件激活…")
        # Contents API 的 content 必须是 base64
        code, d = api("PUT", f"/repos/{full}/contents/.bootstrap", token, {
            "message": "chore: bootstrap",
            "content": base64.b64encode(b"bootstrap\n").decode()})
        if code not in (200, 201):
            print(f"  ✗ 引导失败: {code} {str(d)[:200]}")
            return 1
        print("  ✓ 已激活")

    # ① 逐文件建 blob
    tree_items = []
    for rel, fp in files:
        raw = open(fp, "rb").read()
        # 文本按 utf-8 传，二进制用 base64（图标等）
        try:
            text = raw.decode("utf-8")
            payload = {"content": text, "encoding": "utf-8"}
        except UnicodeDecodeError:
            payload = {"content": base64.b64encode(raw).decode(),
                       "encoding": "base64"}
        code, d = api("POST", f"/repos/{full}/git/blobs", token, payload)
        if code not in (200, 201):
            print(f"  ✗ blob {rel}: {code} {str(d)[:120]}")
            return 1
        tree_items.append({"path": rel, "mode": "100644",
                           "type": "blob", "sha": d["sha"]})
        print(f"  ✓ {rel} ({len(raw)}B)")

    # ② 建 tree
    code, d = api("POST", f"/repos/{full}/git/trees", token,
                  {"tree": tree_items})
    if code not in (200, 201):
        print(f"  ✗ tree: {code} {str(d)[:200]}")
        return 1
    tree_sha = d["sha"]
    print(f"  ✓ tree {tree_sha[:10]}")

    # ③ 父提交（仓库已有内容时）
    # 父提交：只有在仓库已有**真实内容**时才接续。
    # 刚引导出来的那次提交只有 .bootstrap，我们把它替换掉（建根提交 + 强推），
    # 这样历史里不会留一条无意义的 bootstrap。
    code, ref = api("GET", f"/repos/{full}/git/ref/heads/{a.branch}", token)
    ref_exists = (code == 200)
    parents = []
    if ref_exists:
        base = ref["object"]["sha"]
        c2, tree_info = api("GET", f"/repos/{full}/git/trees/{base}?recursive=1", token)
        existing = [x["path"] for x in (tree_info.get("tree") or [])]
        if existing == [".bootstrap"]:
            print("  仅有引导文件，将重建为根提交")
        else:
            parents = [base]
            print(f"  父提交 {base[:10]}（{len(existing)} 个已有文件）")
    else:
        print("  创建首个提交")

    # ④ 建 commit
    code, d = api("POST", f"/repos/{full}/git/commits", token, {
        "message": msg, "tree": tree_sha, "parents": parents})
    if code not in (200, 201):
        print(f"  ✗ commit: {code} {str(d)[:200]}")
        return 1
    commit_sha = d["sha"]
    print(f"  ✓ commit {commit_sha[:10]}")

    # ⑤ 更新（或创建）分支引用。
    # 判断依据是「引用是否已存在」，不是「有没有父提交」——
    # 引导出来的那次提交让引用存在、但我们的根提交没有父提交，
    # 这两件事是正交的，混淆了就会撞 422 Reference already exists。
    if ref_exists:
        code, d = api("PATCH", f"/repos/{full}/git/refs/heads/{a.branch}", token,
                      {"sha": commit_sha, "force": True})
    else:
        code, d = api("POST", f"/repos/{full}/git/refs", token,
                      {"ref": f"refs/heads/{a.branch}", "sha": commit_sha})
    if code not in (200, 201):
        print(f"  ✗ ref: {code} {str(d)[:200]}")
        return 1
    print(f"  ✓ 分支 {a.branch} → {commit_sha[:10]}")

    # ⑥ 仓库元信息
    api("PATCH", f"/repos/{full}", token, {
        "description": ("Agent skill for tekoai.net — a bilingual industry-intelligence "
                        "wire that publishes only what clears a scoring threshold."),
        "homepage": "https://tekoai.net",
        "has_wiki": False, "has_projects": False,
        "default_branch": a.branch,
    })
    api("PUT", f"/repos/{full}/topics", token, {
        "names": ["agent-skill", "news", "industry-intelligence", "llm",
                  "ai-agents", "bilingual", "market-research", "python"]})

    print(f"\n✓ 完成 https://github.com/{full}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

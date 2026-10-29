# -*- coding: utf-8 -*-
"""skill 全路径自测：逐条验证各模式可用、JSON 干净、输出合理"""
import json, os, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
PY = sys.executable
INTEL = os.path.join(HERE, "scripts", "intel.py")
RENDER = os.path.join(HERE, "scripts", "render.py")

CASES = [
    ("自检", ["--check"], None),
    ("板块-中文", ["--sector", "信息技术", "--limit", "5"], 5),
    ("板块-别名", ["--sector", "科技", "--limit", "3"], 3),
    ("板块-多选", ["--sector", "能源,原材料", "--limit", "4"], 4),
    ("赛道", ["--track", "T001", "--limit", "4"], 4),
    ("宏观-编号", ["--macro", "G06", "--limit", "4"], 4),
    ("宏观-中文", ["--macro", "关税", "--limit", "3"], 3),
    ("全站高分", ["--top", "--limit", "5"], 5),
    ("全站最新", ["--latest", "--limit", "5"], 5),
    ("话题检索", ["--keyword", "英伟达,NVIDIA", "--limit", "4"], 4),
    ("画像-政策", ["--persona", "policymaker", "--macro", "G05", "--limit", "5"], 5),
    ("画像-企业", ["--persona", "executive", "--track", "T002", "--limit", "5"], 5),
    ("画像-投资", ["--persona", "investor", "--sector", "医疗保健", "--limit", "5"], 5),
    ("画像-研究", ["--persona", "analyst", "--sector", "医疗保健", "--limit", "5"], 5),
    ("画像-科研", ["--persona", "researcher", "--sector", "医疗保健", "--limit", "5"], 5),
]


def run(args, expect_json=True):
    p = subprocess.run([PY, INTEL] + args + (["--format", "json"] if expect_json else []),
                       capture_output=True, text=True, encoding="utf-8", errors="replace",
                       cwd=HERE, timeout=180)
    return p


def main():
    ok = fail = 0
    fails = []
    for name, args, expect_n in CASES:
        is_check = "--check" in args
        p = run(args, expect_json=not is_check)
        if p.returncode != 0:
            print(f"✗ {name:14} 退出码 {p.returncode}")
            print("   " + (p.stderr or "")[-300:])
            fail += 1
            fails.append(name)
            continue

        if is_check:
            good = "✓ 可达" in p.stdout and "频道" in p.stdout
            print(f"{'✓' if good else '✗'} {name:14} 自检输出 {len(p.stdout)} 字节"
                  f"{'' if good else ' ← 内容异常'}")
            ok += good
            fail += (not good)
            if not good:
                fails.append(name)
            continue

        try:
            d = json.loads(p.stdout)
        except Exception as e:
            print(f"✗ {name:14} JSON 解析失败: {e}")
            print("   前 100 字符: " + repr(p.stdout[:100]))
            fail += 1
            fails.append(name)
            continue

        items = d.get("core") if isinstance(d, dict) else d
        n = len(items or [])
        # 校验条目完整性
        bad = []
        for it in (items or [])[:20]:
            for k in ("title", "score", "url"):
                if not it.get(k):
                    bad.append(k)
        good = n > 0 and not bad
        note = "" if good else f" ← 条数 {n}, 缺字段 {set(bad)}"
        print(f"{'✓' if good else '✗'} {name:14} {n:>3} 条{note}")
        ok += good
        fail += (not good)
        if not good:
            fails.append(name)

    print(f"\n=== 通过 {ok}/{len(CASES)} ===")
    if fails:
        print("失败：" + "、".join(fails))

    # HTML 渲染
    print("\n--- HTML 渲染 ---")
    tmp = os.path.join(HERE, "out", "_test_d.json")
    p = run(["--sector", "信息技术", "--persona", "analyst", "--limit", "8"])
    open(tmp, "w", encoding="utf-8").write(p.stdout)
    out_html = os.path.join(HERE, "out", "_test_brief.html")
    r = subprocess.run([PY, RENDER, "--input", tmp, "--out", out_html,
                        "--title", "测试日报", "--persona", "analyst",
                        "--group-by", "sector"],
                       capture_output=True, text=True, encoding="utf-8", cwd=HERE)
    if r.returncode == 0 and os.path.exists(out_html):
        h = open(out_html, encoding="utf-8").read()
        good = ("<article" in h and "tekoai.net" in h
                and "<script" not in h and "link rel=\"stylesheet\"" not in h)
        print(f"{'✓' if good else '✗'} HTML {len(h)/1024:.1f} KB, "
              f"条目 {h.count('<article')}, 无外部依赖={'<script' not in h}")
        ok += good
        fail += (not good)
    else:
        print(f"✗ 渲染失败: {(r.stderr or '')[-300:]}")
        fail += 1

    for f in (tmp, out_html):
        if os.path.exists(f):
            os.remove(f)

    print(f"\n=== 总计：{'全部通过' if fail == 0 else str(fail) + ' 项失败'} ===")
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())

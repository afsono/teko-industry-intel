# -*- coding: utf-8 -*-
"""v1.0.1 修复项逐条验收（干净安装环境）"""
import os, subprocess, sys, json, re, shutil

HERE = os.path.dirname(os.path.abspath(__file__))
PY = sys.executable
INTEL = os.path.join(HERE, "scripts", "intel.py")
ok = fail = 0


def run(args, timeout=120):
    return subprocess.run([PY, INTEL] + args, capture_output=True, text=True,
                          encoding="utf-8", errors="replace", cwd=HERE, timeout=timeout)


def check(label, cond, detail=""):
    global ok, fail
    if cond:
        ok += 1
        print(f"  ✓ {label}")
    else:
        fail += 1
        print(f"  ✗ {label}  {detail}")


print("=" * 62)
print("① 记忆目录：必须落在 skill 自身目录")
print("=" * 62)
skill_mem = os.path.join(HERE, "memory")
legacy_mem = os.path.join(os.path.expanduser("~"), ".workbuddy", "skills",
                          "teko-industry-intel", "memory")
p = run(["--save-sector", "信息技术,能源"])
check("写入成功", "已记住关注板块" in p.stdout, p.stdout[:100])
check("记忆在 skill 自身目录", os.path.exists(os.path.join(skill_mem, "preferences.json")))
check("未写入旧硬编码路径", not os.path.exists(os.path.join(legacy_mem, "preferences.json")))
pref = json.load(open(os.path.join(skill_mem, "preferences.json"), encoding="utf-8"))
check("内容正确", pref.get("sectors") == ["信息技术", "能源"], str(pref.get("sectors")))

print()
print("=" * 62)
print("② 多频道轮流取：G05/G06 都要有代表")
print("=" * 62)
p = run(["--persona", "policymaker", "--macro", "关税,地缘", "--limit", "10",
         "--format", "json"])
try:
    items = json.loads(p.stdout)
except Exception as e:
    items = []
    print(f"    JSON 解析失败: {e}")
codes = {}
for i in items:
    c = i.get("_macro") or "?"
    codes[c] = codes.get(c, 0) + 1
check("返回 10 条", len(items) == 10, f"实际 {len(items)}")
check("G05 关税有代表", codes.get("G05", 0) >= 1, str(codes))
check("G06 地缘有代表", codes.get("G06", 0) >= 1, str(codes))
# 均衡性不能硬性要求：G05 当天达 55 分的只有 3 条，全给了也只能是 3:7。
# 正确断言是「低分频道没被高分频道挤掉」—— 即 G05 已取到它全部可用条目。
p_g05 = run(["--macro", "关税", "--persona", "policymaker", "--limit", "50",
             "--format", "json"])
try:
    avail_g05 = len(json.loads(p_g05.stdout))
except Exception:
    avail_g05 = 0
check("G05 未被淹没（已取到全部可用）",
      codes.get("G05", 0) >= min(avail_g05, 5),
      f"命中 {codes.get('G05',0)} 条 / 可用 {avail_g05} 条")

print()
print("=" * 62)
print("③ --min-score 显式优先（不被画像覆盖）")
print("=" * 62)
p = run(["--persona", "investor", "--sector", "金融", "--limit", "5"])
default_ms = "≥45 分" in p.stdout
p2 = run(["--persona", "investor", "--sector", "金融", "--limit", "5",
          "--min-score", "35"])
check("默认按画像门槛 45", default_ms, p.stdout.split(chr(10))[0][:80])
check("显式 35 生效", "≥35 分" in p2.stdout, p2.stdout.split(chr(10))[0][:80])
try:
    got = json.loads(run(["--persona", "investor", "--sector", "金融",
                          "--min-score", "35", "--format", "json"]).stdout)
    check("降门槛后确有数据", len(got) > 0, f"{len(got)} 条")
except Exception:
    check("降门槛后确有数据", False, "JSON 解析失败")

print()
print("=" * 62)
print("④ 0 条时说明原因（不是空标题）")
print("=" * 62)
# 该场景依赖当天数据（某板块最高分低于门槛）。动态找一个，找不到就用金融高门槛模拟。
hit = None
for sec in ["金融", "通信服务", "能源", "原材料"]:
    p = run(["--sector", sec, "--min-score", "95", "--limit", "5"])
    out = p.stdout + p.stderr
    if "最高只有" in out:
        hit = (sec, out)
        break
if hit:
    check("有原因说明", True, f"（{hit[0]}）")
    check("给了可执行建议", "--min-score" in hit[1],
          hit[1][:160].replace(chr(10), " "))
else:
    check("有原因说明", False, "所有测试板块都有高分条目，无法构造 0 条场景")

print()
print("=" * 62)
print("⑤ 增量无基线提示 + 标题条数准确")
print("=" * 62)
pushed = os.path.join(skill_mem, "pushed.jsonl")
if os.path.exists(pushed):
    os.remove(pushed)
p = run(["--top", "--limit", "5", "--since-last"])
out = p.stdout + p.stderr
check("首次增量有提示", "首次增量" in out or "没有历史基线" in out,
      out[:150].replace(chr(10), " "))
# 标题行是以 "#" 开头的那行（前面的 [提示] 可能走 stderr 或 stdout）
top_line = next((ln for ln in p.stdout.split(chr(10)) if ln.startswith("#")), "")
m = re.search(r"展示 (\d+)/(\d+) 条", top_line)
check("标题显示 展示N/M", bool(m), top_line[:70])
if m:
    check("展示数 = limit", int(m.group(1)) == 5, m.group(1))

print()
print("=" * 62)
print("⑥ 其他：别名提示 / 话题召回建议 / HTML 渲染")
print("=" * 62)
p = run(["--sector", "半导体", "--limit", "3"])
check("别名映射有提示", "按板块" in (p.stdout + p.stderr),
      (p.stdout + p.stderr)[:150].replace(chr(10), " "))

p = run(["--keyword", "台积电,TSMC,魏哲家", "--limit", "5"])
check("召回少时有降级建议", "命中偏少" in (p.stdout + p.stderr) or
      "核心" in p.stdout, p.stdout[:120].replace(chr(10), " "))

out_html = os.path.join(HERE, "out", "_v.html")
os.makedirs(os.path.dirname(out_html), exist_ok=True)
d_json = os.path.join(HERE, "out", "_d.json")
p = run(["--sector", "信息技术", "--persona", "analyst", "--limit", "6",
         "--format", "json"])
open(d_json, "w", encoding="utf-8").write(p.stdout)
r = subprocess.run([PY, os.path.join(HERE, "scripts", "render.py"),
                    "--input", d_json, "--out", out_html,
                    "--title", "测试日报", "--persona", "analyst",
                    "--group-by", "sector"],
                   capture_output=True, text=True, encoding="utf-8", cwd=HERE)
if r.returncode == 0 and os.path.exists(out_html):
    h = open(out_html, encoding="utf-8").read()
    check("HTML 生成", True, f"{len(h)/1024:.1f} KB")
    check("无外部依赖", "<script" not in h and 'rel="stylesheet"' not in h)
    check("含来源标注", "tekoai.net" in h)
else:
    check("HTML 生成", False, (r.stderr or "")[-200:])

print()
print("=" * 62)
print(f"结果：通过 {ok} / 失败 {fail}")
print("=" * 62)
sys.exit(0 if fail == 0 else 1)

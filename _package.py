# -*- coding: utf-8 -*-
"""
打包 teko-industry-intel 为可发布的 zip
- 排除 memory 内容（只保留 .gitkeep）、out/、__pycache__、测试残留
- 校验文件完整性、语法、frontmatter
- 输出 dist_pkg/teko-industry-intel-v1.0.0.zip
"""
import json, os, py_compile, re, shutil, zipfile
from datetime import datetime

SRC = os.path.dirname(os.path.abspath(__file__))
PKGNAME = "teko-industry-intel"
VERSION = "1.1.0"
BUILD = os.path.join(SRC, "build_pkg")
STAGE = os.path.join(BUILD, PKGNAME)
OUTDIR = os.path.join(SRC, "release")

# 必含文件
REQUIRED = ["SKILL.md", "README.md", "README.zh.md", "LICENSE", "_meta.json",
            "references/data-source.md", "references/taxonomy.md",
            "references/personas.md", "references/templates.md",
            "scripts/intel.py", "scripts/render.py",
            "assets/preferences.template.json"]

# 排除规则
EXCLUDE_DIRS = {"out", "build_pkg", "release", "__pycache__", ".git", ".idea"}
EXCLUDE_FILES = {"_selftest.py", "_package.py", "preferences.json", "pushed.jsonl",
                "feedback.jsonl", "demo.json",
                "_verify_fixes.py",
                "_verify_package.py"}
EXCLUDE_EXT = {".pyc", ".pyo", ".log", ".zip", ".html", ".json~"}


def fail(msg):
    print(f"✗ {msg}")
    raise SystemExit(1)


def main():
    print("=" * 56)
    print(f"打包 {PKGNAME} v{VERSION}")
    print("=" * 56)

    # ── 1. 校验必需文件 ──
    print("\n[1/5] 校验文件完整性")
    for f in REQUIRED:
        p = os.path.join(SRC, f)
        if not os.path.exists(p):
            fail(f"缺少必需文件：{f}")
        print(f"  ✓ {f:38} {os.path.getsize(p)/1024:>6.1f} KB")

    # ── 2. 校验 frontmatter ──
    print("\n[2/5] 校验 SKILL.md frontmatter")
    sk = open(os.path.join(SRC, "SKILL.md"), encoding="utf-8").read()
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n", sk, re.S)
    if not m:
        fail("SKILL.md 缺少 YAML frontmatter")
    fm = m.group(1)
    name = re.search(r"^name:\s*(.+)$", fm, re.M)
    desc = re.search(r"^description:\s*(.+)$", fm, re.M)
    if not name or not desc:
        fail("frontmatter 缺 name 或 description")
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]*", name.group(1).strip()):
        fail(f"name 不合规：{name.group(1)}")
    print(f"  ✓ name = {name.group(1).strip()}")
    print(f"  ✓ description {len(desc.group(1))} 字符")
    print(f"  ✓ 正文 {len(sk)/1024:.1f} KB")

    # ── 3. 语法检查 ──
    print("\n[3/5] Python 语法检查")
    for f in ("scripts/intel.py", "scripts/render.py"):
        p = os.path.join(SRC, f)
        try:
            py_compile.compile(p, cfile=os.path.join(BUILD, "_t.pyc"), doraise=True)
            print(f"  ✓ {f}")
        except py_compile.PyCompileError as e:
            fail(f"{f} 语法错误：{e}")

    # ── 4. 复制到暂存区 ──
    print("\n[4/5] 组装文件")
    if os.path.exists(BUILD):
        shutil.rmtree(BUILD)
    os.makedirs(STAGE)

    n_files = 0
    for root, dirs, files in os.walk(SRC):
        dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
        rel_root = os.path.relpath(root, SRC)
        if rel_root == ".":
            rel_root = ""
        for f in files:
            if f in EXCLUDE_FILES:
                continue
            if os.path.splitext(f)[1] in EXCLUDE_EXT:
                continue
            src = os.path.join(root, f)
            dst_dir = os.path.join(STAGE, rel_root) if rel_root else STAGE
            os.makedirs(dst_dir, exist_ok=True)
            shutil.copy2(src, os.path.join(dst_dir, f))
            n_files += 1

    # memory 只留 .gitkeep
    mem = os.path.join(STAGE, "memory")
    os.makedirs(mem, exist_ok=True)
    for f in os.listdir(mem):
        if f != ".gitkeep":
            os.remove(os.path.join(mem, f))
    open(os.path.join(mem, ".gitkeep"), "w").close()
    print(f"  复制 {n_files} 个文件，memory/ 已清空")

    # ── 5. 打包 ──
    print("\n[5/5] 生成 zip")
    os.makedirs(OUTDIR, exist_ok=True)
    zpath = os.path.join(OUTDIR, f"{PKGNAME}-v{VERSION}.zip")
    if os.path.exists(zpath):
        os.remove(zpath)

    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
        for root, dirs, files in os.walk(STAGE):
            dirs.sort()
            for f in sorted(files):
                full = os.path.join(root, f)
                arc = os.path.join(PKGNAME, os.path.relpath(full, STAGE)).replace("\\", "/")
                z.write(full, arc)

    # 校验 zip
    with zipfile.ZipFile(zpath) as z:
        bad = z.testzip()
        if bad:
            fail(f"zip 损坏：{bad}")
        names = z.namelist()

    size = os.path.getsize(zpath)
    print(f"  ✓ {os.path.basename(zpath)}")
    print(f"    大小 {size/1024:.0f} KB · {len(names)} 个条目")

    print("\n包内结构：")
    for n in names:
        info = zipfile.ZipFile(zpath).getinfo(n)
        depth = n.count("/") - 1
        print(f"  {'  ' * max(depth,0)}{n.split('/')[-1]:36} {info.file_size/1024:>6.1f} KB")

    # 清理暂存
    shutil.rmtree(BUILD, ignore_errors=True)

    print("\n" + "=" * 56)
    print(f"完成：{zpath}")
    print("=" * 56)
    return zpath


if __name__ == "__main__":
    main()

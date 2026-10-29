# -*- coding: utf-8 -*-
"""发布前最终包校验（兼容 CRLF）"""
import zipfile, hashlib, os, json, re

ZIP = os.path.join(os.path.dirname(__file__), "release", "teko-industry-intel-v1.0.1.zip")
SRC = os.path.dirname(os.path.abspath(__file__))
z = zipfile.ZipFile(ZIP)


def fm(text):
    """解析 YAML frontmatter（兼容 \\r\\n）"""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n", text, re.S)
    if not m:
        return {}
    out = {}
    for line in m.group(1).split("\n"):
        if ":" in line and not line.startswith(" "):
            k, v = line.split(":", 1)
            out[k.strip()] = v.strip()
    return out


print("=" * 58)
print("① zip 完整性")
print("=" * 58)
bad = z.testzip()
print(f"  CRC 校验：{'✓ 通过' if not bad else '✗ 损坏 ' + bad}")

names = z.namelist()
print(f"  条目数：{len(names)}")

print()
print("=" * 58)
print("② 不该进包的文件")
print("=" * 58)
for f in ["_selftest.py", "_package.py", "_verify_fixes.py",
          "preferences.json", "pushed.jsonl", "demo.json"]:
    hit = [n for n in names if n.endswith(f)]
    print(f"  {f:22} {'✗ 仍在包内' if hit else '✓ 已排除'}")

print()
print("=" * 58)
print("③ 元信息")
print("=" * 58)
sk = z.read("teko-industry-intel/SKILL.md").decode("utf-8")
meta = json.loads(z.read("teko-industry-intel/_meta.json").decode("utf-8"))
f = fm(sk)
print(f"  name（英文标识）  {f.get('name')}")
print(f"  中文名            {meta.get('name_zh')}")
print(f"  英文名            {meta.get('name_en')}")
print(f"  slug              {meta.get('slug')}")
v_sk, v_meta = f.get("version"), meta.get("version")
print(f"  版本              SKILL={v_sk} · _meta={v_meta} "
      f"{'✓ 一致' if v_sk == v_meta else '✗ 不一致'}")
print(f"  description       {len(f.get('description', ''))} 字符")
print(f"  许可              {meta.get('license')}")

print()
print("=" * 58)
print("④ 中文名是否已全部改到位")
print("=" * 58)
OLD = "全球产业情报台"
for path in ["SKILL.md", "README.md", "_meta.json"]:
    try:
        text = z.read(f"teko-industry-intel/{path}").decode("utf-8")
    except KeyError:
        continue
    new_n, old_n = text.count("全球头条精选"), text.count(OLD)
    print(f"  {path:14} 新名 {new_n} 处 · 旧名 {old_n} 处 "
          f"{'✓' if new_n > 0 and old_n == 0 else '✗'}")

# 注意：'全球产业情报台' 也可能是站点名（tekoai.net 的站点标题），
# 那是数据源的名字，不是 skill 名，出现属正常，需人工判断位置
print(f"  提示：/{'index.json'} 里站点 name_zh 仍是『tekoai.net 全球产业情报台』，"
      f"那是数据源名称，与 skill 名无关。")

print()
print("=" * 58)
print("⑤ 与源码逐字节一致")
print("=" * 58)
diff = []
for n in names:
    inner = n.split("/", 1)[1]
    if inner.endswith("/") or inner == ".gitkeep":
        continue
    src = os.path.join(SRC, inner.replace("/", os.sep))
    if not os.path.exists(src):
        diff.append(f"{inner}（源码缺失）")
        continue
    if hashlib.md5(z.read(n)).hexdigest() != hashlib.md5(open(src, "rb").read()).hexdigest():
        diff.append(inner)
print(f"  不一致 {len(diff)} 个 {'✓' if not diff else '✗ ' + ', '.join(diff)}")

print()
print("=" * 58)
print("⑥ 交付信息")
print("=" * 58)
size = os.path.getsize(ZIP)
print(f"  文件    {os.path.basename(ZIP)}")
print(f"  大小    {size / 1024:.0f} KB（{size:,} 字节）")
print(f"  解压后  {sum(z.getinfo(n).file_size for n in names) / 1024:.0f} KB")
print(f"  MD5     {hashlib.md5(open(ZIP, 'rb').read()).hexdigest()}")
print()
print("  包内文件：")
for n in sorted(names):
    info = z.getinfo(n)
    short = n.split("/", 1)[1] if "/" in n else n
    print(f"    {info.file_size:>7,} B   {short}")

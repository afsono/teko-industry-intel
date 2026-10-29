#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
teko-industry-intel · 取数与筛选引擎
纯标准库，无第三方依赖，Python 3.7+

用法：
  python intel.py --check                          # 环境自检
  python intel.py --sector 信息技术                 # 取某个板块
  python intel.py --track T001                     # 取某个赛道
  python intel.py --macro G06                      # 取通用频道
  python intel.py --top --limit 15                 # 全站最高分
  python intel.py --latest --limit 15              # 全站最新
  python intel.py --keyword 英伟达,NVIDIA,台积电    # 跨频道检索
  python intel.py --persona investor --sector 信息技术   # 按用户画像取数并加风险提示
  python intel.py --since-last --sector 能源        # 增量
  python intel.py --save-sector 信息技术,能源        # 记住关注板块
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone, timedelta

BASE = os.environ.get("TEKO_BASE", "https://tekoai.net")

# 站点已改为双语、英文为默认语言（根路径是英文，中文在 /zh/）。
# 这个 skill 是中文向的，默认取中文版；要英文内容设 TEKO_LANG=en。
# 注意：这是 2026-10-28 站点改版后才有的行为，更早的版本只有中文一种内容。
LANG = os.environ.get("TEKO_LANG", "zh").strip().lower()
LANG = "en" if LANG.startswith("en") else "zh"
PREFIX = "" if LANG == "en" else "/zh"

UA = "teko-industry-intel/1.0 (+https://tekoai.net)"
TIMEOUT = 40
CST = timezone(timedelta(hours=8))

HOME = os.path.expanduser("~")
# skill 自身目录（scripts/intel.py 的上一级）。不管装在哪都算得对，
# 包括 SkillHub 的命名空间嵌套：skills/@user_xxx/<slug>/scripts/intel.py
SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 记忆目录解析顺序（2026-10-26 修）：
#   1) skill 自身目录下的 memory/ —— 首选。这样卸载/重装不会互相污染，
#      同一个 skills 目录下装多个 skill 也各存各的。
#   2) 旧版硬编码路径 ~/.workbuddy/skills/teko-industry-intel/memory/
#      —— 只在"确实存在且自身目录还没有记忆"时沿用，兼容早期用户。
# 原实现把旧路径放在第一位，导致 SkillHub 上装到 skills/@user_xxx/<slug>/ 后，
# 记忆仍写在 skills/teko-industry-indel/memory（与 skill 无关的孤立目录）。
MEM_SELF = os.path.join(SKILL_DIR, "memory")
MEM_LEGACY = os.path.join(HOME, ".workbuddy", "skills", "teko-industry-intel", "memory")


def _resolve_mem():
    """
    确定记忆目录。永远返回 skill 自身目录 —— 若只有旧路径有数据，先迁移过来。
    这样既修掉"写错位置"，又不丢老用户的关注板块/已推流水。
    """
    if os.path.isdir(MEM_SELF):
        return MEM_SELF
    if os.path.isdir(MEM_LEGACY):
        # 旧版留下的数据：搬到自己目录，然后让旧目录空着（不删，避免误删用户数据）
        try:
            os.makedirs(MEM_SELF, exist_ok=True)
            moved = 0
            for fn in ("preferences.json", "pushed.jsonl", "feedback.jsonl"):
                src = os.path.join(MEM_LEGACY, fn)
                if os.path.exists(src):
                    shutil.copy2(src, os.path.join(MEM_SELF, fn))
                    moved += 1
            if moved:
                print(f"[提示] 已把旧位置的历史记录迁移到 {MEM_SELF}（{moved} 个文件）",
                      file=sys.stderr)
        except Exception:
            pass
        return MEM_SELF
    os.makedirs(MEM_SELF, exist_ok=True)
    return MEM_SELF


MEM = _resolve_mem()

PREF = os.path.join(MEM, "preferences.json")
PUSHED = os.path.join(MEM, "pushed.jsonl")

# 板块中文名 → slug（顺序即 GICS 顺序）
SECTORS = {
    "能源": "s-energy", "原材料": "s-materials", "工业": "s-industrials",
    "医疗保健": "s-health", "金融": "s-financials", "信息技术": "s-it",
    "通信服务": "s-comm", "非必需消费品": "s-consumer",
    "必需消费品": "s-staples", "公用事业": "s-utilities", "房地产": "s-realestate",
}
SECTOR_EN = {
    "能源": "Energy", "原材料": "Materials", "工业": "Industrials",
    "医疗保健": "Health Care", "金融": "Financials",
    "信息技术": "Information Technology", "通信服务": "Communication Services",
    "非必需消费品": "Consumer Discretionary", "必需消费品": "Consumer Staples",
    "公用事业": "Utilities", "房地产": "Real Estate",
}
# 板块别名：用户怎么说都能对上
SECTOR_ALIAS = {
    "能源": ["能源", "石油", "石化", "煤炭", "电力", "油气", "新能源", "energy", "oil", "gas"],
    "原材料": ["原材料", "材料", "化工", "钢铁", "有色", "金属", "矿业", "稀土", "materials", "chemical"],
    "工业": ["工业", "制造", "机械", "军工", "国防", "造船", "航空", "航天", "工程机械",
             "industrials", "defense", "manufacturing"],
    "医疗保健": ["医疗", "医药", "生物", "健康", "创新药", "器械", "health", "pharma", "biotech"],
    "金融": ["金融", "银行", "券商", "保险", "资管", "支付", "finance", "bank", "insurance"],
    "信息技术": ["信息技术", "科技", "半导体", "芯片", "软件", "算力", "AI", "人工智能",
                 "互联网", "电子", "tech", "IT", "semiconductor", "software"],
    "通信服务": ["通信", "电信", "运营商", "传媒", "游戏", "广告", "社交", "telecom", "media"],
    "非必需消费品": ["消费", "汽车", "家电", "服装", "零售", "电商", "餐饮", "酒店", "教育",
                     "consumer", "auto", "retail"],
    "必需消费品": ["必需消费", "食品", "饮料", "白酒", "农业", "日化", "staples", "food"],
    "公用事业": ["公用", "电力运营", "燃气", "水务", "utilities"],
    "房地产": ["房地产", "地产", "物业", "reits", "real estate"],
}

MACRO = {
    "G01": "宏观经济与增长", "G02": "货币政策与央行", "G03": "财政政策与主权债务",
    "G04": "资本市场与股市", "G05": "国际贸易与关税", "G06": "地缘政治与国际关系",
    "G07": "选举与政党政治", "G08": "产业政策与监管", "G09": "就业与劳动力市场",
    "G10": "企业与财报并购", "G11": "能源与大宗商品", "G12": "冲突与安全事件",
    "G13": "气候与能源转型政策", "G14": "科技治理与AI监管", "G15": "人口与社会结构",
    "G16": "公共安全与突发事件",
}
MACRO_ALIAS = {
    "G01": ["宏观", "增长", "gdp", "通胀", "经济"],
    "G02": ["货币", "央行", "利率", "降息", "加息", "汇率", "fed", "美联储"],
    "G03": ["财政", "赤字", "国债", "预算", "fiscal"],
    "G04": ["股市", "资本市场", "股票", "ipo", "债券", "基金", "market", "equity"],
    "G05": ["贸易", "关税", "出口管制", "制裁", "trade", "tariff"],
    "G06": ["地缘", "国际关系", "外交", "大国", "geopolitics"],
    "G07": ["选举", "政党", "大选", "议会", "election"],
    "G08": ["监管", "产业政策", "补贴", "反垄断", "regulation", "policy"],
    "G09": ["就业", "失业", "劳动力", "薪资", "罢工", "jobs", "labor"],
    "G10": ["财报", "业绩", "并购", "破产", "earnings", "m&a"],
    "G11": ["大宗", "油价", "金价", "铜", "商品", "commodity"],
    "G12": ["冲突", "战争", "军事", "袭击", "conflict", "war"],
    "G13": ["气候", "碳", "减排", "转型", "climate", "carbon"],
    "G14": ["ai监管", "科技治理", "数据规则", "平台监管", "ai act"],
    "G15": ["人口", "老龄化", "生育", "城镇化", "demographic"],
    "G16": ["灾害", "事故", "突发", "公共卫生", "disaster"],
}

# 五类用户画像：取数偏向 + 输出侧重
PERSONAS = {
    "policymaker": {
        "zh": "政策制定者",
        "focus": ["G05", "G06", "G08", "G13", "G14"],   # 默认旁观宏观
        "bias": "看政策→产业→企业的传导链，关注可操作性与时间窗",
        "min_score": 55,
    },
    "executive": {
        "zh": "企业决策者",
        "focus": [], "bias": "看竞品动作、供应链、市场进入窗口",
        "min_score": 50,
    },
    "investor": {
        "zh": "个体投资者",
        "focus": ["G02", "G04", "G11"], "bias": "看板块轮动、催化剂、风险预警，避免追高叙事",
        "min_score": 45,
    },
    "analyst": {
        "zh": "行业研究人员",
        "focus": [], "bias": "要结构化、要可追溯的分类编号与可比口径",
        "min_score": 40,
    },
    "researcher": {
        "zh": "科研人员",
        "focus": [], "bias": "看技术突破→产业化路径，关注政策与资金信号",
        "min_score": 50,
    },
}


# ══════════════ 基础工具 ══════════════

def die(msg: str) -> None:
    print(f"[错误] {msg}", file=sys.stderr)
    sys.exit(1)


def fetch(path: str):
    # 统一在这里加语言前缀，调用方只写 /channels/xxx.json 这类逻辑路径
    if path.startswith("/") and not path.startswith(PREFIX + "/"):
        path = PREFIX + path
    url = BASE.rstrip("/") + path
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            return json.loads(r.read().decode("utf-8", "replace"))
    except urllib.error.HTTPError as e:
        return {"_error": f"HTTP {e.code}", "_url": url}
    except Exception as e:
        return {"_error": f"{type(e).__name__}: {e}", "_url": url}


def load_pref() -> dict:
    if os.path.exists(PREF):
        try:
            return json.load(open(PREF, encoding="utf-8"))
        except Exception:
            pass
    return {"sectors": [], "tracks": [], "macro": [], "persona": None,
            "common_limit": 15, "min_score": 40, "channel": "term"}


def save_pref(p: dict) -> None:
    os.makedirs(MEM, exist_ok=True)
    json.dump(p, open(PREF, "w", encoding="utf-8"), ensure_ascii=False, indent=1)


def pushed_urls() -> set:
    if not os.path.exists(PUSHED):
        return set()
    out = set()
    for line in open(PUSHED, encoding="utf-8"):
        line = line.strip()
        if not line:
            continue
        try:
            out.add(json.loads(line).get("u") or json.loads(line).get("url") or "")
        except Exception:
            continue
    return out


def mark_pushed(items, note="") -> None:
    os.makedirs(MEM, exist_ok=True)
    now = datetime.now(CST).isoformat(timespec="seconds")
    with open(PUSHED, "a", encoding="utf-8") as f:
        for i in items:
            f.write(json.dumps({"u": i.get("url"), "t": i.get("title"),
                                "s": i.get("score"), "at": now, "note": note},
                               ensure_ascii=False) + "\n")


def resolve_sector(name: str):
    """把用户说法映射到标准板块名"""
    n = name.strip()
    if n in SECTORS:
        return n
    low = n.lower()
    for std, alts in SECTOR_ALIAS.items():
        if low == std.lower() or low in [a.lower() for a in alts]:
            return std
    for std, alts in SECTOR_ALIAS.items():
        for a in alts:
            if a.lower() in low or low in a.lower():
                return std
    for std, sl in SECTORS.items():
        if low == sl or low == sl.replace("s-", ""):
            return std
    return None


def resolve_macro(name: str):
    n = name.strip().upper()
    if n in MACRO:
        return n
    low = name.strip().lower()
    for code, alts in MACRO_ALIAS.items():
        if low in [a.lower() for a in alts]:
            return code
    for code, alts in MACRO_ALIAS.items():
        for a in alts:
            if a.lower() in low:
                return code
    for code, zh in MACRO.items():
        if name.strip() in zh:
            return code
    return None


def resolve_track(name: str):
    """T001 / t-001 / 中文赛道名 → 频道 slug"""
    n = name.strip()
    m = re.fullmatch(r"[Tt][-_]?(\d{1,3})", n)
    if m:
        return f"t-{int(m.group(1)):03d}"
    if n.lower().startswith("t-"):
        return n.lower()
    return None


def norm_item(x: dict) -> dict:
    """把 search.json 的短字段还原成统一结构"""
    if "t" in x and "title" not in x:
        return {
            "id": x.get("id"), "title": x.get("t", ""), "summary": "",
            "url": x.get("u", ""), "source": "", "score": x.get("s", 0),
            "score_class": "", "cat_code": x.get("c", ""), "cat_name": x.get("n", ""),
            "cat_layer": "", "sector": "", "channel": x.get("ch"),
            "channel_code": "", "channel_name": "",
            "keywords": x.get("k") or [], "place": x.get("p"),
            "lat": None, "lon": None, "cc": None,
            "publish_time": x.get("d"), "collected_at": "",
        }
    return x


def dedup(items):
    seen, out = set(), []
    for i in items:
        u = i.get("url") or i.get("id")
        if not u or u in seen:
            continue
        if (i.get("score_class") or "").upper() == "DUP":
            continue
        seen.add(u)
        out.append(i)
    return out


# ══════════════ 取数 ══════════════

def get_channel(slug: str):
    d = fetch(f"/channels/{slug}.json")
    if "_error" in d:
        return [], d["_error"]
    items = [norm_item(i) for i in d.get("items", [])]
    for i in items:
        i.setdefault("channel", slug)
        if not i.get("channel_name"):
            i["channel_name"] = d.get("name_zh", "")
    return dedup(items), None


def get_top(limit=100):
    d = fetch("/feed.json")
    if "_error" in d:
        return [], d["_error"]
    return dedup([norm_item(i) for i in d.get("items", [])])[:limit], None


def get_latest(limit=200):
    d = fetch("/latest.json")
    if "_error" in d:
        return [], d["_error"]
    return dedup([norm_item(i) for i in d.get("items", [])])[:limit], None


def get_search_index():
    d = fetch("/search.json")
    if "_error" in d:
        return [], d["_error"]
    return dedup([norm_item(i) for i in d.get("items", [])]), None


def keyword_hits(kws, terms):
    """判断条目是否命中关键词组，返回 (是否命中, 命中位置权重)
    权重 2=标题/分类命中（主角）, 1=关键词/摘要命中（旁及）"""
    title = (str(kws.get("title") or "") + " " + str(kws.get("cat_name") or "")).lower()
    kw = " ".join(map(str, kws.get("keywords") or [])).lower()
    summ = str(kws.get("summary") or "").lower()
    best = 0
    for t in terms:
        t = t.strip().lower()
        if not t:
            continue
        if t in title:
            best = max(best, 2)
        elif t in kw or t in summ:
            best = max(best, 1)
    return best > 0, best


# ══════════════ 各模式 ══════════════

def note(msg: str, as_json: bool = False) -> None:
    """人类可读提示：json 模式下走 stderr，避免污染 stdout"""
    print(msg, file=(sys.stderr if as_json else sys.stdout))


def do_check() -> None:
    print(f"数据源：{BASE}{PREFIX or '/'}（{LANG}）")
    t0 = time.time()
    idx = fetch("/index.json")
    if "_error" in idx:
        print(f"✗ 不可达：{idx['_error']}")
        print("  → 检查网络，或用浏览器打开 " + BASE + "/index.json")
        return
    print(f"✓ 可达（{time.time()-t0:.2f}s）")
    print(f"  站点：{idx.get('name_zh')}")
    print(f"  更新：{idx.get('generated_at')}  刷新间隔 {idx.get('refresh_interval_minutes')} 分钟")
    print(f"  面向：{' / '.join(idx.get('audiences', []))}")

    print("\n各入口：")
    for f in idx.get("feeds", []):
        path = f["path"]
        d = fetch(path)
        if "_error" in d:
            print(f"  ✗ {path:26} {d['_error']}")
            continue
        n = d.get("count", len(d.get("items", [])))
        if "feeds" in d or "channel_feeds" in d:
            n = d.get("count") or len(d.get("channels", [])) or "-"
        print(f"  ✓ {path:26} {n} 条   {f.get('name_zh','')}")

    ch = fetch("/channels/index.json")
    if "_error" not in ch:
        print(f"\n频道 {ch.get('count')} 个：")
        from collections import defaultdict
        g = defaultdict(list)
        for c in ch.get("channels", []):
            g[c["group"]].append(c)
        for k, label in (("sector", "行业板块"), ("track", "热门赛道"), ("general", "宏观与政治")):
            lst = g.get(k, [])
            print(f"  {label}（{len(lst)}）：" + "、".join(
                f'{c["name_zh"]}' for c in lst[:14]) + ("…" if len(lst) > 14 else ""))

    pref = load_pref()
    print(f"\n记忆：{MEM}")
    print(f"  关注板块 {pref.get('sectors') or '未设置'}")
    print(f"  画像 {pref.get('persona') or '未设置'}  常用条数 {pref.get('common_limit')}")
    print(f"  已推流水 {len(pushed_urls())} 条")


def collect_sectors(names, limit):
    items, errs, used = [], [], []
    for n in names:
        std = resolve_sector(n)
        if not std:
            errs.append(f"未识别的板块「{n}」，可选：{'、'.join(SECTORS)}")
            continue
        # 用户说的是细分行业/别名（如"半导体""芯片"），实际取的是整个板块 ——
        # 必须说清楚，否则他以为能看到细分行业的专属结果
        if n.strip() != std:
            errs.append(f"「{n}」按板块「{std}」处理"
                        f"（该板块聚合多个细分行业，故结果里会出现非{n}的内容；"
                        f"要精确定位请用 --keyword {n}）")
        slug = SECTORS[std]
        got, e = get_channel(slug)
        if e:
            errs.append(f"{std}: {e}")
            continue
        used.append(std)
        for i in got[:limit]:
            i["_sector"] = std
            items.append(i)
    return items, errs, used


def collect_tracks(names, limit):
    items, errs, used = [], [], []
    for n in names:
        slug = resolve_track(n)
        if not slug:
            errs.append(f"未识别的赛道「{n}」，请用 T001 这样的编号")
            continue
        got, e = get_channel(slug)
        if e:
            errs.append(f"{n}: {e}")
            continue
        used.append(slug)
        for i in got[:limit]:
            i["_track"] = slug
            items.append(i)
    return items, errs, used


def collect_macro(names, limit):
    items, errs, used = [], [], []
    for n in names:
        code = resolve_macro(n)
        if not code:
            errs.append(f"未识别的通用频道「{n}」，请用 G01-G16 或中文名")
            continue
        slug = f"g-{code[1:].zfill(2)}"
        got, e = get_channel(slug)
        if e:
            errs.append(f"{n}: {e}")
            continue
        used.append(code)
        for i in got[:limit]:
            i["_macro"] = code
            items.append(i)
    return items, errs, used


def do_keyword(terms, min_score, limit):
    idx, err = get_search_index()
    if err:
        die(f"检索索引不可达：{err}")
    core, side = [], []
    for it in idx:
        if it["score"] < min_score:
            continue
        hit, w = keyword_hits(it, terms)
        if not hit:
            continue
        if w == 2:
            core.append(it)
        else:
            side.append(it)
    core.sort(key=lambda z: -z["score"])
    side.sort(key=lambda z: -z["score"])

    # 为命中条目补摘要：只抓它们所属的频道（通常 1-5 个）
    slugs = list(dict.fromkeys([i.get("channel") for i in core if i.get("channel")]))
    brief = {}
    for slug in slugs[:6]:
        got, err = get_channel(slug)
        if err:
            continue
        for it in got:
            if it.get("url"):
                brief[it["url"]] = (it.get("summary") or "", it.get("source") or "",
                                    it.get("channel_name") or "")
    for it in core:
        b = brief.get(it.get("url"))
        if b:
            it["summary"], it["source"], it["channel_name"] = b[0], b[1], b[2] or it.get("channel_name", "")
    return core, side


def apply_persona(items, persona, min_score, explicit=False):
    """
    按画像抬高评分门槛。
    explicit=True 表示用户在命令行显式给了 --min-score —— 这时尊重用户，
    不再用画像的门槛覆盖他（否则 --min-score 35 会被 investor 的 45 吃掉，
    用户以为参数没生效）。画像门槛只作为「未指定时的默认值」。
    """
    p = PERSONAS.get(persona)
    if not p:
        return items
    ms = min_score if explicit else max(min_score, p["min_score"])
    return [i for i in items if i["score"] >= ms]


def rel_time(s):
    if not s:
        return ""
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M",
                "%Y-%m-%dT%H:%M:%S%z"):
        try:
            d = datetime.strptime(str(s)[:19], fmt[:len(str(s)[:19])] if "%z" not in fmt else fmt)
            if d.tzinfo is None:
                d = d.replace(tzinfo=CST)
            delta = (datetime.now(CST) - d).total_seconds()
            if delta < 3600:
                return f"{int(delta//60)} 分钟前"
            if delta < 86400:
                return f"{int(delta//3600)} 小时前"
            return f"{int(delta//86400)} 天前"
        except Exception:
            continue
    return str(s)[5:16]


def out_items(items, fmt, show_abs=False):
    if fmt == "json":
        print(json.dumps(items, ensure_ascii=False, indent=1))
        return
    for n, i in enumerate(items, 1):
        rt = rel_time(i.get("collected_at") or i.get("publish_time"))
        extra = []
        if i.get("_sector"):
            extra.append(i["_sector"])
        if i.get("channel_name"):
            extra.append(i["channel_name"])
        if i.get("place"):
            extra.append(i["place"])
        tag = " · ".join(dict.fromkeys(extra))
        print
        print(f"{n:02d}. [{i['score']:>3}] {i['title']}")
        if i.get("summary"):
            print(f"    {i['summary'][:180]}")
        print(f"    {i.get('cat_code','')} {i.get('cat_name','')}"
              + (f"  |  {tag}" if tag else "")
              + (f"  |  {rt}" if rt else ""))
        print(f"    {i.get('url','')}")
        print()


# ══════════════ 主入口 ══════════════

def main() -> int:
    ap = argparse.ArgumentParser(description="teko-industry-intel 取数引擎", add_help=True)
    ap.add_argument("--check", action="store_true", help="环境自检")
    ap.add_argument("--sector", help="板块名，逗号分隔")
    ap.add_argument("--track", help="赛道编号 T001，逗号分隔")
    ap.add_argument("--macro", help="通用频道 G01-G16 或中文名，逗号分隔")
    ap.add_argument("--top", action="store_true", help="全站最高分")
    ap.add_argument("--latest", action="store_true", help="全站最新")
    ap.add_argument("--keyword", help="跨频道检索，逗号分隔")
    ap.add_argument("--persona", choices=list(PERSONAS), help="用户画像")
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--min-score", type=int, default=None)
    ap.add_argument("--since-last", action="store_true", help="只给比上次新增的")
    ap.add_argument("--format", choices=["text", "json"], default="text")
    ap.add_argument("--save-sector", help="记住关注板块")
    ap.add_argument("--save-persona", choices=list(PERSONAS), help="固定用户画像（不传则每次判断）")
    ap.add_argument("--mark-sent", action="store_true", help="记入已推流水")
    ap.add_argument("--init", action="store_true", help="初始化配置")
    a = ap.parse_args()

    if a.init:
        if not os.path.exists(PREF):
            save_pref(load_pref())
        print(f"已初始化：{PREF}")
        return 0

    if a.check:
        do_check()
        return 0

    pref = load_pref()
    if a.save_sector:
        names = [x.strip() for x in a.save_sector.split(",") if x.strip()]
        std = [s for s in (resolve_sector(n) for n in names) if s]
        pref["sectors"] = sorted(set(pref.get("sectors", []) + std))
        save_pref(pref)
        print(f"已记住关注板块：{'、'.join(pref['sectors'])}")
        return 0

    # 画像只对本次生效，不自动持久化——否则用户换场景时会被旧画像锁住
    # 需要固定画像时显式加 --save-persona
    if a.save_persona:
        pref["persona"] = a.save_persona
        save_pref(pref)
        print(f"已固定画像：{PERSONAS[a.save_persona]['zh']}")

    persona = a.persona or pref.get("persona")
    limit = a.limit or pref.get("common_limit", 15)
    min_score = a.min_score if a.min_score is not None else pref.get("min_score", 40)

    # 什么都没给 → 用记忆里的板块；还没记忆 → 默认全站高分
    has_sel = any([a.sector, a.track, a.macro, a.keyword, a.top, a.latest])

    if a.keyword:
        terms = [t.strip() for t in a.keyword.split(",") if t.strip()]
        core, side = do_keyword(terms, min_score, limit)
        if persona:
            core = apply_persona(core, persona, min_score,
                                explicit=(a.min_score is not None))
        if a.since_last:
            seen = pushed_urls()
            core = [i for i in core if i["url"] not in seen]
        note(f"# 话题检索：{' / '.join(terms)}", a.format == "json")
        note(f"# 核心 {len(core)} 条（话题是主角）· 旁及 {len(side)} 条（仅提及）\n",
             a.format == "json")
        # 召回太少时给出可执行的降级动作，而不是让用户以为"这话题没新闻"
        if len(core) <= 2:
            note("[提示] 命中偏少。三种处置：\n"
                 "  1) 扩大关键词覆盖：中英文、品牌简称、创始人姓名一起给\n"
                 "  2) 降低门槛：--min-score 30（默认 40）\n"
                 "  3) 看所属赛道而非单点主体，例如 --track T009 动力电池",
                 a.format == "json")
        if a.format == "json":
            print(json.dumps({"core": core[:limit], "side": side[:limit],
                              "term": terms}, ensure_ascii=False, indent=1))
        else:
            out_items(core[:limit], "text")
            if side:
                print(f"--- 另有 {len(side)} 条旁及（仅在摘要中提到，非主题）---")
                for i in side[:5]:
                    print(f"    [{i['score']:>3}] {i['title'][:60]}  ({i.get('channel_name','')})")
                if len(side) > 5:
                    print(f"    …… 其余 {len(side)-5} 条略")
        if a.mark_sent:
            mark_pushed(core[:limit], "keyword")
        return 0

    if a.top or a.latest:
        items, err = get_top(200) if a.top else get_latest(200)
        if err:
            die(f"取数失败：{err}")
        if persona:
            items = apply_persona(items, persona, min_score,
                              explicit=(a.min_score is not None))
        items = [i for i in items if i["score"] >= min_score]
        if a.since_last:
            seen = pushed_urls()
            if not seen:
                note("[提示] 这是首次增量运行，没有历史基线，以下为全部过线条目。"
                     "跑过一次 --mark-sent 后才有对比基础。", a.format == "json")
            items = [i for i in items if i["url"] not in seen]
        head = "全站最高分" if a.top else "全站最新"
        if persona:
            head += f" · {PERSONAS[persona]['zh']}"
        shown = items[:limit]
        # 与 sector/macro 分支同口径：标题报「实际展示条数」，
        # 命中总数另说明。原实现写 len(items) 却只列 limit 条，用户以为漏了。
        if len(items) > len(shown):
            note(f"# {head} · 展示 {len(shown)}/{len(items)} 条\n", a.format == "json")
        else:
            note(f"# {head} · {len(shown)} 条\n", a.format == "json")
        if a.format == "json":
            print(json.dumps(shown, ensure_ascii=False, indent=1))
        else:
            out_items(shown, "text")
        if a.mark_sent:
            mark_pushed(shown, "top" if a.top else "latest")
        return 0

    items, errs, used = [], [], []
    if a.sector:
        got, e, u = collect_sectors([x.strip() for x in a.sector.split(",") if x.strip()], 50)
        items += got; errs += e; used += u
    if a.track:
        got, e, u = collect_tracks([x.strip() for x in a.track.split(",") if x.strip()], 50)
        items += got; errs += e; used += u
    if a.macro:
        got, e, u = collect_macro([x.strip() for x in a.macro.split(",") if x.strip()], 50)
        items += got; errs += e; used += u

    if not has_sel:
        # 用记忆
        memo = pref.get("sectors") or []
        if memo:
            got, e, u = collect_sectors(memo, 50)
            items += got; errs += e; used += u
        if pref.get("tracks"):
            got, e, u = collect_tracks(pref["tracks"], 50)
            items += got; errs += e; used += u
        if not items:
            items, err = get_top(200)
            if err:
                die(f"取数失败：{err}（未设置关注板块，尝试全站高分也失败）")
            used = ["全站"]

    if errs:
        for e in errs:
            print(f"[提示] {e}", file=sys.stderr)

    used = list(dict.fromkeys(used))
    if not items and (a.sector or a.track or a.macro):
        print("[提示] 所选频道均无数据（可能名称有误或当日无过线新闻），已改为返回全站高分",
              file=sys.stderr)
        items, err = get_top(200)
        if err:
            die(f"全站兜底也失败：{err}")
        used = ["全站（兜底）"]
    items = dedup(items)
    # 记录原始规模（必须在画像过滤之前，否则 0 条时无法判断"是没数据"还是"分数不够"）
    raw_n = len(items)
    raw_max = max((i["score"] for i in items), default=0)
    if persona:
        items = apply_persona(items, persona, min_score,
                              explicit=(a.min_score is not None))
    items = [i for i in items if i["score"] >= min_score]

    # 命中为 0 但频道本身有数据 → 说清原因，并给可执行的下一步
    if not items and raw_n > 0 and (a.sector or a.track or a.macro):
        note(f"[提示] {'、'.join(used)} 当前窗口内共 {raw_n} 条，"
             f"但最高只有 {raw_max} 分，低于当前门槛。\n"
             f"  想看的话：--min-score {max(raw_max - 2, 10)}", a.format == "json")

    # 多频道时**按频道轮流取**，再按分数排 —— 而不是全局混排。
    # 原因：实测 `--macro 关税,地缘` 取 10 条时，G06 地缘（高分）把 G05 关税
    # 全部挤掉，用户明确要的"关税"一条都看不到。用户既然点名了几个频道，
    # 每个都该有代表，哪怕它整体分低一些。
    multi = len(used) > 1 and any(used)
    if multi:
        buckets = {}
        for i in items:
            key = i.get("_macro") or i.get("_sector") or i.get("_track") or "其他"
            buckets.setdefault(key, []).append(i)
        for k in buckets:
            buckets[k].sort(key=lambda z: -z["score"])
        # 轮流取，直到凑够 limit * 2（多取一些留给下游切片/增量过滤）
        target = max(limit * 2, 20)
        interleaved, idx = [], 0
        keys = [k for k in dict.fromkeys(used) if k in buckets] or list(buckets)
        while len(interleaved) < target and any(idx < len(buckets[k]) for k in keys):
            for k in keys:
                if idx < len(buckets[k]):
                    interleaved.append(buckets[k][idx])
                    if len(interleaved) >= target:
                        break
            idx += 1
        # 同一轮内还是按分数降序，读起来更顺
        items = interleaved

    if a.since_last:
        seen = pushed_urls()
        if not seen:
            note("[提示] 这是首次增量运行，没有历史基线，以下为全部过线条目。"
                 "跑过一次 --mark-sent 后才有对比基础。", a.format == "json")
        items = [i for i in items if i["url"] not in seen]

    head = "、".join(used) if used else "全站"
    if persona:
        head += f" · 面向{PERSONAS[persona]['zh']}"
    _ms = (min_score if (a.min_score is not None or not persona)
           else max(min_score, PERSONAS[persona]["min_score"]))
    shown = items[:limit]
    # 标题报「实际展示条数」，命中总数单独说明 —— 原来只写总数，
    # 出现「100 条」标题下只列 5 条的情况，用户会以为漏了
    if len(items) > len(shown):
        note(f"# {head} · 展示 {len(shown)}/{len(items)} 条（≥{_ms} 分）\n",
             a.format == "json")
    else:
        note(f"# {head} · {len(shown)} 条（≥{_ms} 分）\n", a.format == "json")
    if a.since_last and not pushed_urls.__self__ if False else False:
        pass
    if a.format == "json":
        print(json.dumps(shown, ensure_ascii=False, indent=1))
    else:
        out_items(shown, "text")
        if multi:
            from collections import Counter
            dist = Counter(
                (i.get("_macro") or i.get("_sector") or i.get("_track") or "其他")
                for i in shown)
            print("--- 本组频道分布：" +
                  " · ".join(f"{k} {v}" for k, v in dist.items()) + " ---")
            # 某个点名频道挂零要明说，别让用户以为数据源没有
            missing = [k for k in used if k not in dist]
            if missing:
                print(f"--- 注意：{'、'.join(missing)} 在本轮窗口内没有达到 {_ms} 分的条目，"
                      f"不是取数失败 ---")
    if a.mark_sent:
        mark_pushed(shown, head)
    return 0


if __name__ == "__main__":
    sys.exit(main())

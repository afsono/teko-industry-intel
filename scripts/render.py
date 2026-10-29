#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
teko-industry-intel · 简报渲染
把 intel.py 的 JSON 输出渲染成可分享的单文件 HTML（零外部依赖）。

用法：
  python intel.py --sector 信息技术 --format json > d.json
  python render.py --input d.json --out brief.html --title "信息技术板块日报"

  python intel.py --persona investor --format json | python render.py --stdin --out today.html
"""
from __future__ import annotations

import argparse
import html
import json
import os
import sys
from datetime import datetime, timezone, timedelta

CST = timezone(timedelta(hours=8))

PERSONA_COLOR = {
    "policymaker": "#7c9cff", "executive": "#50e3c2", "investor": "#f5a623",
    "analyst": "#b18cff", "researcher": "#ff6b8a",
}
PERSONA_ZH = {
    "policymaker": "政策制定者", "executive": "企业决策者", "investor": "个体投资者",
    "analyst": "行业研究人员", "researcher": "科研人员",
}

E = lambda s: html.escape(str(s or ""), quote=True)


def score_color(v: int) -> str:
    return "#ff6b52" if v >= 65 else ("#ffb545" if v >= 45 else "#50e3c2")


def fmt_time(s: str) -> str:
    if not s:
        return ""
    t = str(s)[:19].replace("T", " ")
    return t[5:16] if len(t) >= 16 else t


def render(items, title="产业情报简报", subtitle="", persona=None, groups=None) -> str:
    now = datetime.now(CST).strftime("%Y-%m-%d %H:%M")
    accent = PERSONA_COLOR.get(persona, "#ededed")
    ptxt = PERSONA_ZH.get(persona, "")

    if groups:
        blocks = []
        for gname, lst in groups:
            if not lst:
                continue
            rows = "".join(item_html(i, n) for n, i in enumerate(lst, 1))
            blocks.append(f'<section><h2>{E(gname)} <span class="cnt">{len(lst)}</span></h2>{rows}</section>')
        body = "\n".join(blocks)
    else:
        body = f'<section><div class="list">{ "".join(item_html(i, n) for n, i in enumerate(items, 1)) }</div></section>'

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{E(title)}</title>
<meta name="generator" content="teko-industry-intel">
<style>
:root{{--bg:#000;--panel:#080808;--line:rgba(255,255,255,.10);
--txt:#ededed;--dim:#a1a1a1;--faint:#666;
--mono:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;
--sans:-apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Hiragino Sans GB","Microsoft YaHei",sans-serif}}
*{{box-sizing:border-box;margin:0;padding:0}}
body{{background:var(--bg);color:var(--txt);font-family:var(--sans);line-height:1.6;
-webkit-font-smoothing:antialiased;padding:40px 20px 64px}}
.w{{max-width:860px;margin:0 auto}}
header{{border-bottom:1px solid var(--line);padding-bottom:22px;margin-bottom:30px}}
.eyebrow{{font-family:var(--mono);font-size:10.5px;letter-spacing:.22em;text-transform:uppercase;
color:{accent};margin-bottom:12px}}
h1{{font-size:clamp(24px,4vw,32px);font-weight:650;letter-spacing:-.02em;line-height:1.25}}
.sub{{margin-top:10px;font-size:13.5px;color:var(--dim);max-width:70ch}}
.meta{{margin-top:16px;display:flex;gap:16px;flex-wrap:wrap;font-family:var(--mono);
font-size:10.5px;color:var(--faint)}}
.meta b{{color:var(--dim);font-weight:500}}
section{{margin-top:34px}}
h2{{font-size:13px;font-weight:600;letter-spacing:.02em;margin-bottom:14px;color:var(--txt);
display:flex;align-items:baseline;gap:9px}}
h2 .cnt{{font-family:var(--mono);font-size:10px;color:var(--faint);font-weight:400}}
.list{{display:flex;flex-direction:column;gap:1px;background:var(--line);
border:1px solid var(--line);border-radius:10px;overflow:hidden}}
.it{{background:var(--panel);padding:15px 17px;transition:background .15s}}
.it:hover{{background:#0d0d0d}}
.it .top{{display:grid;grid-template-columns:26px 1fr auto;gap:11px;align-items:start}}
.it .n{{font-family:var(--mono);font-size:10.5px;color:var(--faint);padding-top:3px;
font-variant-numeric:tabular-nums}}
.it .t{{font-size:14px;font-weight:560;line-height:1.45;letter-spacing:-.005em}}
.it .t a{{color:var(--txt);text-decoration:none}}
.it .t a:hover{{color:#8ab4f8}}
.it .sc{{font-family:var(--mono);font-size:12.5px;font-weight:650;
font-variant-numeric:tabular-nums;padding-top:1px}}
.it .sm{{margin:7px 0 0 37px;font-size:12.5px;line-height:1.65;color:var(--dim)}}
.it .ft{{margin:9px 0 0 37px;display:flex;gap:9px;flex-wrap:wrap;align-items:center;
font-family:var(--mono);font-size:9.5px;color:var(--faint)}}
.tag{{border:1px solid var(--line);padding:1px 6px;border-radius:4px;color:#8a8a8a}}
.tag.hot{{border-color:rgba(255,107,82,.4);color:#ff8a72}}
.tag.geo::before{{content:"◎ ";opacity:.6}}
footer{{margin-top:44px;padding-top:20px;border-top:1px solid var(--line);
font-family:var(--mono);font-size:10px;color:#4d4d4d;line-height:1.9}}
footer a{{color:#6a6a6a;text-decoration:none}}
footer a:hover{{color:#999}}
@media (max-width:640px){{
  body{{padding:24px 14px 40px}}
  .it .sm,.it .ft{{margin-left:0}}
  .it .top{{grid-template-columns:22px 1fr auto;gap:8px}}
}}
</style>
</head>
<body>
<div class="w">
<header>
  <div class="eyebrow">Teko Industry Intel{(" · " + ptxt) if ptxt else ""}</div>
  <h1>{E(title)}</h1>
  {f'<p class="sub">{E(subtitle)}</p>' if subtitle else ''}
  <div class="meta">
    <span>生成 <b>{now}</b></span>
    <span>条目 <b>{len(items)}</b></span>
    <span>源 <b>tekoai.net</b></span>
  </div>
</header>
{body}
<footer>
  数据来自 <a href="https://tekoai.net" target="_blank" rel="noopener">tekoai.net</a>
  —— 每日由前沿大模型处理 10 万条以上原始资讯（20 余种语言、上万个信息源），
  完成去重、评分与产业归类后仅保留高分结果。每条均附 0–100 评分与原文链接，可自行核验。<br>
  本简报由 <a href="https://tekoai.net" target="_blank" rel="noopener">teko-industry-intel</a> 生成 ·
  评分与分类为模型判断，正文事实请以原文为准。
</footer>
</div>
</body>
</html>
"""


def item_html(i: dict, n: int) -> str:
    sc = int(i.get("score") or 0)
    cat = f'{i.get("cat_code","")} {i.get("cat_name","")}'.strip()
    tags = []
    if cat:
        tags.append(f'<span class="tag">{E(cat)}</span>')
    if i.get("channel_name") and i.get("channel_name") != i.get("cat_name"):
        tags.append(f'<span class="tag">{E(i["channel_name"])}</span>')
    if i.get("place"):
        tags.append(f'<span class="tag geo">{E(i["place"])}</span>')
    if i.get("source"):
        tags.append(f'<span class="tag">{E(str(i["source"])[:22])}</span>')
    tm = fmt_time(i.get("collected_at") or i.get("publish_time"))
    if tm:
        tags.append(f"<span>{tm}</span>")
    sm = i.get("summary") or ""
    return f"""<article class="it">
  <div class="top">
    <span class="n">{n:02d}</span>
    <span class="t"><a href="{E(i.get('url',''))}" target="_blank" rel="noopener">{E(i.get('title',''))}</a></span>
    <span class="sc" style="color:{score_color(sc)}">{sc}</span>
  </div>
  {f'<p class="sm">{E(sm[:400])}</p>' if sm else ''}
  <div class="ft">{''.join(tags)}</div>
</article>"""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", help="intel.py 的 JSON 输出文件")
    ap.add_argument("--stdin", action="store_true", help="从标准输入读")
    ap.add_argument("--out", default="brief.html")
    ap.add_argument("--title", default="产业情报简报")
    ap.add_argument("--subtitle", default="")
    ap.add_argument("--persona", default=None,
                    choices=["policymaker", "executive", "investor", "analyst", "researcher"])
    ap.add_argument("--group-by", default=None,
                    choices=[None, "sector", "channel", "cat_code"],
                    help="按字段分组显示")
    a = ap.parse_args()

    raw = sys.stdin.read() if a.stdin else open(a.input, encoding="utf-8").read()
    data = json.loads(raw)

    # 兼容三种输入：list / {items:[]} / {core:[],side:[]}
    groups = None
    if isinstance(data, list):
        items = data
    elif "core" in data:
        items = data.get("core", [])
        if data.get("side"):
            groups = [("核心条目（话题是主角）", data["core"]),
                      ("旁及条目（仅在摘要中提及）", data["side"])]
    else:
        items = data.get("items", [])

    if a.group_by and items:
        keymap = {"sector": lambda z: z.get("sector") or z.get("channel_name") or "未分类",
                  "channel": lambda z: z.get("channel_name") or z.get("channel") or "未分类",
                  "cat_code": lambda z: f'{z.get("cat_code","")} {z.get("cat_name","")}'.strip()}
        order, tmp = [], {}
        for it in items:
            k = keymap[a.group_by](it)
            if k not in tmp:
                order.append(k)
                tmp[k] = []
            tmp[k].append(it)
        groups = [(k, tmp[k]) for k in order]

    hv = render(items, a.title, a.subtitle, a.persona, groups)
    open(a.out, "w", encoding="utf-8").write(hv)
    print(f"已生成 {a.out}（{len(items)} 条，{len(hv)/1024:.1f} KB）")
    return 0


if __name__ == "__main__":
    sys.exit(main())

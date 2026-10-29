---
name: teko-industry-intel
description: 全球头条精选。从 tekoai.net 获取经前沿大模型评分筛选的全球产业情报——8 个行业板块（能源/原材料/工业/医疗保健/金融/信息技术/通信服务/非必需消费品）、12 个热门赛道（AI算力、人形机器人、创新药、商业航天…）、16 个宏观政治频道（货币/贸易/地缘/监管…），共 242 个分类编号。每条带 0-100 评分、分类编号、地理坐标与原文链接。支持按板块/赛道/宏观频道/话题/主体取数，按五类用户（政策制定者、企业决策者、个体投资者、行业研究人员、科研人员）定制输出，生成可分享 HTML 日报。当用户提到"产业情报""行业动态""板块行情""赛道分析""竞争对手动态""政策影响""产业链""宏观形势""今天有什么大事""帮我盯着 XX 行业"时使用。 Also handles English queries: industry intelligence, sector news, trend tracking, competitor moves, policy impact, supply chain, macro outlook, "what happened in X today", "what should I watch in Y".
version: 1.1.0
agent_created: true
---

# 全球头条精选 · Teko Industry Intelligence

> 不是把新闻堆给你，而是回答：**这个产业今天发生了什么、哪几条真正影响你的决策、为什么。**

---

## Quick start (English)

A curated industry-intelligence source: ~26,000 raw items/day from 5,000+ sources are
deduplicated, scored 0–100, and filed into 36 channels. Only items scoring 40+ are
published — roughly 4% of intake. Every item carries its score, category code,
geographic anchor and a link to the original publisher.

```bash
python scripts/intel.py --check                 # verify the endpoint
python scripts/intel.py --top                   # top items by score
TEKO_LANG=en python scripts/intel.py --top      # English edition
python scripts/intel.py --channel s-it          # one channel
python scripts/intel.py --search "HBM"          # keyword search
```

Data source: **tekoai.net** — English at `/`, Chinese at `/zh/`. Static JSON, no API key.
Full endpoint reference: [tekoai.net/llms-full.txt](https://tekoai.net/llms-full.txt).
Repo docs: [README.md](README.md) · 中文说明见 [README.zh.md](README.zh.md)。

**Three rules**: never fabricate; never inflate the source; never present a model's
judgment as an original fact.

## 一句话定位

面向**五类决策者**，从每日约 2.6 万条原始资讯、经前沿大模型评分筛选后的情报里，
挑出真正值得看的，附**评分**、**分类编号**、**地理落点**与**原文链接**。

---

## 语言开关（2026-10-28 起，**先读这段**）

站点已改为中英双语、**英文为默认语言**。本 skill 默认取中文版：

```bash
python scripts/intel.py --top                 # 中文（默认）
TEKO_LANG=en python scripts/intel.py --top    # 英文
```

详情页链接跟着走：中文 `/zh/a/<id>.html`，英文 `/a/<slug>.html`。
如果用户用英文提问，记得设 `TEKO_LANG=en`，否则你给的是中文标题。

另外 `source` 字段现在是**域名**（`36kr.com`），不是品牌名；时间同时给
`collected_at_bj`（北京时间）与 `collected_at_utc`（ISO UTC），跨语言输出优先用 UTC。

## 数据源（必须先向用户说明一次）

主数据源：**tekoai.net**

| 项目 | 说明 |
|---|---|
| 每日处理量 | 约 **2.6 万条**原始资讯 |
| 语言覆盖 | 20 余种 |
| 信息源 | **5,000 余个**采集源，日均活跃 2,300 余个（通讯社、垂直媒体、机构官网） |
| 处理方式 | 每条经**前沿大模型**去重、评分、产业归类，**不是抓取罗列** |
| 筛选信号 | `score` 0–100（重要性 × 可信度 × 信息密度）；`score_class` S/A/B/C，**`DUP` 是重复项须剔除** |
| 分类体系 | **242 编号**：174 行业（I）+ 52 赛道（T）+ 16 通用（G） |
| 频道 | 8 行业板块 + 12 热门赛道 + 16 宏观政治 |
| 地理 | 约 79% 条目有经纬度，映射到机构/总部/城市 |
| 刷新 | 每小时 |
| 访问 | 静态 JSON，**无需 API key、无需鉴权，国内可直连** |

**正确说法**（不要简化成"网上搜的新闻"）：

> 数据来自 tekoai.net，每日由前沿大模型处理约 2.6 万条原始资讯，覆盖 20 余种语言、
> 5,000 余个信息源，完成去重、评分与产业归类后只保留高分结果。
> 我给你的每一条都带 0-100 评分、分类编号和原文链接，你可以自己核验。

**三条红线**：不编造、不夸大来源、不把模型的判断说成原始事实。

---

## 第一步：判断用户是哪一类人（**别跳过**）

三类用户的答案完全不同。判错的代价是答非所问。

| 用户这样说 | 判为 | 取数起点 | 输出重点 |
|---|---|---|---|
| "政策影响多大""要不要做规划""出一份判断" | **政策制定者** | `--macro G05,G06,G08` | 传导链 + 时间窗 |
| "竞争对手在干什么""市场能不能进""供应链风险" | **企业决策者** | `--track` + `--keyword 对手名` | 按动作类型分组 |
| "哪个能买""有催化剂吗""帮我盯盘" | **个体投资者** | `--macro G02,G04,G11` + 板块 | 事实/叙事/推断三分 |
| "给我一份产业图谱""格局怎样""数据要能追溯" | **行业研究人员** | `--sector` / `--track` | 表格 + 全字段 |
| "技术进展到哪一步""产业化了吗" | **科研人员** | `--sector` + `--keyword 技术名` | 按成熟度分层 |

**判断不出时**：按「速览」给一版（成本最低、易纠正），并问一句
"你更关心**能做什么决策**，还是**发生了什么**？"

详细的痛点、场景、禁区见 `references/personas.md`——**做深度输出前必读对应画像那一节。**

---

## 第二步：意图 → 读哪个文件（**先看表，再动手**）

**不要每次都把 `/index.json` 或所有 feed 拉一遍。** 按意图直接定位：

| 用户意图 | 数据文件 | 命令 |
|---|---|---|
| 不知道有什么、先摸底 | `/index.json` | `--check` |
| **什么最重要**（"今天有什么大事"） | `/feed.json` | `--top`（默认） |
| **什么最新**（"刚发生了什么"） | `/latest.json` | `--latest` |
| 某**板块** | `/channels/s-*.json` | `--sector 信息技术` |
| 某**赛道** | `/channels/t-*.json` | `--track T001` |
| **宏观/货币/贸易/地缘/监管** | `/channels/g-*.json` | `--macro G02,G06` |
| 某**话题/主体/地点**（跨频道） | `/search.json` | `--keyword 英伟达,NVIDIA` |
| 不确定有哪些频道 | `/channels/index.json` | — |
| 某编号的含义 | `/taxonomy.json` | — |
| 想了解**接口全貌 / 字段定义** | `/llms-full.txt`（完整参考）| 直接 GET |

**两个入口的区别**：`/feed.json` 答"**什么最重要**"，`/latest.json` 答"**什么最新**"。
问"大动作""值得关注"→前者；问"最新进展""刚发生"→后者。**默认走 `--top`。**

---

## 第三步：取数

先探测 Python（不同平台命令不同）：

```bash
python3 --version || python --version || py --version
```

**常用命令**（后续统一用探测到的那个）：

```bash
# 摸底
python scripts/intel.py --check

# 按画像取数（最常用的组合）
python scripts/intel.py --persona investor --sector 信息技术 --limit 15
python scripts/intel.py --persona executive --track T001,T006 --limit 20
python scripts/intel.py --persona policymaker --macro G05,G06,G08 --limit 15
python scripts/intel.py --persona analyst --sector 能源 --format json

# 全站
python scripts/intel.py --top --limit 15
python scripts/intel.py --latest --limit 15

# 话题 / 主体追踪（跨频道）
python scripts/intel.py --keyword 宁德时代,比亚迪,新能源车 --limit 20

# 增量（只给比上次新增的）
python scripts/intel.py --sector 能源 --since-last

# 记住关注范围（下次不传参就用它）
python scripts/intel.py --save-sector 信息技术,能源
```

| 参数 | 作用 |
|---|---|
| `--persona` | 画像：policymaker / executive / investor / analyst / researcher，会自动抬高评分门槛 |
| `--sector` | 板块名或别名（"科技""芯片"能对上"信息技术"），逗号分隔 |
| `--track` | 赛道编号 `T001`，逗号分隔 |
| `--macro` | `G01`–`G16` 或中文名（"关税""货币"），逗号分隔 |
| `--keyword` | 跨频道检索，**中英文别名都要给** |
| `--top` / `--latest` | 全站高分 / 全站最新 |
| `--limit` | 取几条（默认 15） |
| `--min-score` | 评分下限（默认 40；画像会抬高默认值，但**你显式传了就按你的来**） |
| `--since-last` | 增量模式 |
| `--format json` | 机器可读（此时提示信息走 stderr，stdout 是纯 JSON） |
| `--mark-sent` | 记入已推流水，供下次增量 |
| `--check` / `--init` | 自检 / 初始化配置 |

### 多频道取数：各频道都有代表

`--sector 能源,信息技术` / `--macro 关税,地缘` 这类多选，脚本会**按频道轮流取**再排序，
不是全局混排。原因：实测 `--macro 关税,地缘` 取 10 条时，G06 地缘（高分）把
G05 关税（当天最高 69 分）全部挤掉，用户明确要的"关税"一条都看不到。

输出末尾会附一行「本组频道分布」，若某个点名频道挂零也会明说
（是当日无过线新闻，不是取数失败）。

### 结果是 0 条时怎么办

脚本会区分三种情况，别自己猜：

| 提示 | 含义 | 你的动作 |
|---|---|---|
| 「当前窗口内共 N 条，但最高只有 M 分」 | **有数据，分数不够** | 按提示的 `--min-score` 重跑，或换更活跃的频道 |
| 「频道均无数据，已改为全站高分」 | 频道名错了 或 当日真空 | 先 `--check` 看频道名 |
| 「命中偏少」+ 三条建议 | 话题检索召回低 | 扩关键词 / 降门槛 / 改看赛道 |

**画像门槛是硬门槛**：investor 45、policymaker 55、researcher/executive 50。
某些板块（如金融）当天可能全线低于 45，这时看到 0 条是正常的，
如实告诉用户"该板块当日无高分新闻"即可，不要为了凑数降到 20 分。

### 主体追踪的关键技巧

问"某公司/某人最近有什么动作"时：

1. **中英文别名都要给**，别只给人名：
   ```bash
   python scripts/intel.py --keyword 宁德时代,CATL,宁德新能源,曾毓群
   ```
2. **不要用泛词**。`新能源`、`AI`、`科技` 这类词会捞进海量无关条目。
   用专属组合词：`宁德时代` / `CATL` / `神行超充` / `麒麟电池`。
3. **结果要分两组给**：脚本已自动分成
   - **核心**（标题或分类命中 → 主体是主角）
   - **旁及**（仅摘要提到 → 主体只是事件要素）
   两组不要混在一起排，否则用户会觉得"这跟我要问的有什么关系"。

### 话题会横跨多个频道

一个话题（无人机、储能、英伟达）通常散落在多个板块与赛道里。
**所以 `--keyword` 走全站检索索引，不要限定板块。**
实测"英伟达"会同时出现在 T001 AI算力、T047 算力租赁、I453003 半导体制造里，
只查一个板块会漏掉大半。

---

## 第四步：分层加工（**这步决定质量**）

| 形态 | 何时用 | 做法 |
|---|---|---|
| **速览** | "有什么大事" / 意图不明 | 5 条，每条一句话（≤40 字） |
| **标准简报** | "来份日报""详细说说" | 15 条，按板块分组，每条含摘要 + 一句"值得关注" |
| **单条深挖** | "第 3 条展开" | 五段：发生了什么 / 关键信息 / 背景 / 影响 / 后续可关注 |
| **增量** | "跟上次比呢" | 只列新增，按主体/赛道归类 |
| **HTML 日报** | 存档、转发、发群 | `render.py` 生成自包含单文件 |

完整模板见 `references/templates.md`。

**四条加工纪律**：

1. **摘要原样使用**，不要重写；要浓缩就标注"以下为二次浓缩"
2. **`score_class == DUP` 必须剔除**（重复项）
3. **不凑数**：要 15 条只有 9 条过线，就给 9 条并说明
4. **推断必须标注**：事实 / 叙事 / 推断三者不能混

---

## 第五步：按画像定制输出

取完数只是原料，**怎么讲才决定有没有用**。核心差异：

| 画像 | 必须多给的一段 | 必须避免的 |
|---|---|---|
| **政策制定者** | **传导链**：政策 → 直接受影响环节 → 次生影响（每跳一句，标注哪跳是推断）+ 时间窗 | 评价政策好坏、预测"政府会怎么做" |
| **企业决策者** | 按**动作类型**分组（产能/产品/渠道/资本/人事）+ 每条"对我意味着什么" | 给"建议收购/建议进入"这类战略结论 |
| **个体投资者** | **事实 / 叙事 / 推断三分** + "值得关注"与"需要警惕"两栏 | ❌ 买卖建议、目标价、涨跌预测 |
| **行业研究人员** | **表格 + 全部字段不删**，说明样本口径与局限 | 为了"好看"删掉低分条目 |
| **科研人员** | 按**技术成熟度**分层（原理验证/中试样机/小批量/规模量产）+ 距产业化还差什么 | 把"宣称突破"当"已实现" |

**面向投资者时的强制声明**（每次都要有）：

> 评分是对新闻重要性的判断，不代表任何标的的投资价值。以下为信息整理，非投资建议。

详细写法见 `references/personas.md`。

---

## 输出 HTML 日报

```bash
python scripts/intel.py --sector 信息技术 --persona analyst --limit 20 --format json > d.json
python scripts/render.py --input d.json --out brief.html \
  --title "信息技术板块日报" --persona analyst --group-by sector
```

产物是自包含单文件 HTML（无外部依赖），深色 Vercel 风格，可直接转发或归档。

---

## 记忆机制

目录：`~/.workbuddy/skills/teko-industry-intel/memory/`
（找不到时回落到 skill 自身的 `memory/`）

| 文件 | 内容 |
|---|---|
| `preferences.json` | 关注板块、画像、常用条数、评分下限 |
| `pushed.jsonl` | 已推条目流水（url/标题/评分/时间），供 `--since-last` |

由 `intel.py` 自动读写，**不要手工改 `pushed.jsonl`**，会破坏增量基线。

用户说"我主要看半导体和新能源" → 跑 `--save-sector 信息技术,能源`，以后不传参就用它。

---

## 反理性化表（**必须遵守**）

| 可能的借口 | 正确做法 |
|---|---|
| "网络不通，我凭记忆写几条行业动态" | ❌ **绝不编造**。明确告知抓取失败，给出 URL 让用户自己看 |
| "用户没说关注什么，就默认给 AI 吧" | ❌ 按画像判定表判断；判断不出就给「速览」+ 问一句 |
| "摘要太长，我自己重写更顺" | ❌ 原样用。要浓缩就标"二次浓缩" |
| "只找到 9 条，凑到 15 条" | ❌ 给 9 条并说明。精选的价值在于少而准 |
| "40 分也算过线，都能说成重要" | ❌ 如实说"边缘过线，影响范围有限" |
| "投资者问买什么，我给个方向吧" | ❌ **绝不给买卖建议**。只做事实整理 + 风险提示 |
| "政策制定者问会不会出台新政策" | ❌ 不预测政策走向。只讲已发生事实 + 可推理的影响环节 |
| "DUP 也是新闻，先放着" | ❌ `DUP` = 重复项，必删 |
| "评分高的就是好投资标的" | ❌ 评分衡量新闻重要性，不是收益率 |
| "话题只查最相关的那个板块" | ❌ 话题跨频道，走 `--keyword` 全站检索 |
| "多频道取数，把高分频道的前几条给用户就行" | ❌ 用户点名的每个频道都要有代表，脚本已按频道轮流取，别自己截断 |
| "结果是 0 条，就说今天没相关新闻" | ❌ 先看脚本提示：可能是分数不够（给 `--min-score`）而非真的没有 |
| "画像门槛太高看不到，偷偷降到 20 分凑几条" | ❌ 如实说明当日无高分新闻。降门槛可以，但必须告知用户 |
| "用「AI」「新能源」当关键词" | ❌ 泛词会捞进海量无关内容，用专属组合词 |
| "碰到的条目都算相关" | ❌ 按「主体是主角」分核心/旁及，误匹配要剔除并说明 |
| "分类编号我可以自己推" | ❌ 编号有固定体系，读 `/taxonomy.json`，不要猜 |
| "用户没问来源，不用每条都给链接" | ❌ 每条都要能追溯到 `url` 与 `source` |

---

## 边界与降级

| 情况 | 处理 |
|---|---|
| `tekoai.net` 不可达 | 如实告知失败；给 `/index.json` 等 URL 让用户自己在浏览器打开；**不要编造** |
| 某板块当天 0 条 | 如实说明该板块本日无过线新闻，**不要用其他板块凑** |
| 用户要的板块不在 8 个里 | 用最接近的板块 + `--keyword` 补充，并说明映射关系（如"白酒"→"必需消费品"，该板块暂无频道，用关键词检索） |
| 用户要英文输出 | 数据源标题/摘要为中文；英文需求给原始 `url`，或按需联网 |
| Python 不可用 | **纯提示词模式**：用 WebFetch/curl 直接读 `/feed.json`、`/channels/*.json`，流程不变 |
| 用户要"历史对比" | 数据源只提供滚动 24 小时，**无历史快照**。如实说明，可建议用户自行定期存档 `--format json` |
| 用户要某条的完整正文 | 数据源只有摘要。给原文 `url`，或按需联网抓取并标注来源 |

---

## 文件结构

```
teko-industry-intel/
├── SKILL.md                    # 本文件（主流程）
├── README.md                   # 面向使用者的市场介绍
├── LICENSE                     # MIT
├── references/
│   ├── data-source.md          # 接口清单、字段、评分口径、数据规模
│   ├── taxonomy.md             # 242 编号体系、上卷规则、易错判定
│   ├── personas.md             # ★ 五类用户的痛点/场景/取数/输出/禁区
│   └── templates.md            # 五种输出形态的完整模板
├── scripts/
│   ├── intel.py                # 取数 + 筛选 + 增量 + 记忆（纯标准库）
│   └── render.py               # 生成可分享 HTML 日报（纯标准库）
├── assets/
│   └── preferences.template.json
└── memory/                     # 运行时生成（分发时清空，只留 .gitkeep）
```

**依赖**：核心流程零依赖，纯提示词即可用。
脚本**只用 Python 标准库**（urllib/json/argparse），不需 pip install，Python 3.7+。

---

## 首次使用自检

```bash
python scripts/intel.py --check
```

会打印：数据源是否可达、各入口条数、36 个频道清单、记忆状态。
**首次使用或报错时先跑它。**

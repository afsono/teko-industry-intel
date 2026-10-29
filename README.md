# teko-industry-intel

An agent skill for querying [tekoai.net](https://tekoai.net) — a bilingual industry-intelligence wire that publishes only what clears a scoring threshold.

Ask it "what moved in semiconductor equipment this week" in plain language. It handles the channel routing, the score thresholds, and the step where 400 matching items become the 12 that matter.

[中文说明](README.zh.md) · [Site](https://tekoai.net) · [Blog](https://tekoai.net/blog/) · [llms.txt](https://tekoai.net/llms.txt)

---

## What the data actually is

tekoai.net ingests about **26,000 raw items a day** from **5,000+ configured sources** (≈2,300 active in any 24h window), across 20+ languages. Each item is deduplicated, scored 0–100, and filed into a three-layer taxonomy. Only items scoring **40 or above** are published — roughly 4% of intake.

Recent 24-hour snapshot:

| Stage | Count |
|---|---|
| Ingested | 25,764 |
| Scored ≥ 40 (published) | 6,243 |
| Scored ≥ 65 (hot) | 1,108 |
| With a geographic anchor | ~79% |

**Score = importance × credibility × information density**, scaled to 0–100.

- *Importance* — does it change a supply chain, a capital allocation, a policy constraint?
- *Credibility* — named source, document, filing, number. Anonymous attribution is discounted.
- *Information density* — verifiable facts per hundred words.

Items can be filtered out before scoring matters: entertainment/sports keywords, simhash duplicates, and bodies too thin to summarise (marked `SHORT`). `DUP` marks a duplicate — always exclude it.

### Channels

36 public channels in three groups:

- **8 GICS-aligned sectors** — energy, materials, industrials, health care, financials, IT, communication services, consumer discretionary
- **12 trending themes** — AI compute, humanoid robotics, commercial space, innovative drugs, energy storage, and more
- **16 macro/politics channels** — monetary policy, trade, geopolitics, regulation, public safety, and more

Underneath is a taxonomy of **174 industries + 52 themes + 16 general categories = 242 codes**.

---

## Install

### Any skill-capable agent

```
/skills install https://github.com/afsono/teko-industry-intel
```

Or clone and point your agent at `SKILL.md`:

```bash
git clone https://github.com/afsono/teko-industry-intel.git
```

The skill is a `SKILL.md` plus a small Python script. No dependencies — standard library only, Python 3.9+.

### Requirements

- Python 3.9+
- Network access to `tekoai.net`
- No API key, no account

---

## Usage

```bash
# Top items by score (Chinese edition by default)
python scripts/intel.py --top

# English edition
TEKO_LANG=en python scripts/intel.py --top

# One channel
python scripts/intel.py --channel s-it

# Search by keyword
python scripts/intel.py --search "HBM"

# Check the endpoint is reachable
python scripts/intel.py --check
```

The agent normally calls these for you. You ask in natural language; it picks the endpoint.

---

## Site structure

Everything is static. No database sits behind the public endpoints — which means it can be mirrored, cached, and parsed by anything that speaks HTTP.

```
/                        English (default)
/zh/                     Chinese (full parallel tree)
/channels/{slug}.json    One channel, full records
/channels/{slug}.xml     Same as RSS 2.0
/a/{slug}.html           Summary page: 80–110 word summary, up to 5 related items, link to the original
/zh/a/{simhash}.html     Chinese summary page
/archive/                Daily archive, kept permanently
/feed.json               Top 100 by score
/latest.json             Newest 200
/search.json             Lightweight index, no summaries
/taxonomy.json           242 codes with rules
/llms.txt                Endpoint map written for models
```

Channel slugs: sector `s-<name>` (`s-it`), theme `t-<nnn>` (`t-002`), macro `g-<nn>` (`g-16`).

**Rebuilt hourly.** Every JSON payload carries `api_version: 1`, the contract marker — new services get added without breaking existing consumers.

### Item fields

| Field | Meaning |
|---|---|
| `id` | Stable primary key. Use it to deduplicate across feeds. |
| `title` / `summary` | In the language of the feed you requested. |
| `url` | **Original publisher URL.** |
| `detail_url` | Our summary page, when one exists. |
| `source` | Publisher **domain** (`reuters.com`), not a brand name — language-neutral. |
| `score` | 0–100 composite. 40+ published, 65+ hot. |
| `cat_code` / `cat_name` | Taxonomy code and its name. |
| `keywords` | 5–8 phrases, most specific first. |
| `place` / `place_en` / `lat` / `lon` / `cc` | Geographic anchor. |
| `collected_at_bj` | UTC+8 timestamp. |
| `collected_at_utc` | ISO 8601 UTC. Prefer this in multilingual output. |

---

## Why bilingual matters here

English is the default at `/`; Chinese lives at `/zh/` as a **full parallel static tree**, not a JavaScript toggle. Two static trees means both editions get indexed separately instead of one being invisible to crawlers.

Every item is machine-translated and summarised **from the article body, not the headline** — headline-based summarisation is the usual way summaries acquire invented details. English pages are marked as machine-generated, and the original publisher link is always one click away.

Translation runs incrementally under upstream rate limits, so about 30% of published items have an English edition at any given hour. The Chinese edition leads by roughly 24 hours.

---

## Built for machines first

The primary reader is a model, not a person. That shapes the whole site:

- **No client-side rendering.** The HTML body is complete on arrival.
- **Nav menus are `<details>` elements, not JavaScript** — a crawler with JS disabled still finds all 36 channels.
- **JSON-LD on every page** — `NewsArticle` + `BreadcrumbList`, `BlogPosting` for posts.
- **hreflang triples** (en / zh-Hans / x-default) so search engines treat the two editions as one page in two languages rather than duplicates.
- **`/llms.txt` and `/llms-full.txt`** — endpoint map, field tables, eight worked recipes, and an explicit statement of what the data does and does not mean.

If you want to query this without the skill, `curl https://tekoai.net/feed.json` is a valid answer.

---

## What this is not

- **Not a real-time wire.** Rebuilt hourly. Polling faster returns identical bytes.
- **Not a full-text archive.** Summaries, not article bodies. Read the source.
- **Not calibrated against outcomes.** We have no ground truth for "was this significant in hindsight." It is a judgment, applied consistently.
- **Not neutral by omission.** We filter entertainment and sports entirely. That is a choice, and you should know it.

---

## Repository layout

```
SKILL.md                 Skill definition: triggers, method, output shapes
scripts/intel.py         The query script (stdlib only)
references/
  data-source.md         Endpoint details and field semantics
  taxonomy.md            242-code taxonomy
  personas.md            Five reader archetypes and their output shapes
  templates.md           Output templates
assets/
  preferences.template.json
examples/
  示例简报_行业研究人员.html    Sample briefing output
```

---

## License

MIT. The data at tekoai.net is machine-generated summarisation of third-party reporting — cite the original publisher when you quote facts.

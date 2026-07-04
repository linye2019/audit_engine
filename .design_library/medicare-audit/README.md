# 医保审核引擎 Design System

A design system for **Medicare Audit Engine** — an intelligent medical insurance claims audit dashboard handling pre-check, end-check, and post-audit stages. The system is purpose-built for data-dense administrative interfaces where accuracy, clarity, and institutional trust take precedence over decorative expression. Every visual decision reinforces the message: this is a serious, reliable tool for safeguarding public health insurance funds.

## Source

- **Origin:** From-scratch design system (no Figma bundle)
- **Brand context:** Medical insurance (医保) intelligent audit — trust, intelligence, healthcare professionalism
- **Kit type:** Dashboard (admin panels, analytics, data-dense information architecture)

## What this design system covers

- **Foundations** — 6 color families (teal, cyan, green, amber, red, blue) with 10-stop scales, Slate gray neutrals, surface system, 5-level shadow elevation, 4-px spacing grid, Plus Jakarta Sans + JetBrains Mono typography
- **Components** — 6 documented components: Button, Card, Sidebar, Table, Input, Badge
- **Theming** — Full light/dark mode via `.dark` class toggle with inverted token maps

---

## CONTENT FUNDAMENTALS

### Voice & tone

The product voice is institutional, precise, and action-oriented. It speaks in the register of a government health administrator — not casual, not academic, but operational. Sentences are short and directive: "本季度共完成 1,280 条审核规则的执行分析，发现 42 条异常规则需要进一步排查。" The system avoids emotional language; severity is communicated through structured badges (违规 / 可疑 / 合规) and color coding rather than editorial commentary. There is no use of emoji or exclamation marks in the product UI. English appears only in technical identifiers (DRG-001, API endpoints) and the logo lockup.

### Concrete copy examples (lifted from the design system)

- **Dashboard card body:** *"本季度共完成 1,280 条审核规则的执行分析，发现 42 条异常规则需要进一步排查，建议重点关注住院费用审核模块。"*
- **Stat card labels:** *"规则总数" / "活跃规则" / "审核通过率"*
- **Status card descriptions:** *"当前规则覆盖率已达到 87.3%，超出目标阈值"* / *"本月批量审核任务已全部完成，无待处理项"* / *"3 条规则将于下周到期，请及时更新配置"*
- **Button labels:** *"提交审核" / "开始审核" / "生成报告" / "导出数据" / "批量处理" / "终止审核"*
- **Table headers:** *"规则编码" / "规则名称" / "分类" / "审核阶段" / "严重等级" / "状态"*
- **Sidebar navigation:** *"工作台" / "规则审核" / "规则沙箱" / "智能分析" / "AI 助手" / "审核报告" / "系统设置"*
- **Input labels and placeholders:** *"规则名称"* / *"请输入规则名称..."* / *"搜索规则编码或名称..."* / *"请输入审核意见..."*
- **Input helper text:** *"支持模糊搜索规则编码或名称"*
- **Audit stage terminology:** *"事前审核" / "事中审核" / "事后审核"*
- **Badge values:** *"合规" / "可疑" / "违规" / "信息" / "启用" / "停用"*

### When generating copy

- Use Chinese as the primary UI language. English is reserved for technical codes (DRG-001) and system version strings.
- Severity must be communicated through the four-tier badge system (合规 / 可疑 / 违规 / 信息), not through adjectives or color alone.
- Audit stage terms are fixed: 事前审核, 事中审核, 事后审核 — do not substitute synonyms.
- Quantitative statements must include the unit context (e.g., "1,280 条审核规则", not "1,280 规则").
- Action buttons use verb-object patterns: 提交审核, 导出数据, 生成报告. Never bare nouns.
- Descriptions in cards and status panels should state the finding, then the recommendation, in that order.

---

## VISUAL FOUNDATIONS

### Color

The palette is built around a deep teal-cyan primary axis that immediately signals "healthcare" without resorting to the overused hospital blue. **Brand primary is `--med-teal-500` (`#0d9488`)**, a moderately saturated teal that reads as authoritative and calm — neither playful nor cold. The accent mirror `--med-cyan-500` (`#06b6d4`) sits adjacent on the color wheel, providing differentiation for secondary actions and interactive highlights without breaking the cool-healthcare unity.

The primary scale runs 10 stops from `--med-teal-50` (`#effefb`, near-white teal wash) through `--med-teal-900` (`#0d3f3b`, near-black teal). The 50-100 range functions as tinted backgrounds for primary containers and stat icon wrappers; 500 is the working primary; 700-900 are reserved for dark-mode inversions and deep hover states.

**Neutrals** follow the Slate family (`--med-gray-50` `#f8fafc` through `--med-gray-900` `#0f172a`). The dominant working neutrals are `--med-gray-50` (page background), `--med-gray-200` (`#e2e8f0`, borders and dividers), `--med-gray-400` (`#94a3b8`, muted text), and `--med-gray-900` (`#0f172a`, primary text). The sidebar deliberately uses `--med-gray-900` as its background in light mode, creating a high-contrast dark rail against the light content area — a signature pattern of this system.

**Semantic colors** map to distinct hue families for maximum accessibility: success uses green (`--med-green-600` `#059669`), warning uses amber (`--med-amber-600` `#d97706`), error uses red (`--med-red-600` `#dc2626`), and info uses blue (`--med-blue-500` `#3b82f6`). In dark mode, these shift to their 400-level counterparts for adequate contrast on dark surfaces.

The **surface system** provides four elevation levels: `--surface` (pure white `#ffffff`), `--surface-dim` (`#f1f5f9`), `--surface-container-low` (`#f8fafc`), `--surface-container` (`#f1f5f9`), and `--surface-container-high` (`#e2e8f0`). Interactive states use teal-tinted alpha layers: hover at 8%, focus at 12%, press at 16%.

**Chart colors** cycle through the five primary hue families: teal, cyan, blue, amber, green (`--chart-1` through `--chart-5`), ensuring data visualization stays within the brand palette rather than introducing foreign hues.

### Typography

**Primary face:** **Plus Jakarta Sans** — a geometric humanist sans-serif with a technical character that avoids both the corporate blandness of Inter and the geometric stiffness of Poppins. It is loaded via Google Fonts with weights 400, 500, 600, 700, 800. This face handles display, headings, body, and UI text across the entire system; there is no secondary Latin face because the product is Chinese-first and Plus Jakarta Sans covers the full weight range needed.

**Monospace face:** **JetBrains Mono** (weights 400, 500) — used exclusively for code snippets, rule identifiers, and data fields that require fixed-width alignment (e.g., `DRG-001` in table cells). Not used for any prose.

**Scale** (size / weight / line-height):
| Token | Size | Weight | Line-height | Use |
|---|---|---|---|---|
| display | 56px | 800 | 1.1 | Dashboard hero numbers, major KPIs |
| h1 | 40px | 700 | 1.2 | Page titles |
| h2 | 32px | 600 | 1.25 | Section headers |
| h3 | 24px | 600 | 1.3 | Card stat values, subsection titles |
| h4 | 20px | 600 | 1.4 | Card titles, sidebar logo |
| lead | 18px | 500 | 1.7 | Introductory body text |
| body | 16px | 400 | 1.6 | Default prose, table cells, inputs |
| caption | 12px | 400 | 1.5 | Meta text, helpers, timestamps |
| eyebrow | 11px | 600 | 1.4 | Labels, category tags, table headers |
| mono | 14px | 400 | 1.6 | Code, identifiers |

The display type uses `letter-spacing: -0.02em` (negative tracking) for tighter KPI numbers. The eyebrow style uses `letter-spacing: 0.08em` with `text-transform: uppercase` — this is the only tokenized uppercase treatment in the system and is used exclusively for structural labels (e.g., "默认卡片", "审核状态" row labels in preview specimens), never for user-facing content.

Chinese text does not have variable letter-spacing applied at the token level. The system relies on Plus Jakarta Sans's default CJK sidebearings, which are adequate for the 16px body size. For Chinese-heavy screens, line-height at 1.6 provides comfortable reading density.

### Spacing

The spacing system is a **4-px base grid** with 8 tokens: `--space-1` (4px) through `--space-8` (64px). The progression is not strictly linear — it jumps from 16px to 24px (space-5) then 32px (space-6), 48px (space-7), 64px (space-8). The working range for component internals is space-2 (8px) through space-5 (24px); space-7 and space-8 are reserved for page-level section padding.

**Component height anchors:** Buttons default to `40px` (`--size-button-height`), with small at `32px` and large at `48px`. Inputs share the `40px` default height (`--size-input`). The sidebar is fixed at `240px` width (`--sidebar-width`) and the top navigation bar at `56px` (`--nav-height`). Content max-width is `1440px`.

### Radius

Radius values are restrained and functional: `--radius-sm` (4px) for small controls, `--radius-md` (8px) for cards and inputs, `--radius-lg` (12px) for elevated containers and sidebar, `--radius-xl` (16px) for search inputs and large panels, and `--radius-full` (9999px) exclusively for badges. The pill shape (`radius-full`) is a deliberate semantic marker — if you see a pill, it is a status indicator, never a button or card.

### Shadow / Elevation

Five shadow levels provide depth without visual noise:
1. **Level 1 (Card):** `0 1px 2px rgba(15,23,42,.06), 0 1px 1px rgba(15,23,42,.04)` — the lightest touch, used for accent-border cards at rest.
2. **Level 2 (Card Hover):** `0 4px 8px -2px rgba(15,23,42,.10)` — default card elevation and hover state for level-1 cards.
3. **Level 3 (Float):** `0 8px 24px -8px rgba(15,23,42,.18)` — dropdowns, popovers, elevated panels.
4. **Level 4 (Modal):** `0 16px 40px -12px rgba(15,23,42,.24)` — modal dialogs and overlays.
5. **Level 5 (Overlay):** `0 24px 60px -20px rgba(15,23,42,.30)` — full-screen overlays.

The philosophy is "whisper-quiet at rest, deliberate on interaction." Cards sit at level 2 and lift to level 3 on hover. In dark mode, all shadow opacities are significantly increased (e.g., level 1 uses `.20` and `.14` instead of `.06` and `.04`) because dark surfaces need stronger shadow definition to perceive depth.

### Borders

Borders are consistently `1px solid var(--color-border)` which resolves to `1px solid #e2e8f0` in light mode and `1px solid #334155` in dark mode. The sidebar uses a special treatment: `border-left: 3px solid transparent` on nav items, switching to `border-left-color: var(--primary)` for the active state — this is the primary active-state indicator for navigation, not background color change alone. Dividers use `var(--color-outline-variant)` (lighter than the main border) for subtle separation within cards.

### Backgrounds

The page background is `var(--background)` → `var(--med-gray-50)` (`#f8fafc`), a barely-off-white that avoids the clinical sterility of pure white. Cards and inputs use `var(--surface)` (`#ffffff`). The sidebar breaks from this with `--med-gray-900` (`#0f172a`) creating a dark-to-light composition that anchors the layout. Interactive hover uses `var(--interactive-hover)` (`rgba(13,148,136,.08)`) — a teal-tinted wash that reinforces brand identity even in subtle micro-interactions.

---

## Component Patterns

| Component | Preview | Contract | CSS Source | Key Facts | Key Insight |
|---|---|---|---|---|---|
| Button | `preview/component-button.html` | `components/button.json` | `components.css` | 4 variants (primary, secondary, ghost, danger) x 3 sizes (sm 32px, md 40px, lg 48px); disabled state at 50% opacity | Teal primary with 8px radius; danger uses red-500 directly, no outlined variant |
| Card | `preview/component-card.html` | `components/card.json` | `components.css` | 3 types: default (header/body/footer), stat (icon + number), accent (left-border status); shadow-2 rest / shadow-3 hover | Left-border accent card is the primary status communication pattern — 3px border, 4px radius |
| Sidebar | `preview/component-sidebar.html` | `components/sidebar.json` | `components.css` | Fixed 240px width, gray-900 background, 7 nav items, active via left-border + background highlight | Dark sidebar against light content is a deliberate composition anchor, not a theme choice |
| Table | `preview/component-table.html` | `components/table.json` | `components.css` | Default and striped variants; sticky headers; badge-integrated severity columns; caption-size (12px) cells | Table is intentionally dense — 12px font, compact 12px/16px padding for data scanning efficiency |
| Input | `preview/component-input.html` | `components/input.json` | `components.css` | Default, search (with icon, lg radius), textarea; 40px height; teal focus ring (3px offset) | Focus state is the key brand moment — teal ring with interactive-focus alpha, not a hard border change |
| Badge | `preview/component-badge.html` | `components/badge.json` | `components.css` | 4 semantic variants (success/warning/error/info); pill shape (radius-full); 10% alpha backgrounds with 700-level text | Badge is the sole component using radius-full — pill = status, never interactive |

---

## Index

- `README.md` — this file (brand narrative, visual foundations, component overview)
- `colors_and_type.css` — single combined CSS file with all design tokens (color, type, spacing, radius, shadow, layout)
- `css.json` — structured JSON token representation for programmatic consumption
- `components.css` — aggregated component CSS extracted from preview pages
- `components/index.json` — component index with slugs, categories, variant counts, and key insight seeds
- `components/{slug}.json` — individual component contracts (button, card, sidebar, table, input, badge)
- `preview/component-{slug}.html` — interactive HTML specimen cards for each component

---

## Caveats / known substitutions

1. **Plus Jakarta Sans** is a Google Fonts face not bundled with any operating system. The CSS imports it via `@import url(...)` which introduces a network dependency on first load. For offline or air-gapped deployments, self-host the woff2 files and update the import path. Fallback is `sans-serif`, which will resolve to the OS default (PingFang SC on macOS, Microsoft YaHei on Windows) — acceptable for CJK but loses the Latin geometric character.

2. **JetBrains Mono** is similarly Google-sourced and used only for code/identifier contexts. If unavailable, `monospace` fallback will use Menlo (macOS) or Consolas (Windows), both adequate for the narrow use case.

3. **BrandFile (phase2-brand-analyst.json)** was empty for this generation. All brand context, copy samples, and design decisions were inferred from the CSS token file and preview HTML specimens. This means voice/tone analysis and copywriting rules are derived from observed patterns in the preview components rather than from an explicit brand brief. Treat these sections as informed defaults, not validated brand guidance.

4. **No icon library is bundled.** Preview specimens use `lucide-static` via jsDelivr CDN for demonstration icons. Production implementations should either self-host the required SVGs or adopt an icon strategy consistent with the team's build pipeline. The system does not prescribe an icon style beyond the sizing tokens (`--size-icon-sm` 16px, `--size-icon-md` 20px, `--size-icon-lg` 24px).

5. **Dark mode token inversion is mechanically generated.** The `.dark` class inverts the color scales (50↔900, 100↔800, etc.) and increases shadow opacities. This has not been visually audited against real dashboard screens with dense data tables. Pay special attention to badge contrast (error/warning badges use 700-level text on 50-level alpha backgrounds in both modes) and table striped-row readability in dark mode.

6. **Component contracts are `from-scratch` with `medium` confidence.** The 6 components were designed from first principles based on the token system, not extracted from an existing Figma library. Variant coverage and state matrices should be treated as starting points for further refinement, not exhaustive specifications.

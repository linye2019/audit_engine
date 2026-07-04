---
name: medicare-audit-design
description: Use this skill to generate well-branded interfaces for Medicare Audit Engine. Contains colors, type, fonts, assets, and UI kit for prototyping dashboard UIs.
user-invocable: true
---
# Medicare Audit Design Skill

Read the `README.md` file within this skill, and explore the other available files.

If creating visual artifacts, copy assets out and create static HTML files. If working on production code, read the rules here to become an expert in designing with this brand.

## Quick map
- `README.md` — brand context, content fundamentals, visual foundations (read first)
- `colors_and_type.css` — drop-in CSS variables for colors, type, radius, shadow, spacing
- `css.json` — structured token understanding source
- `components/index.json` — component index + cross-component patterns
- `preview/` — small HTML cards illustrating foundations and components
- `library-consumption.json` — recommended downstream read order

## Essentials at a glance
- Brand primary `#0d9488` (med-teal-500) — deep teal-cyan, professional, trustworthy, tech-forward
- Radius: 4/8/12/16/full — small for inputs, medium for cards/buttons, large for modals, full for badges/chips
- 4px spacing base unit; buttons 32/40/48px, inputs 40px
- Type: **Plus Jakarta Sans** for display/heading/body, **JetBrains Mono** for code — loaded via Google Fonts
- Voice: bilingual CN-first, professional, neutral, no emoji in UI
- 5-level shadow elevation: hairline card rest → ambient overlay (`--shadow-1` through `--shadow-5`)
- AI components are first-class: dedicated chat/thinking states with cyan accent glow (`--med-cyan-500`)

## Components
| Slug | Name | Key Insight |
|------|------|-------------|
| button | Button | Primary teal with subtle glow for AI actions |
| card | Card | Clean elevated card with left accent border for status |
| sidebar | Sidebar | Dark sidebar with AI agent navigation section |
| table | Table | Compact data table with severity badges |
| input | Input | Minimal input with teal focus ring |
| badge | Badge | Semantic severity badges for audit results |

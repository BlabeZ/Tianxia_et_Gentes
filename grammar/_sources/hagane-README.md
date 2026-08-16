# HOI4 Modmaking Skills

*Read this in: **English** · [中文](README.zh.md) · [Русский](README.ru.md) · [Deutsch](README.de.md) · [Español](README.es.md) · [Français](README.fr.md) · [日本語](README.ja.md) · [한국어](README.ko.md)*

**Build Hearts of Iron IV mods by talking to your AI agent.**

Connect your own AI coding agent — **Claude Code**, **Cursor**, or any skills-capable agent — to [hagane.works](https://scharnhorst.hagane.works), a visual HOI4 mod workbench. Describe what you want in plain language; your agent builds it through the platform; you refine it visually and export a ready-to-play mod.

No Paradox script syntax. No crash-hunting. No lost weekend over one misplaced bracket.

---

## What this is

A set of **skills** (instruction packs) + a **field reference** that teach your AI agent how to drive the hagane.works platform. Your agent builds across **every content workbench**: countries, focus trees, events & fullscreen super-events, decisions, ideas, characters, scenario bookmarks & day-0 history, states & territory, technologies, equipment, divisions & starting armies (land, air, naval), military-industrial organizations, intelligence agencies, special projects, scripted effects & triggers, dynamic modifiers, localisation — and the platform handles the parts that usually break mods:

- **ID collisions** — auto-suffixed, never clash with vanilla or each other
- **Namespacing** — your mod's entities auto-prefixed, cleanly separated from the base game
- **Validation** — catches crash-causing mistakes *before* the game does
- **Export** — a correctly structured, ready-to-load mod folder

You bring the creativity and your own AI. The platform makes sure it actually loads.

> **Publish anywhere.** We don't run a mod marketplace and never will. You get the mod files; you keep the credit and the audience — Steam Workshop, Paradox Mods, your call.

---

## Now in your language

**The workbench speaks 8 languages.** English · 简体中文 · Русский · Deutsch · Español · Français · 日本語 · 한국어 — pick yours from the switcher and the *whole* workbench follows, not just the landing page: every editor, every dialog, every validation message.

**And your mod can speak 10.** Export writes localisation for all ten languages Hearts of Iron IV itself ships — the eight above plus **Polski** and **Português do Brasil** — each into the correct `localisation/<language>/` folder with the matching `l_<language>:` header. The platform can also AI-translate your mod's strings into those ten, so you author in one language and ship to a wider audience than you wrote for.

---

## Why not just have your AI write the files directly?

An AI *can* write raw mod files — and then you spend the weekend finding out which of 400 files has the bracket that crashes the game on load. hagane.works is a visual workbench with schema-aware validation, WYSIWYG editing, and correct export built in. These skills are the bridge from your agent to that. You get AI speed **and** a mod that boots.

---

## Requirements

- An AI agent that can connect over **MCP** or load **skills** — e.g. **Claude Code**, **Cursor**, **Cline**, or any MCP-capable client *(one command — see Quick start)*
- A **hagane.works** account *(currently BETA — see Access below)*

### Which models work?

**Any of them.** This is our most-asked question, so: DeepSeek, Kimi, Qwen, GPT, Gemini — the model is not the deciding factor.

These skills never talk to a model directly. They run inside your **agent** (Claude Code, Cursor, Cline, …), and MCP is a **model-agnostic protocol** — what matters is whether your *client* speaks MCP, not which model sits behind it. Point any MCP-capable client at us and the tools show up.

We measure this rather than guess. Driving the platform with **DeepSeek** (`deepseek-chat`), it completed every task we gave it: picked the right tool, sent valid arguments, and got the ordering right on its own — creating the focus tree before the focus, and the event namespace before the event.

Two honest caveats:

- **The skills *files* (Option B) are more Claude-flavoured.** `SKILL.md` auto-discovery is a Claude Code convention. On other agents the MCP route (Option A) is the smooth one — you can still point an agent at these files by hand.
- **Connecting is not the same as taste.** Any model that does tool-calling can drive the platform correctly; how *interesting* the resulting focus branch is still depends on the model. The important half is covered either way — validation and export run on our servers, so a weaker model gives you a less inspired mod, not a broken one.

---

## Quick start

1. **Create an account.** hagane.works is in open public beta — registration is open to everyone, no invite needed. (Questions or feedback? Join our [Discord](https://discord.gg/hw5UH4NmuA).)
2. **Sign in** at [hagane.works](https://scharnhorst.hagane.works) and generate a **Personal Access Token**: account menu (👤) → **🔐 Access tokens** → generate. Copy it — it's shown once. You can optionally set an expiry (30 / 90 / 365 days); leave it **Never** for a long-lived agent setup.

Then connect your agent — **two ways**:

### Option A · MCP (recommended · one command)

No file install, always up to date. In Claude Code (`--scope user` makes it available in all your projects):

```
claude mcp add --transport http --scope user hoi4 \
  https://scharnhorst.hagane.works/mcp/ \
  --header "Authorization: Bearer hoi4pat_YOUR_TOKEN"
```

Cursor / other MCP clients: add an HTTP (Streamable-HTTP) MCP server — e.g. in `mcp.json`:

```json
{ "mcpServers": { "hoi4": {
  "type": "http",
  "url": "https://scharnhorst.hagane.works/mcp/",
  "headers": { "Authorization": "Bearer hoi4pat_YOUR_TOKEN" }
} } }
```

Then just talk to your agent — the tools appear automatically.

### Option B · Skills files

Download this repo (**Code → Download ZIP**, or `git clone`). Copy the folders under `skills/` into your agent's skills directory (e.g. `~/.claude/skills/`) and keep `field-reference/` reachable (simplest: use the whole folder as your working directory). Paste your token into `platform.env`, then `source platform.env`.

### Then build

Talk to your agent:
> *"Open my Italy mod and add a 'Restore the Roman Empire' focus branch — about 5 focuses, the last one fires an event to claim the Mediterranean."*

Your agent builds it on the platform. Open hagane.works to see it on the canvas, refine it visually, and export.

Details live in each skill and in `field-reference/README.md`.

**Every account is separate.** Use your own account and your own token — never share tokens.

> **Your token is an auth *header*, not a login.** The skills send it as `Authorization: Bearer hoi4pat_…` on every API call (that's what `platform.env` wires up), and the MCP setup passes it the same way (`--header "Authorization: Bearer hoi4pat_…"`). Don't paste your token into a chat and expect the agent to "log in" with it — it isn't an email/password.

---

## Staying up to date

The skills tell your agent to run `git pull --ff-only` in this repo at the start of each
session, so you always work from the latest recipes automatically — no manual updates needed.
The current version is in [`VERSION`](VERSION) (also a git tag); see [`CHANGELOG.md`](CHANGELOG.md)
for what changed. To pin a known-good copy: `git checkout v1.3.0`.

## Access (Public Beta)

hagane.works is in **open public beta** — registration is open; sign in with email or Google.

The **Command Wiki** (2400+ HOI4 commands, effects, triggers) is **open to everyone, no login**. To use the workbench + these skills, just create an account — and join our [Discord](https://discord.gg/hw5UH4NmuA) for feedback and release notes.

---

## Roadmap

- **Now** — connect over **MCP** (one command) or install the **skills + token** files. Either way your agent drives the platform through its API.
- **Later** — deeper coverage as the platform's newer workbenches mature — e.g. **in-game UI panel authoring** (the scripted-GUI builder) joins the agent toolset once its visual editor is polished.

---

## Support

Free during BETA. If it saves you a modding weekend and you'd like to help cover server costs: [support the project](https://scharnhorst.hagane.works/donate).

---

## License

**[CC BY-NC-SA 4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/)** — Attribution · NonCommercial · ShareAlike.

Authored by the hagane.works team; the field reference is derived from publicly documented HOI4 modding knowledge. Free to use and adapt for non-commercial modding, with attribution; derivatives stay open. Not for resale or commercial repackaging.

---

## Links

- **Platform** — https://scharnhorst.hagane.works
- **Discord** — https://discord.gg/hw5UH4NmuA
- **Contact** — scharnhorst@hagane.works

# grantfin

Find grants for your nonprofit and fill out the applications, from inside Claude Code.

grantfin is an [MCP](https://modelcontextprotocol.io) server. Claude Code does the
thinking — deciding which grants fit your organization and how to answer each form
field. grantfin does the deterministic work — calling grant APIs, scraping foundation
pages, tracking what you've seen, and filling forms in a real browser. Your sensitive
data (EIN, bank details, logins) stays in your OS keychain and never passes through
the model.

## What it does

- **Search** government grant databases (US Grants.gov, EU Funding & Tenders, UK
  360Giving) and find foundations that fund your cause.
- **Match** each opportunity against your organization's profile and write out a
  clean CSV — one row per grant, sorted by deadline.
- **Track** opportunities across runs in a local database, so a scheduled scan only
  surfaces what's new.
- **Apply** by driving a browser to fill application forms. Public answers are typed
  normally; secrets are injected directly into the page and never seen by the model.
  Submitting always requires explicit human approval.

## Install

```bash
git clone https://github.com/arnavgowda/grantfin.git
cd grantfin
pip install -e .
```

Requires Python 3.11+. Auto-apply also needs Node 24+ and
[agent-browser](https://github.com/vercel-labs/agent-browser):

```bash
npm install -g agent-browser && agent-browser install
```

Connect it to Claude Code:

```bash
claude mcp add grantfin -- python -m grant_scout
```

## Setup

Copy the examples and fill them in:

```bash
cp org_profile.example.toml org_profile.toml     # your mission, focus areas, geography
cp answers.toml.example answers.toml             # reusable narrative answers (optional)
cp vault_policy.example.toml vault_policy.toml    # which secrets exist and where they're allowed
```

Store secrets in your OS keychain (you'll be prompted; the value is never echoed):

```bash
grant-scout vault set org.bank_account
```

## Use

Talk to Claude Code in plain language:

> Find education grants my org qualifies for and export them to a CSV.

> Scan for youth-mentoring grants and tell me what's new since last time.

> Open this grant application and fill in everything you can.

Run a recurring scan with `/loop`:

```
/loop 1d scan "rural health"
```

## How secrets are handled

- A **public profile** (mission, programs, EIN) is shared with the model freely.
- A **secret vault** (bank account, SSN, portal passwords) lives in the OS keychain.
  The model only ever references secrets by name, like `{{org.bank_account}}`.
- When filling a form, a value is resolved and injected straight into the page input.
  It never enters the model's context, the command line, logs, or screenshots.
- `vault_policy.toml` limits each secret to specific domains. A mismatched domain or
  field type is refused.
- Submitting an application requires a human to review a screenshot and confirm.

## Data sources

| Source | Coverage | Key required |
| --- | --- | --- |
| Grants.gov | US federal | no |
| EU Funding & Tenders | EU | no |
| Simpler.Grants.gov | US federal | yes (set `SIMPLER_API_KEY`) |
| ProPublica 990 | US foundations | no |
| 360Giving | UK funders | no |
| Foundation websites | anywhere | no (robots.txt respected) |

## Tests

```bash
pytest -m "not live and not browser"   # fast, offline
pytest                                  # includes live API + browser tests
```

## License

MIT

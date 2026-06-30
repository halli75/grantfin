"""Grant Scout MCP server.

Claude Code is the agent loop; this server is the deterministic layer. It fetches
and normalises grant data and writes the clean CSVs. Eligibility matching stays in
Claude.

Two distinct flows, two clean outputs:
  - Opportunities (apply-able open calls)  -> search_grants  -> grants CSV
  - Funder intelligence (who to approach)  -> find_funders   -> funders CSV
"""

from __future__ import annotations

import sys

from fastmcp import FastMCP

from . import store
from .scrape import fetch_page as _fetch_page
from .csv_export import write_funders_csv, write_grants_csv
from .dedupe import dedupe_opportunities
from .funders import ProPublicaSource, ThreeSixtyGivingSource
from .profile import load_profile
from .sources import EuSediaSource, GrantsGovSource
from .sources.simpler import SimplerSource, is_enabled as simpler_enabled

mcp = FastMCP("grant-scout")


def _log(msg: str) -> None:
    print(f"[grant-scout] {msg}", file=sys.stderr)


def _opportunity_sources():
    srcs = [GrantsGovSource(), EuSediaSource()]
    if simpler_enabled():
        srcs.append(SimplerSource())
        _log("Simpler.Grants.gov enabled (SIMPLER_API_KEY set).")
    return srcs


def _funder_sources():
    return [ProPublicaSource(), ThreeSixtyGivingSource(logger=_log)]


@mcp.tool
def search_grants(keyword: str, status: str = "posted", rows: int = 25) -> list[dict]:
    """Search apply-able grant opportunities across all sources (US Grants.gov, EU
    Funding & Tenders, and Simpler.Grants.gov when configured).

    Returns deduped opportunity records. Call `get_opportunity` for full US-federal
    detail. A failing source is skipped (logged), never fails the whole search.

    Args:
        keyword: free-text, e.g. "youth literacy" or "renewable energy".
        status: posted | forecasted | closed (default posted; maps to open/forthcoming for EU).
        rows: max results per source (default 25).
    """
    out: list[dict] = []
    for src in _opportunity_sources():
        try:
            out.extend(o.to_dict() for o in src.search(keyword, status=status, rows=rows))
        except Exception as e:  # one bad source must not sink the search
            _log(f"source {getattr(src, 'name', '?')} failed: {e}")
    return dedupe_opportunities(out)


@mcp.tool
def get_opportunity(opportunity_id: str, source: str = "grants.gov") -> dict | None:
    """Fetch full detail for one opportunity: award range, eligibility, description.

    Note: the detail record has no status flag — keep the `status` from the matching
    `search_grants` hit when you assemble the row for `export_csv`.
    """
    srcs = {s.name: s for s in _opportunity_sources()}
    src = srcs.get(source)
    if src is None:
        raise ValueError(f"Unknown source '{source}'. Known: {sorted(srcs)}")
    opp = src.fetch(opportunity_id)
    return opp.to_dict() if opp else None


@mcp.tool
def find_funders(keyword: str, state: str = "", rows: int = 25) -> list[dict]:
    """Find grantmakers/foundations to approach for a cause (PROSPECTING, not open calls).

    Sources: ProPublica 990 (US nonprofits/foundations) and 360Giving (UK, name match).
    Returns funder records for the SEPARATE funders CSV — never mix into the grants CSV.

    Args:
        keyword: cause/program area, e.g. "literacy" or "homelessness".
        state: optional US state code to narrow ProPublica (e.g. "CA").
        rows: max results per source.
    """
    out: list[dict] = []
    for src in _funder_sources():
        try:
            out.extend(f.to_dict() for f in src.find(keyword, location=state, rows=rows))
        except Exception as e:
            _log(f"funder source {getattr(src, 'name', '?')} failed: {e}")
    return out


@mcp.tool
def get_org_profile(path: str = "org_profile.toml") -> dict:
    """Return the nonprofit's PUBLIC profile to match opportunities against.

    Contains only public fields (mission, programs, focus areas, geography,
    org type, EIN). Never contains secrets.
    """
    try:
        return load_profile(path).to_dict()
    except FileNotFoundError as e:
        return {"error": str(e)}


@mcp.tool
def export_csv(opportunities: list[dict], path: str | None = None) -> dict:
    """Write opportunities to a clean, deadline-sorted CSV for the user.

    Pass opportunity dicts (from search/get_opportunity). Add your own assessment
    by including `match` (High/Medium/Low), `why` (one-sentence rationale), and
    optional `notes` on each row before exporting.
    """
    written = write_grants_csv(opportunities, path)
    return {"path": str(written.resolve()), "count": len(opportunities)}


@mcp.tool
def export_funders_csv(funders: list[dict], path: str | None = None) -> dict:
    """Write funder/grantmaker prospects to a clean, separate CSV (funders_<date>.csv)."""
    written = write_funders_csv(funders, path)
    return {"path": str(written.resolve()), "count": len(funders)}


# --- Increment 3: persistent pipeline (tracking + dedupe across runs) ---


@mcp.tool
def scan(keyword: str, status: str = "posted", rows: int = 25,
         db_path: str = store.DEFAULT_DB) -> dict:
    """Scan all sources, store results, and return only opportunities NOT seen before.

    Use this for recurring monitoring (e.g. via `/loop`). New hits are saved at
    stage "new"; previously-seen ones are skipped (cross-run dedupe). Also refreshes
    a clean `grants_<date>.csv` of the whole open pipeline. Assess the returned new
    hits and record verdicts with `set_status`.
    """
    found: list[dict] = []
    for src in _opportunity_sources():
        try:
            found.extend(o.to_dict() for o in src.search(keyword, status=status, rows=rows))
        except Exception as e:
            _log(f"source {getattr(src, 'name', '?')} failed: {e}")
    found = dedupe_opportunities(found)
    conn = store.connect(db_path)
    try:
        new = store.upsert_new(conn, found)
        open_pipeline = [
            o for o in store.list_opportunities(conn) if o.get("stage") != "dismissed"
        ]
    finally:
        conn.close()
    csv_path = write_grants_csv(open_pipeline)
    return {"new_count": len(new), "new": new,
            "pipeline_size": len(open_pipeline), "csv": str(csv_path.resolve())}


@mcp.tool
def list_pipeline(stage: str = "", db_path: str = store.DEFAULT_DB) -> list[dict]:
    """List tracked opportunities, optionally filtered by stage
    (new/matched/saved/dismissed/applying/applied)."""
    conn = store.connect(db_path)
    try:
        return store.list_opportunities(conn, stage=stage or None)
    finally:
        conn.close()


@mcp.tool
def set_status(source: str, opportunity_id: str, stage: str,
               match: str = "", why: str = "", notes: str = "",
               db_path: str = store.DEFAULT_DB) -> dict:
    """Set an opportunity's pipeline stage + optional assessment (match/why/notes).

    stage ∈ new / matched / saved / dismissed / applying / applied.
    """
    conn = store.connect(db_path)
    try:
        ok = store.set_stage(conn, source, opportunity_id, stage,
                             match=match or None, why=why or None, notes=notes or None)
    finally:
        conn.close()
    return {"updated": ok}


@mcp.tool
def dismiss(source: str, opportunity_id: str, db_path: str = store.DEFAULT_DB) -> dict:
    """Mark an opportunity dismissed so it stops cluttering the pipeline + CSV."""
    conn = store.connect(db_path)
    try:
        ok = store.set_stage(conn, source, opportunity_id, "dismissed")
    finally:
        conn.close()
    return {"updated": ok}


@mcp.tool
def save_opportunity(opportunity: dict, db_path: str = store.DEFAULT_DB) -> dict:
    """Manually add one opportunity to the pipeline (e.g. a foundation hit found by hand)."""
    conn = store.connect(db_path)
    try:
        new = store.upsert_new(conn, [opportunity])
    finally:
        conn.close()
    return {"saved": len(new)}


@mcp.tool
def export_pipeline_csv(stage: str = "", path: str | None = None,
                        db_path: str = store.DEFAULT_DB) -> dict:
    """Write the tracked pipeline (optionally one stage) to a clean grants CSV."""
    conn = store.connect(db_path)
    try:
        rows = store.list_opportunities(conn, stage=stage or None)
    finally:
        conn.close()
    written = write_grants_csv(rows, path)
    return {"path": str(written.resolve()), "count": len(rows)}


# --- Increment 4: foundation scraping (server fetches; Claude extracts) ---


@mcp.tool
def fetch_page(url: str) -> dict:
    """Fetch a public foundation/RFP page as clean text, respecting robots.txt.

    Returns {url, final_url, status, text, blocked, reason}. Use this to read a
    foundation's grants/funding page, then extract any open opportunities yourself
    and store each via `save_opportunity` (tag source as "foundation:<domain>",
    fill title/funder/close_date/eligibility/url). If `text` is empty/thin the page
    is likely JavaScript-rendered — fall back to your claude-in-chrome browser tools.
    Never fetch paywalled databases; stick to public foundation sites.
    """
    return _fetch_page(url)


# --- Increment 5: auto-apply (secrets injected deterministically; human gate before submit) ---

_apply: dict = {}


def _apply_ctx():
    """Lazy singletons for the apply session (real keychain + agent-browser)."""
    if not _apply:
        from .apply import AgentBrowser, Filler, SubmitGate
        from .secrets import Registry, Resolver, Vault
        br = AgentBrowser()
        reg = Registry.load()
        resolver = Resolver(Vault(), reg)
        _apply.update(browser=br, registry=reg, resolver=resolver,
                     filler=Filler(br, resolver), gate=SubmitGate(br))
    return _apply


def _current_domain() -> str:
    try:
        host = _apply_ctx()["browser"].eval("location.hostname")
        return host.strip().strip('"').lower()
    except Exception:
        return ""


@mcp.tool
def list_secret_refs(policy_path: str = "vault_policy.toml") -> list[dict]:
    """List available secret references (ref, type, allowed_domains) — NO values.

    Use these as `{{ref}}` placeholders in an `apply_fill` plan. Values are entered
    by the human via `grant-scout vault set <ref>` and never pass through you.
    """
    from .secrets import Registry
    return Registry.load(policy_path).refs()


@mcp.tool
def get_answers(path: str = "answers.toml") -> dict:
    """Reusable PUBLIC answers (mission, need statement, org history) to fill narrative
    fields. Never contains secrets."""
    from .answers import load_answers
    return load_answers(path)


@mcp.tool
def apply_open(url: str) -> dict:
    """Open a grant application page in the automated browser (agent-browser)."""
    _apply_ctx()["browser"].open(url)
    return {"opened": url, "domain": _current_domain()}


@mcp.tool
def apply_snapshot() -> dict:
    """Accessibility snapshot of the current page: interactive fields with @eN refs +
    labels. Use this to build an `apply_fill` plan. No secret values are present."""
    return {"snapshot": _apply_ctx()["browser"].snapshot()}


@mcp.tool
def apply_fill(plan: list[dict]) -> dict:
    """Fill form fields. Each plan item: {ref: "@eN", value, field_type}.

    `value` is either a public literal OR a `{{secret.ref}}` placeholder. Public
    values are typed directly; secrets are resolved from the vault and injected via
    stdin (never argv, never returned to you). Returns a masked per-field report.
    Off-allow-list domains and field-type mismatches are blocked.
    """
    ctx = _apply_ctx()
    report = ctx["filler"].fill(plan, _current_domain())
    return {"domain": _current_domain(), "fields": report}


@mcp.tool
def apply_preview(path: str = "apply_preview.png") -> dict:
    """Screenshot the filled form for a HUMAN to review before submitting."""
    return _apply_ctx()["gate"].preview(path)


@mcp.tool
def apply_submit(submit_ref: str, confirm_token: str = "") -> dict:
    """Submit the application — BLOCKED unless a human passes the exact confirm token
    (see `apply_preview`). Submissions are irreversible; never invent the token."""
    return _apply_ctx()["gate"].submit(submit_ref, confirm_token)


def run() -> None:
    mcp.run()

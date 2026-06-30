from grant_scout.models import Opportunity


def test_enriched_with_fills_blanks_without_clobbering():
    hit = Opportunity(id="1", source="grants.gov", title="T", funder="NSF",
                      status="posted", close_date="2026-09-01")
    detail = Opportunity(id="1", source="grants.gov", title="T", funder="NSF",
                         status="", award_floor="100000", eligibility="Nonprofits")
    merged = hit.enriched_with(detail)
    assert merged.status == "posted"          # not clobbered by detail's blank
    assert merged.award_floor == "100000"     # filled from detail
    assert merged.eligibility == "Nonprofits"
    assert merged.close_date == "2026-09-01"

from grant_scout.dedupe import dedupe_opportunities


def test_dedupe_exact_source_id():
    opps = [
        {"source": "grants.gov", "id": "1", "title": "A", "funder": "X"},
        {"source": "grants.gov", "id": "1", "title": "A", "funder": "X"},
    ]
    assert len(dedupe_opportunities(opps)) == 1


def test_dedupe_cross_source_title_funder():
    opps = [
        {"source": "grants.gov", "id": "1", "title": "Rural Literacy Grant", "funder": "Dept of Ed"},
        {"source": "eu-sedia", "id": "Z", "title": "rural literacy grant", "funder": "DEPT OF ED"},
    ]
    assert len(dedupe_opportunities(opps)) == 1


def test_dedupe_keeps_distinct():
    opps = [
        {"source": "grants.gov", "id": "1", "title": "A", "funder": "X"},
        {"source": "eu-sedia", "id": "2", "title": "B", "funder": "Y"},
    ]
    assert len(dedupe_opportunities(opps)) == 2


def test_dedupe_blank_title_not_collapsed():
    opps = [
        {"source": "a", "id": "1", "title": "", "funder": ""},
        {"source": "b", "id": "2", "title": "", "funder": ""},
    ]
    assert len(dedupe_opportunities(opps)) == 2

"""ProPublica Nonprofit Explorer — US nonprofits/foundations from IRS 990 data.

No API key. Answers "which US organizations work in my cause area" (prospecting),
not "what's open to apply for". `/v2/search.json?q=<cause>` returns organizations.

`normalize_org` is pure and unit-tested against a captured fixture.
"""

from __future__ import annotations

import httpx

from ..models import Funder

SEARCH_URL = "https://projects.propublica.org/nonprofits/api/v2/search.json"
ORG_URL = "https://projects.propublica.org/nonprofits/organizations/{ein}"

# NTEE first-letter → human-readable major group (so the CSV reads cleanly).
_NTEE_GROUPS = {
    "A": "Arts, Culture & Humanities",
    "B": "Education",
    "C": "Environment",
    "D": "Animal-Related",
    "E": "Health Care",
    "F": "Mental Health",
    "G": "Disease & Disorders",
    "H": "Medical Research",
    "I": "Crime & Legal",
    "J": "Employment",
    "K": "Food, Agriculture & Nutrition",
    "L": "Housing & Shelter",
    "M": "Public Safety & Disaster",
    "N": "Recreation & Sports",
    "O": "Youth Development",
    "P": "Human Services",
    "Q": "International & Foreign Affairs",
    "R": "Civil Rights & Advocacy",
    "S": "Community Improvement",
    "T": "Philanthropy & Grantmaking",
    "U": "Science & Technology",
    "V": "Social Science",
    "W": "Public & Societal Benefit",
    "X": "Religion-Related",
    "Y": "Mutual & Membership Benefit",
    "Z": "Unknown",
}


def _ntee_focus(code: str | None) -> str:
    if not code:
        return ""
    group = _NTEE_GROUPS.get(code[0].upper(), "")
    return f"{group} ({code})" if group else code


def normalize_org(org: dict) -> Funder:
    ein = str(org.get("ein") or "").strip()
    city = (org.get("city") or "").strip()
    state = (org.get("state") or "").strip()
    location = ", ".join(p for p in (city, state) if p)
    return Funder(
        id=ein,
        source="propublica",
        name=(org.get("name") or "").strip(),
        location=location,
        focus=_ntee_focus(org.get("ntee_code")),
        url=ORG_URL.format(ein=ein) if ein else "",
    )


class ProPublicaSource:
    name = "propublica"

    def __init__(self, *, timeout: float = 30.0, client: httpx.Client | None = None):
        self._timeout = timeout
        self._client = client

    def find(self, keyword: str, *, location: str = "", rows: int = 25) -> list[Funder]:
        params = {"q": keyword}
        if location:
            params["state[id]"] = location
        if self._client is not None:
            resp = self._client.get(SEARCH_URL, params=params)
        else:
            resp = httpx.get(SEARCH_URL, params=params, timeout=self._timeout)
        resp.raise_for_status()
        orgs = resp.json().get("organizations") or []
        return [normalize_org(o) for o in orgs[:rows]]

import pytest

from grant_scout.profile import load_profile


def test_load_example_profile(tmp_path):
    p = tmp_path / "org.toml"
    p.write_text(
        'name = "Test Org"\nein = "12-3456789"\nfocus_areas = ["education"]\n'
        'geography = ["US"]\nkeywords = ["literacy"]\n',
        encoding="utf-8",
    )
    prof = load_profile(p)
    assert prof.name == "Test Org"
    assert prof.focus_areas == ["education"]
    assert prof.keywords == ["literacy"]


def test_missing_profile_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_profile(tmp_path / "nope.toml")


def test_secret_key_rejected(tmp_path):
    p = tmp_path / "bad.toml"
    p.write_text('name = "X"\npassword = "hunter2"\n', encoding="utf-8")
    with pytest.raises(ValueError):
        load_profile(p)


def test_unknown_keys_ignored(tmp_path):
    p = tmp_path / "ok.toml"
    p.write_text('name = "X"\nsome_future_field = "y"\n', encoding="utf-8")
    prof = load_profile(p)
    assert prof.name == "X"

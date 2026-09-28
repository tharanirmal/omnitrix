"""Profiles: passphrase hashing, sessions and their timeouts, and the lock after wrong passphrases."""
import json
import stat

import pytest

from engram.profiles import FREE_TRIES, IDLE, Locked, Profiles, WrongPassphrase


class Clock:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t


def test_registry_keeps_no_passphrase_and_is_private(tmp_path):
    p = Profiles(tmp_path / "profiles.json")
    assert p.add("kaminski", "correct horse", "engram", "s2") == {"name": "kaminski", "database": "engram",
                                                                   "color": "s2"}
    raw = (tmp_path / "profiles.json").read_text()
    assert "correct horse" not in raw and json.loads(raw)["profiles"][0]["salt"]
    assert stat.S_IMODE((tmp_path / "profiles.json").stat().st_mode) == 0o600
    with pytest.raises(ValueError):
        p.add("kaminski", "another one", "other")              # the name is taken
    with pytest.raises(ValueError):
        p.add("again", "another one", "engram")                # the database belongs to kaminski
    for name, phrase, color in (("Kaminski", "long enough", "s1"), ("postgres", "long enough", "s1"),
                                ("ok", "short", "s1"), ("ok", "long enough", "red")):
        with pytest.raises(ValueError):
            p.add(name, phrase, None, color)


def test_sessions_expire_and_end(tmp_path):
    clock = Clock()
    p = Profiles(tmp_path / "profiles.json", clock=clock)
    p.add("meetings", "correct horse")
    token = p.unlock("meetings", "correct horse")
    assert p.session(token)["database"] == "meetings"
    clock.t += IDLE - 1
    assert p.session(token) is not None                        # a request keeps it alive
    clock.t += IDLE + 1
    assert p.session(token) is None                            # idle too long
    token = p.unlock("meetings", "correct horse")
    p.end(token)
    assert p.session(token) is None and p.session(None) is None and p.session("forged") is None
    token = p.unlock("meetings", "correct horse")
    p.remove("meetings")
    assert p.session(token) is None                            # a removed profile's sessions go with it


def test_wrong_passphrases_lock_the_profile_for_longer_each_time(tmp_path):
    clock = Clock()
    p = Profiles(tmp_path / "profiles.json", clock=clock)
    p.add("meetings", "correct horse")
    for left in range(FREE_TRIES - 1, 0, -1):
        with pytest.raises(WrongPassphrase) as e:
            p.unlock("meetings", "wrong")
        assert e.value.remaining == left
    with pytest.raises(Locked) as e:
        p.unlock("meetings", "wrong")
    first = e.value.seconds
    with pytest.raises(Locked):
        p.unlock("meetings", "correct horse")                  # locked means locked
    clock.t += first + 1
    with pytest.raises(Locked) as e:
        p.unlock("meetings", "wrong again")
    assert e.value.seconds == pytest.approx(2 * first)
    clock.t += e.value.seconds + 1
    assert p.unlock("meetings", "correct horse")               # right: the counter resets
    with pytest.raises(WrongPassphrase) as e:
        p.unlock("meetings", "wrong")
    assert e.value.remaining == FREE_TRIES - 1
    with pytest.raises(LookupError):
        p.unlock("nobody", "whatever")

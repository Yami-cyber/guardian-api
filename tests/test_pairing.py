"""Tests untuk endpoint & service pairing (Firestore diganti fake di memori)."""

import pytest

from app import create_app, limiter
from app.config import Config
from app.services import pairing_service
from tests.fake_firestore import FakeDb

NOW = 1_800_000_000_000  # epoch ms tetap
CHILD, PARENT, PARENT2, PARENT3 = "child1", "parent1", "parent2", "parent3"


class _FakeAuth:
    """verify_id_token: token == uid, kecuali 'bad'."""

    def verify_id_token(self, token):
        if token == "bad":
            raise ValueError("bad token")
        return {"uid": token}


@pytest.fixture
def db(monkeypatch):
    fake = FakeDb()
    monkeypatch.setattr("app.firebase_admin_client.get_firestore", lambda: fake)
    monkeypatch.setattr("app.auth.get_firestore", lambda: fake)
    monkeypatch.setattr("app.auth.get_auth", lambda: _FakeAuth())
    monkeypatch.setattr(pairing_service, "_now_ms", lambda: NOW)
    monkeypatch.setattr(pairing_service, "_run_in_transaction", lambda d, fn: fn(d.transaction()))
    monkeypatch.setattr(pairing_service, "_increment", _inc)
    fake.put("users", CHILD, {"role": "child", "display_name": "Budi", "photo_url": "http://x/b.png"})
    for uid, name in ((PARENT, "Ibu"), (PARENT2, "Ayah"), (PARENT3, "Wali")):
        fake.put("users", uid, {"role": "parent", "display_name": name})
    return fake


def _inc(n):
    from google.cloud.firestore_v1.transforms import Increment

    return Increment(n)


@pytest.fixture
def client(db):
    app = create_app(Config())
    app.config["TESTING"] = True
    limiter.reset()
    return app.test_client()


def _post(client, path, uid, body=None):
    return client.post(
        f"/api/v1/pairing/{path}",
        json=body if body is not None else {},
        headers={"Authorization": f"Bearer {uid}"},
    )


def _new_code(client) -> str:
    res = _post(client, "code", CHILD)
    assert res.status_code == 201, res.get_json()
    return res.get_json()["code"]


def _pair(client, parent) -> dict:
    res = _post(client, "redeem", parent, {"code": _new_code(client)})
    assert res.status_code == 200, res.get_json()
    return res.get_json()


# ───────────────────────── auth & role ─────────────────────────

def test_requires_auth(client):
    assert client.post("/api/v1/pairing/code").status_code == 401
    assert _post(client, "code", "bad").status_code == 401


def test_roles_enforced(client):
    assert _post(client, "code", PARENT).status_code == 403
    assert _post(client, "redeem", CHILD, {"code": "123456"}).status_code == 403
    assert _post(client, "validate", CHILD, {"code": "123456"}).status_code == 403


# ───────────────────────── create / cancel ─────────────────────────

def test_create_code_stores_expected_document(client, db):
    body = _post(client, "code", CHILD).get_json()
    code = body["code"]
    assert len(code) == 6 and code.isdigit()
    assert body["expires_at"] == NOW + 5 * 60 * 1000

    doc = db.doc("pairing_codes", code)
    assert doc["childUid"] == CHILD
    assert doc["expiresAt"] == NOW + 5 * 60 * 1000
    assert doc["childName"] == "Budi"
    assert doc["childPhoto"] == "http://x/b.png"


def test_new_code_replaces_old_one(client, db):
    first = _new_code(client)
    second = _new_code(client)
    assert db.doc("pairing_codes", first) is None or first == second
    assert db.doc("pairing_codes", second) is not None
    assert len(db.data["pairing_codes"]) == 1


def test_cancel_removes_code_and_is_idempotent(client, db):
    code = _new_code(client)
    assert _post(client, "cancel", CHILD).status_code == 200
    assert db.doc("pairing_codes", code) is None
    assert _post(client, "cancel", CHILD).status_code == 200


def test_child_cannot_create_code_when_already_has_two_parents(client):
    _pair(client, PARENT)
    _pair(client, PARENT2)
    res = _post(client, "code", CHILD)
    assert res.status_code == 409
    assert res.get_json()["error"]["code"] == "PAIRING_LIMIT"


# ───────────────────────── validate ─────────────────────────

def test_validate_returns_child_preview_without_side_effects(client, db):
    code = _new_code(client)
    res = _post(client, "validate", PARENT, {"code": code})
    assert res.status_code == 200
    body = res.get_json()
    assert body["child_name"] == "Budi" and body["child_uid"] == CHILD
    assert db.doc("pairing_codes", code) is not None
    assert not db.data.get("pairings")


@pytest.mark.parametrize("code", ["12345", "1234567", "abcdef", "12 456", "١٢٣٤٥٦"])
def test_validate_rejects_bad_format(client, code):
    res = _post(client, "validate", PARENT, {"code": code})
    assert res.status_code == 400
    assert res.get_json()["error"]["code"] == "INVALID_CODE"


def test_validate_unknown_code(client):
    res = _post(client, "validate", PARENT, {"code": "000000"})
    assert res.status_code == 404


def test_validate_expired_code(client, db, monkeypatch):
    code = _new_code(client)
    monkeypatch.setattr(pairing_service, "_now_ms", lambda: NOW + 5 * 60 * 1000 + 1)
    res = _post(client, "validate", PARENT, {"code": code})
    assert res.status_code == 400
    assert res.get_json()["error"]["code"] == "EXPIRED_CODE"


def test_validate_requires_code(client):
    assert _post(client, "validate", PARENT, {}).status_code == 400


# ───────────────────────── redeem ─────────────────────────

def test_redeem_creates_pairing_updates_counts_and_consumes_code(client, db):
    code = _new_code(client)
    res = _post(client, "redeem", PARENT, {"code": code})
    assert res.status_code == 200
    body = res.get_json()
    assert body["pairing_id"] == f"{CHILD}_{PARENT}"

    p = db.doc("pairings", f"{CHILD}_{PARENT}")
    assert p["uid_anak"] == CHILD and p["uid_orangtua"] == PARENT
    assert p["status"] == "active"
    assert p["nama_ortu"] == "Ibu" and p["nama_anak"] == "Budi"
    assert p["consent_anak"] is True and p["consent_ortu"] is True
    assert p["paired_at"] == NOW

    assert db.doc("users", CHILD)["pairing_count"] == 1
    assert db.doc("users", PARENT)["pairing_count"] == 1
    assert db.doc("pairing_codes", code) is None


def test_code_is_single_use(client):
    code = _new_code(client)
    assert _post(client, "redeem", PARENT, {"code": code}).status_code == 200
    again = _post(client, "redeem", PARENT2, {"code": code})
    assert again.status_code == 404
    assert again.get_json()["error"]["code"] == "INVALID_CODE"


def test_redeem_expired_code_creates_nothing(client, db, monkeypatch):
    code = _new_code(client)
    monkeypatch.setattr(pairing_service, "_now_ms", lambda: NOW + 6 * 60 * 1000)
    res = _post(client, "redeem", PARENT, {"code": code})
    assert res.status_code == 400
    assert not db.data.get("pairings")
    assert "pairing_count" not in db.doc("users", PARENT)


def test_redeem_own_code_rejected(client, db):
    db.put("pairing_codes", "111111", {"code": "111111", "childUid": PARENT, "expiresAt": NOW + 1000})
    res = _post(client, "redeem", PARENT, {"code": "111111"})
    assert res.status_code == 400
    assert res.get_json()["error"]["code"] == "SELF_PAIRING"
    assert not db.data.get("pairings")


def test_redeem_same_child_twice_rejected(client):
    _pair(client, PARENT)
    res = _post(client, "redeem", PARENT, {"code": _new_code(client)})
    assert res.status_code == 409
    assert res.get_json()["error"]["code"] == "ALREADY_PAIRED"


def test_third_parent_rejected_even_with_valid_code(client, db):
    _pair(client, PARENT)
    _pair(client, PARENT2)
    # Kode disisipkan langsung: menguji batas di redeem, bukan di create.
    db.put("pairing_codes", "222222", {"code": "222222", "childUid": CHILD, "expiresAt": NOW + 1000})
    res = _post(client, "redeem", PARENT3, {"code": "222222"})
    assert res.status_code == 409
    assert res.get_json()["error"]["code"] == "PAIRING_LIMIT"
    assert db.doc("pairings", f"{CHILD}_{PARENT3}") is None
    assert db.doc("users", CHILD)["pairing_count"] == 2


# ───────────────────────── revoke ─────────────────────────

def test_revoke_by_child_deletes_pairing_and_decrements(client, db):
    pid = _pair(client, PARENT)["pairing_id"]
    res = _post(client, "revoke", CHILD, {"pairing_id": pid})
    assert res.status_code == 200
    assert db.doc("pairings", pid) is None
    assert db.doc("users", CHILD)["pairing_count"] == 0
    assert db.doc("users", PARENT)["pairing_count"] == 0


def test_revoke_by_parent_keeps_other_parent(client, db):
    pid1 = _pair(client, PARENT)["pairing_id"]
    _pair(client, PARENT2)
    assert _post(client, "revoke", PARENT, {"pairing_id": pid1}).status_code == 200
    assert db.doc("pairings", f"{CHILD}_{PARENT2}") is not None
    assert db.doc("users", CHILD)["pairing_count"] == 1
    assert db.doc("users", PARENT2)["pairing_count"] == 1


def test_revoke_by_stranger_forbidden(client, db):
    pid = _pair(client, PARENT)["pairing_id"]
    res = _post(client, "revoke", PARENT2, {"pairing_id": pid})
    assert res.status_code == 403
    assert db.doc("pairings", pid) is not None
    assert db.doc("users", CHILD)["pairing_count"] == 1


def test_revoke_is_idempotent_and_count_never_negative(client, db):
    pid = _pair(client, PARENT)["pairing_id"]
    assert _post(client, "revoke", CHILD, {"pairing_id": pid}).status_code == 200
    assert _post(client, "revoke", CHILD, {"pairing_id": pid}).status_code == 200
    assert db.doc("users", CHILD)["pairing_count"] == 0


def test_revoke_requires_pairing_id(client):
    assert _post(client, "revoke", CHILD, {}).status_code == 400


# ───────────────────────── rate limit ─────────────────────────

def test_validate_is_rate_limited_per_account(client):
    statuses = [_post(client, "validate", PARENT, {"code": "000000"}).status_code for _ in range(12)]
    assert statuses[:10] == [404] * 10
    assert statuses[10:] == [429, 429]


def test_redeem_shares_nothing_with_other_accounts_limit(client):
    for _ in range(10):
        _post(client, "validate", PARENT, {"code": "000000"})
    assert _post(client, "validate", PARENT, {"code": "000000"}).status_code == 429
    # Akun lain dari IP yang sama masih di bawah batas IP.
    assert _post(client, "validate", PARENT2, {"code": "000000"}).status_code == 404

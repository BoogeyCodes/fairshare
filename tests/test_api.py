from __future__ import annotations

from conftest import register


def _group_with_two_members(make_client):
    """Alice (owner) + Bob in one group. Returns (alice_client, group_id, alice_id, bob_id)."""
    alice = make_client()
    a = register(alice, "alice@x.com", "Alice")
    bob = make_client()
    b = register(bob, "bob@x.com", "Bob")
    gid = alice.post("/api/groups", json={"name": "Flat"}).json()["id"]
    alice.post(f"/api/groups/{gid}/members", json={"email": "bob@x.com"})
    return alice, gid, a["id"], b["id"]


class TestAuth:
    def test_register_logs_in_and_me_works(self, client):
        register(client, "ada@x.com", "Ada")
        me = client.get("/api/auth/me")
        assert me.status_code == 200
        assert me.json()["email"] == "ada@x.com"

    def test_duplicate_email_rejected(self, client):
        register(client, "dup@x.com")
        body = {"email": "dup@x.com", "display_name": "X", "password": "password123"}
        assert client.post("/api/auth/register", json=body).status_code == 400

    def test_short_password_is_a_validation_error(self, client):
        r = client.post("/api/auth/register", json={"email": "s@x.com", "display_name": "S", "password": "short"})
        assert r.status_code == 422

    def test_login_and_logout(self, make_client):
        signup = make_client()
        register(signup, "grace@x.com", "Grace")
        other = make_client()
        creds = {"email": "grace@x.com", "password": "password123"}
        assert other.post("/api/auth/login", json=creds).status_code == 200
        assert other.get("/api/auth/me").status_code == 200
        assert other.post("/api/auth/logout").status_code == 204
        assert other.get("/api/auth/me").status_code == 401

    def test_wrong_password_rejected(self, make_client):
        signup = make_client()
        register(signup, "linus@x.com")
        bad = make_client()
        assert bad.post("/api/auth/login", json={"email": "linus@x.com", "password": "nope"}).status_code == 401

    def test_me_requires_auth(self, client):
        assert client.get("/api/auth/me").status_code == 401


class TestGroups:
    def test_create_and_list(self, client):
        register(client, "o@x.com")
        gid = client.post("/api/groups", json={"name": "Trip", "description": "d"}).json()["id"]
        groups = client.get("/api/groups").json()
        assert [g["id"] for g in groups] == [gid]

    def test_non_member_cannot_see_group(self, make_client):
        owner = make_client()
        register(owner, "owner@x.com")
        gid = owner.post("/api/groups", json={"name": "Secret"}).json()["id"]
        stranger = make_client()
        register(stranger, "stranger@x.com")
        assert stranger.get(f"/api/groups/{gid}").status_code == 404


class TestMembers:
    def test_owner_adds_member_who_then_sees_group(self, make_client):
        alice, gid, _, _ = _group_with_two_members(make_client)
        members = alice.get(f"/api/groups/{gid}/members").json()
        assert {m["email"] for m in members} == {"alice@x.com", "bob@x.com"}

    def test_unknown_email_is_not_found(self, client):
        register(client, "o2@x.com")
        gid = client.post("/api/groups", json={"name": "G"}).json()["id"]
        assert client.post(f"/api/groups/{gid}/members", json={"email": "ghost@x.com"}).status_code == 404

    def test_non_owner_cannot_add_members(self, make_client):
        alice, gid, _, _ = _group_with_two_members(make_client)
        bob = make_client()
        bob.post("/api/auth/login", json={"email": "bob@x.com", "password": "password123"})
        carol = make_client()
        register(carol, "carol@x.com")
        r = bob.post(f"/api/groups/{gid}/members", json={"email": "carol@x.com"})
        assert r.status_code == 403


class TestExpenses:
    def test_equal_expense_balances_and_settle(self, make_client):
        alice, gid, aid, bid = _group_with_two_members(make_client)
        alice.post(
            f"/api/groups/{gid}/expenses",
            json={"description": "Dinner", "amount_cents": 3000, "paid_by": aid, "split_type": "equal"},
        )
        balances = {b["user_id"]: b["net_cents"] for b in alice.get(f"/api/groups/{gid}/balances").json()}
        assert balances == {aid: 1500, bid: -1500}

        settle = alice.get(f"/api/groups/{gid}/settle").json()
        assert settle == [{"from_user": bid, "to_user": aid, "amount_cents": 1500}]

    def test_exact_split_via_splits(self, make_client):
        alice, gid, aid, bid = _group_with_two_members(make_client)
        r = alice.post(
            f"/api/groups/{gid}/expenses",
            json={
                "description": "Groceries",
                "amount_cents": 1000,
                "paid_by": aid,
                "split_type": "exact",
                "splits": {str(aid): 700, str(bid): 300},
            },
        )
        assert r.status_code == 201
        shares = {s["user_id"]: s["share_cents"] for s in r.json()["shares"]}
        assert shares == {aid: 700, bid: 300}

    def test_payer_must_be_a_member(self, make_client):
        alice, gid, aid, _ = _group_with_two_members(make_client)
        r = alice.post(
            f"/api/groups/{gid}/expenses",
            json={"description": "x", "amount_cents": 100, "paid_by": 9999, "split_type": "equal"},
        )
        assert r.status_code == 400

    def test_bad_exact_sum_rejected(self, make_client):
        alice, gid, aid, bid = _group_with_two_members(make_client)
        r = alice.post(
            f"/api/groups/{gid}/expenses",
            json={
                "description": "x",
                "amount_cents": 1000,
                "paid_by": aid,
                "split_type": "exact",
                "splits": {str(aid): 700, str(bid): 500},
            },
        )
        assert r.status_code == 400


class TestSettlements:
    def test_recording_a_payment_updates_balances(self, make_client):
        alice, gid, aid, bid = _group_with_two_members(make_client)
        alice.post(
            f"/api/groups/{gid}/expenses",
            json={"description": "Dinner", "amount_cents": 3000, "paid_by": aid, "split_type": "equal"},
        )
        alice.post(
            f"/api/groups/{gid}/settlements",
            json={"from_user": bid, "to_user": aid, "amount_cents": 1500},
        )
        balances = {b["user_id"]: b["net_cents"] for b in alice.get(f"/api/groups/{gid}/balances").json()}
        assert balances == {aid: 0, bid: 0}
        assert alice.get(f"/api/groups/{gid}/settle").json() == []

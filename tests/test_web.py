from __future__ import annotations


class TestWebFlow:
    def test_landing_page_renders(self, client):
        r = client.get("/")
        assert r.status_code == 200
        assert "FairShare" in r.text

    def test_register_then_land_on_groups(self, client):
        r = client.post(
            "/register",
            data={"display_name": "Ada", "email": "ada@x.com", "password": "password123"},
        )
        assert r.status_code == 200
        assert r.url.path == "/groups"
        assert "Your groups" in r.text

    def test_full_group_flow_through_the_ui(self, client):
        client.post("/register", data={"display_name": "Ada", "email": "ada@x.com", "password": "password123"})

        created = client.post("/groups", data={"name": "Trip", "description": "Lahore"})
        assert created.url.path.startswith("/groups/")
        group_path = created.url.path

        # add an expense split equally (only Ada so far -> she owes herself nothing)
        gid = group_path.rsplit("/", 1)[1]
        client.post(
            f"/groups/{gid}/expenses",
            data={
                "description": "Hotel",
                "amount": "100.00",
                "paid_by": "1",
                "split_type": "equal",
                "include_1": "on",
            },
        )
        page = client.get(group_path)
        assert page.status_code == 200
        assert "Hotel" in page.text
        assert "100.00" in page.text

    def test_settle_fragment(self, client):
        client.post("/register", data={"display_name": "Ada", "email": "ada@x.com", "password": "password123"})
        gid = client.post("/groups", data={"name": "G"}).url.path.rsplit("/", 1)[1]
        frag = client.get(f"/groups/{gid}/settle")
        assert frag.status_code == 200
        assert "settled up" in frag.text.lower()

    def test_requires_login(self, client):
        # hitting a protected page while logged out bounces to the login page
        r = client.get("/groups")
        assert r.status_code == 200
        assert r.url.path == "/"
        assert "FairShare" in r.text

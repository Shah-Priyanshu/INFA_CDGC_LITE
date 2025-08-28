def test_glossary_crud(client):
    # Create term
    r = client.post("/glossary/", json={"name": "Email", "description": "Email address"})
    assert r.status_code in (201, 409)
    if r.status_code == 201:
        tid = r.json()["id"]
    else:
        tid = next(x["id"] for x in client.get("/glossary/").json() if x["name"] == "Email")

    # Update
    r = client.patch(f"/glossary/{tid}", json={"description": "Updated"})
    assert r.status_code == 200

    # List
    r = client.get("/glossary/")
    assert r.status_code == 200
    assert isinstance(r.json(), list)

    # Delete
    assert client.delete(f"/glossary/{tid}").status_code == 204

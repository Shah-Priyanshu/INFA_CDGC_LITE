def test_asset_column_crud(client):
    # Create system
    r = client.post("/systems/", json={"name": "sys1", "description": "d"})
    if r.status_code == 201:
        sid = r.json()["id"]
    else:
        # List and find existing
        sid = next(x["id"] for x in client.get("/systems/").json() if x["name"] == "sys1")

    # Create asset
    r = client.post("/assets/", json={"system_id": sid, "name": "asset1", "description": "ad"})
    assert r.status_code == 201
    aid = r.json()["id"]

    # List assets with pagination
    r = client.get("/assets/?limit=1&offset=0")
    assert r.status_code == 200
    assert isinstance(r.json(), list)

    # Get asset
    assert client.get(f"/assets/{aid}").status_code == 200

    # Update asset
    assert client.patch(f"/assets/{aid}", json={"description": "u"}).status_code == 200

    # Create column
    r = client.post("/columns/", json={"asset_id": aid, "name": "c1", "data_type": "text"})
    assert r.status_code == 201
    cid = r.json()["id"]

    # List columns
    r = client.get("/columns/")
    assert r.status_code == 200
    assert isinstance(r.json(), list)

    # Update and delete column
    assert client.patch(f"/columns/{cid}", json={"description": "cd"}).status_code == 200
    assert client.delete(f"/columns/{cid}").status_code == 204

    # Delete asset
    assert client.delete(f"/assets/{aid}").status_code == 204

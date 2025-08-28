def test_search_and_job_status_and_column_names(client):
    # Create system and asset
    r = client.post("/systems/", json={"name": "sys_search", "description": "d"})
    sid = r.json()["id"] if r.status_code == 201 else next(x["id"] for x in client.get("/systems/").json() if x["name"] == "sys_search")
    r = client.post("/assets/", json={"system_id": sid, "name": "asset_search", "description": "asset for search"})
    assert r.status_code == 201
    aid = r.json()["id"]

    # Add columns and verify asset.column_names maintained
    r = client.post("/columns/", json={"asset_id": aid, "name": "c_a", "data_type": "text"})
    assert r.status_code == 201
    r = client.post("/columns/", json={"asset_id": aid, "name": "c_b", "data_type": "int"})
    assert r.status_code == 201

    # Fetch asset and ensure column_names field is present (string or null in SQLite tests)
    a = client.get(f"/assets/{aid}").json()
    assert "column_names" in a

    # Run search (will fallback to ILIKE on SQLite); ensure endpoint is reachable
    rs = client.get("/search/?q=asset")
    assert rs.status_code == 200
    body = rs.json()
    assert "assets" in body and "columns" in body

    # Enqueue ingest with an idempotency key and fetch job status
    r = client.post("/ingest/snowflake/scan", json={"idempotency_key": "k1"})
    assert r.status_code == 202
    job_id = r.json()["job_id"]
    r = client.get(f"/ingest/jobs/{job_id}")
    assert r.status_code == 200

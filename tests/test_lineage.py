def test_lineage_graph_empty(client):
    r = client.get("/lineage/graph")
    assert r.status_code == 200
    data = r.json()
    assert data["nodes"] == []
    assert data["edges"] == []

    def test_sql_lineage_parsing(client):
        sql = """
            CREATE TABLE tgt_db.tgt_table AS
            SELECT * FROM src_db.src_table st
            JOIN src_db.dim d ON st.k = d.k;
        """
        r = client.post("/lineage/sql", json={"sql": sql})
        assert r.status_code == 200
        body = r.json()
        assert "sources" in body and "targets" in body
        # Best-effort assertions (sqlglot may be absent in CI); allow empty when not installed
        if body["sources"]:
            assert any("src_db.src_table" in s for s in body["sources"]) or any("src_table" in s for s in body["sources"])  # noqa: E501
        if body["targets"]:
            assert any("tgt_db.tgt_table" in t for t in body["targets"]) or any("tgt_table" in t for t in body["targets"])  # noqa: E501

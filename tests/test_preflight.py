from schema_lens.schema.preflight import run_preflight


def _schema_with_copyfields():
    return {
        "schema": {
            "fields": [
                {"name": "title", "type": "text_general"},
                {"name": "title_txt", "type": "text_general"},
            ],
            "dynamicFields": [{"name": "*_txt", "type": "text_general"}],
            "copyFields": [{"source": "title", "dest": "title_txt"}],
        }
    }


def test_preflight_no_findings_for_query_only_changes():
    report = run_preflight(
        _schema_with_copyfields(),
        [{"op": "queryparams.set", "set": {"qf": "title^2"}}],
        fail_on_risk=False,
    )
    assert report["summary"]["total"] == 0
    assert report["block_run"] is False


def test_preflight_detects_copyfield_replace_risk_and_block():
    report = run_preflight(
        _schema_with_copyfields(),
        [{"op": "schema.fieldType.replace", "name": "text_general", "with": "text_en"}],
        fail_on_risk=True,
    )
    assert report["summary"]["total"] > 0
    codes = {f["code"] for f in report["findings"]}
    assert "COPYFIELD_COMPAT_RISK" in codes
    assert "REPLACE_FIELDTYPE_COPYFIELD_DEST_HAZARD" in codes
    assert report["block_run"] is True


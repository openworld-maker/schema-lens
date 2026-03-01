from schema_lens.schema.graph import build_schema_graph


def test_build_schema_graph_extracts_dependencies():
    schema = {
        "schema": {
            "fields": [
                {"name": "id", "type": "string"},
                {"name": "title", "type": "text_general"},
            ],
            "dynamicFields": [
                {"name": "*_txt", "type": "text_general"},
            ],
            "copyFields": [
                {"source": "title", "dest": "title_txt"},
            ],
        }
    }

    graph = build_schema_graph(schema)
    assert graph.fields["title"] == "text_general"
    assert graph.dynamic_fields["*_txt"] == "text_general"
    assert graph.copy_fields[0]["source"] == "title"
    assert "title" in graph.field_type_to_fields["text_general"]
    assert "*_txt" in graph.field_type_to_dynamic_fields["text_general"]


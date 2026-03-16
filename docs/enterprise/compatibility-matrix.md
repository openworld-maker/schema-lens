# Solr Compatibility Matrix

| Solr target | Support tier | Notes |
|---|---|---|
| 8.x | supported_with_fallbacks | vector/v2 may be unavailable; fallback paths are reported |
| 9.x | recommended | full governance workflows supported |
| 10.x | forward_ready | compatibility confidence medium until broad field validation |
| unknown/custom | unknown | safe degradations with explicit missing capability reporting |

Fixtures:

- `examples/compat/solr8_system_info.json`
- `examples/compat/solr9_system_info.json`
- `examples/compat/solr10_system_info.json`

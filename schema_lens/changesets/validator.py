"""Changeset validator."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from schema_lens.changesets.model import Changeset
from schema_lens.changesets.operations import SUPPORTED_OPS

CONFIGSET_UPDATE_MODES = {"replace", "patch_append", "patch_merge"}
VECTOR_SCENARIO_MODES = {"lexical_only", "vector_only", "hybrid"}
VECTOR_SIMILARITIES = {"cosine", "dot", "euclidean"}
VECTOR_QUERY_VECTOR_POLICIES = {"skip", "fail"}
VECTOR_BLEND_METHODS = {"linear", "normalize_linear", "rrf"}
VECTOR_BLEND_EXECUTION = {"auto", "client", "solr_native"}
VECTOR_NORMALIZE = {"none", "minmax", "zscore"}
SECURITY_PROFILES = {
    "local-dev",
    "enterprise-safe",
    "no-persist-sensitive",
    "redacted-artifacts-only",
}
SECURITY_AUTH_TYPES = {"none", "basic", "bearer", "mtls", "plugin", "kerberos"}
GOV_PROMOTION_STATES = {"dev", "stage", "prod_candidate", "prod_approved"}
PRIVACY_PROFILES = {"off", "default", "export-safe"}


@dataclass
class ValidationReport:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors


def _get_in(data: dict[str, Any], dotted: str) -> Any:
    cur: Any = data
    for part in dotted.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return None
        cur = cur[part]
    return cur


def _resolve_input_path(base_file: Path | None, raw_path: str) -> Path:
    path = Path(raw_path)
    if path.is_absolute():
        return path

    candidates = []
    if base_file is not None:
        candidates.append((base_file.parent / path).resolve())
    candidates.append((Path.cwd() / path).resolve())

    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0]


def validate_changeset(changeset: Changeset, check_paths: bool = True) -> ValidationReport:
    report = ValidationReport()
    raw = changeset.raw
    legacy_version = raw.get("schema_lens_version")
    new_version = raw.get("solrguard_version")
    version = new_version if new_version is not None else legacy_version
    if version not in (None, 1):
        report.errors.append(f"Unsupported changeset version: {version}")
    if legacy_version is not None and new_version is None:
        report.warnings.append(
            "schema_lens_version is deprecated; prefer solrguard_version (legacy key remains supported)."
        )
    if legacy_version is not None and new_version is not None and legacy_version != new_version:
        report.errors.append(
            "schema_lens_version and solrguard_version both set with different values."
        )

    required = ["baseline.solr_url", "baseline.collection"]
    for key in required:
        if _get_in(raw, key) in (None, ""):
            report.errors.append(f"Missing required field: {key}")

    docs_source = _get_in(raw, "data.docs_source") or {}
    if not isinstance(docs_source, dict):
        report.errors.append("data.docs_source must be an object")
        docs_source = {}
    docs_source_type = str(docs_source.get("type", "file"))
    if docs_source_type not in {"file", "solr", "plugin"}:
        report.errors.append("data.docs_source.type must be 'file', 'solr', or 'plugin'")
    if docs_source_type == "file":
        if not docs_source.get("path"):
            report.errors.append("Missing required field: data.docs_source.path")
    elif docs_source_type == "plugin":
        if not docs_source.get("provider"):
            report.errors.append("Missing required field: data.docs_source.provider")
    else:
        for key in ("solr_url", "collection"):
            if not docs_source.get(key):
                report.errors.append(f"Missing required field: data.docs_source.{key}")
        mode = docs_source.get("mode")
        if mode and mode not in {"export", "cursormark"}:
            report.errors.append("data.docs_source.mode must be 'export' or 'cursormark'")

    query_source = _get_in(raw, "queries.source") or {}
    if not isinstance(query_source, dict):
        report.errors.append("queries.source must be an object")
        query_source = {}
    query_source_type = str(query_source.get("type", "file"))
    if query_source_type not in {"file", "log", "plugin"}:
        report.errors.append("queries.source.type must be 'file', 'log', or 'plugin'")
    if query_source_type in {"file", "log"} and not query_source.get("path"):
        report.errors.append("Missing required field: queries.source.path")
    if query_source_type == "plugin" and not query_source.get("provider"):
        report.errors.append("Missing required field: queries.source.provider")

    if query_source_type == "log":
        fmt = str(query_source.get("format", "solr_params"))
        if fmt not in {"solr_params", "jsonl"}:
            report.errors.append("queries.source.format must be 'solr_params' or 'jsonl'")

    sampling_mode = _get_in(raw, "queries.sampling.mode")
    if sampling_mode is not None and sampling_mode not in {"top", "reservoir"}:
        report.errors.append("queries.sampling.mode must be 'top' or 'reservoir'")

    preflight_fail = _get_in(raw, "preflight.fail_on_risk")
    if preflight_fail is not None and not isinstance(preflight_fail, bool):
        report.errors.append("preflight.fail_on_risk must be boolean")

    replay_capture = _get_in(raw, "replay.capture")
    if replay_capture is not None and not isinstance(replay_capture, dict):
        report.errors.append("replay.capture must be an object")
    if isinstance(replay_capture, dict):
        facets = replay_capture.get("facets")
        if facets is not None and not isinstance(facets, dict):
            report.errors.append("replay.capture.facets must be an object")
        if isinstance(facets, dict):
            enabled = facets.get("enabled")
            if enabled is not None and not isinstance(enabled, bool):
                report.errors.append("replay.capture.facets.enabled must be boolean")
            if facets.get("enabled"):
                fields = facets.get("fields")
                if not isinstance(fields, list) or not all(isinstance(x, str) for x in fields):
                    report.errors.append(
                        "replay.capture.facets.fields must be a list of strings "
                        "when facets are enabled"
                    )
            limit = facets.get("limit")
            if limit is not None:
                try:
                    if int(limit) <= 0:
                        raise ValueError
                except (TypeError, ValueError):
                    report.errors.append("replay.capture.facets.limit must be an integer > 0")
        for field_name in ("track_numfound", "track_sort"):
            field_val = replay_capture.get(field_name)
            if field_val is not None and not isinstance(field_val, bool):
                report.errors.append(f"replay.capture.{field_name} must be boolean")

    performance = raw.get("performance")
    if performance is not None and not isinstance(performance, dict):
        report.errors.append("performance must be an object")
        performance = {}
    if isinstance(performance, dict):
        enabled = performance.get("enabled")
        if enabled is not None and not isinstance(enabled, bool):
            report.errors.append("performance.enabled must be boolean")
        warmup = performance.get("warmup")
        if warmup is not None and not isinstance(warmup, dict):
            report.errors.append("performance.warmup must be an object")
        capture = performance.get("capture")
        if capture is not None and not isinstance(capture, dict):
            report.errors.append("performance.capture must be an object")
        if isinstance(capture, dict):
            percentiles = capture.get("percentiles")
            if percentiles is not None:
                if not isinstance(percentiles, list) or not all(
                    isinstance(item, int) for item in percentiles
                ):
                    report.errors.append("performance.capture.percentiles must be a list of ints")
        caches = performance.get("caches")
        if caches is not None and not isinstance(caches, dict):
            report.errors.append("performance.caches must be an object")

    security = raw.get("security")
    if security is not None and not isinstance(security, dict):
        report.errors.append("security must be an object")
        security = {}
    if isinstance(security, dict):
        profile = security.get("profile")
        if profile is not None and str(profile) not in SECURITY_PROFILES:
            report.errors.append(
                f"security.profile must be one of {sorted(SECURITY_PROFILES)}"
            )
        for auth_field in ("baseline_auth", "shadow_auth"):
            auth_cfg = security.get(auth_field)
            if auth_cfg is not None and not isinstance(auth_cfg, dict):
                report.errors.append(f"security.{auth_field} must be an object")
                continue
            if isinstance(auth_cfg, dict):
                auth_type = str(auth_cfg.get("type", "none")).lower()
                if auth_type not in SECURITY_AUTH_TYPES:
                    report.errors.append(
                        f"security.{auth_field}.type must be one of {sorted(SECURITY_AUTH_TYPES)}"
                    )
                if auth_type == "basic":
                    if not any(auth_cfg.get(name) for name in ("username", "username_env", "username_file")):
                        report.errors.append(
                            f"security.{auth_field} basic auth requires username or *_env/*_file"
                        )
                    if not any(auth_cfg.get(name) for name in ("password", "password_env", "password_file")):
                        report.errors.append(
                            f"security.{auth_field} basic auth requires password or *_env/*_file"
                        )
                if auth_type == "bearer" and not any(
                    auth_cfg.get(name) for name in ("token", "token_env", "token_file")
                ):
                    report.errors.append(
                        f"security.{auth_field} bearer auth requires token or *_env/*_file"
                    )
                if auth_type in {"plugin", "kerberos"} and not auth_cfg.get("provider"):
                    report.errors.append(
                        f"security.{auth_field} {auth_type} auth requires provider plugin name"
                    )

    observability = raw.get("observability")
    if observability is not None and not isinstance(observability, dict):
        report.errors.append("observability must be an object")
        observability = {}
    if isinstance(observability, dict):
        enabled = observability.get("enabled")
        if enabled is not None and not isinstance(enabled, bool):
            report.errors.append("observability.enabled must be boolean")
        prometheus = observability.get("prometheus")
        if prometheus is not None and not isinstance(prometheus, dict):
            report.errors.append("observability.prometheus must be an object")
        elif isinstance(prometheus, dict):
            p_enabled = prometheus.get("enabled")
            if p_enabled is not None and not isinstance(p_enabled, bool):
                report.errors.append("observability.prometheus.enabled must be boolean")
        otel = observability.get("otel")
        if otel is not None and not isinstance(otel, dict):
            report.errors.append("observability.otel must be an object")
        elif isinstance(otel, dict):
            o_enabled = otel.get("enabled")
            if o_enabled is not None and not isinstance(o_enabled, bool):
                report.errors.append("observability.otel.enabled must be boolean")
        webhooks = observability.get("webhooks")
        if webhooks is not None and not isinstance(webhooks, dict):
            report.errors.append("observability.webhooks must be an object")
        elif isinstance(webhooks, dict):
            w_enabled = webhooks.get("enabled")
            if w_enabled is not None and not isinstance(w_enabled, bool):
                report.errors.append("observability.webhooks.enabled must be boolean")
            urls = webhooks.get("urls")
            if urls is not None and (
                not isinstance(urls, list) or not all(isinstance(item, str) for item in urls)
            ):
                report.errors.append("observability.webhooks.urls must be a list of strings")

    plugins = raw.get("plugins")
    if plugins is not None and not isinstance(plugins, dict):
        report.errors.append("plugins must be an object")
        plugins = {}
    if isinstance(plugins, dict):
        enabled = plugins.get("enabled")
        if enabled is not None and not isinstance(enabled, bool):
            report.errors.append("plugins.enabled must be boolean")
        strict_mode = plugins.get("strict_mode", plugins.get("strict"))
        if strict_mode is not None and not isinstance(strict_mode, bool):
            report.errors.append("plugins.strict_mode must be boolean")
        directories = plugins.get("directories", plugins.get("paths"))
        if directories is not None and (
            not isinstance(directories, list) or not all(isinstance(item, str) for item in directories)
        ):
            report.errors.append("plugins.directories must be a list of strings")
        enabled_plugins = plugins.get("enabled_plugins", plugins.get("enable_plugins"))
        if enabled_plugins is not None and (
            not isinstance(enabled_plugins, list)
            or not all(isinstance(item, str) for item in enabled_plugins)
        ):
            report.errors.append("plugins.enabled_plugins must be a list of strings")
        plugin_config = plugins.get("config")
        if plugin_config is not None and not isinstance(plugin_config, (str, dict)):
            report.errors.append("plugins.config must be a file path or object")

    governance = raw.get("governance")
    if governance is not None and not isinstance(governance, dict):
        report.errors.append("governance must be an object")
        governance = {}
    if isinstance(governance, dict):
        enabled = governance.get("enabled")
        if enabled is not None and not isinstance(enabled, bool):
            report.errors.append("governance.enabled must be boolean")
        approval = governance.get("approval")
        if approval is not None and not isinstance(approval, dict):
            report.errors.append("governance.approval must be an object")
        if bool(enabled):
            if not isinstance(approval, dict) or not str(approval.get("requested_by", "")).strip():
                report.errors.append(
                    "governance.approval.requested_by is required when governance.enabled=true"
                )
        promotion_state = governance.get("promotion_state")
        if promotion_state is not None and str(promotion_state) not in GOV_PROMOTION_STATES:
            report.errors.append(
                f"governance.promotion_state must be one of {sorted(GOV_PROMOTION_STATES)}"
            )
        exceptions = governance.get("exceptions")
        if exceptions is not None and not isinstance(exceptions, list):
            report.errors.append("governance.exceptions must be a list")
        bundles = governance.get("policy_bundles")
        if bundles is not None and (
            not isinstance(bundles, list) or not all(isinstance(item, str) for item in bundles)
        ):
            report.errors.append("governance.policy_bundles must be a list of strings")
        signing = governance.get("signing")
        if signing is not None and not isinstance(signing, dict):
            report.errors.append("governance.signing must be an object")
        if isinstance(signing, dict):
            s_enabled = signing.get("enabled")
            if s_enabled is not None and not isinstance(s_enabled, bool):
                report.errors.append("governance.signing.enabled must be boolean")
            if bool(s_enabled) and not any(
                signing.get(key) for key in ("secret", "secret_env")
            ):
                report.errors.append(
                    "governance.signing requires secret or secret_env when enabled=true"
                )

    segments = raw.get("segments")
    if segments is not None and not isinstance(segments, dict):
        report.errors.append("segments must be an object")
        segments = {}
    if isinstance(segments, dict):
        enabled = segments.get("enabled")
        if enabled is not None and not isinstance(enabled, bool):
            report.errors.append("segments.enabled must be boolean")
        keys = segments.get("keys")
        if keys is not None and (
            not isinstance(keys, list) or not all(isinstance(item, str) for item in keys)
        ):
            report.errors.append("segments.keys must be a list of strings")
        policy = segments.get("policy")
        if policy is not None and not isinstance(policy, dict):
            report.errors.append("segments.policy must be an object")

    privacy = raw.get("privacy")
    if privacy is not None and not isinstance(privacy, dict):
        report.errors.append("privacy must be an object")
        privacy = {}
    if isinstance(privacy, dict):
        profile = privacy.get("profile")
        if profile is not None and str(profile) not in PRIVACY_PROFILES:
            report.errors.append(f"privacy.profile must be one of {sorted(PRIVACY_PROFILES)}")
        for key in ("allowlist", "denylist"):
            values = privacy.get(key)
            if values is not None and (
                not isinstance(values, list) or not all(isinstance(item, str) for item in values)
            ):
                report.errors.append(f"privacy.{key} must be a list of strings")
        for key in ("no_persist_sensitive",):
            value = privacy.get(key)
            if value is not None and not isinstance(value, bool):
                report.errors.append(f"privacy.{key} must be boolean")

    rewrite_diff = _get_in(raw, "evaluation.rewrite_diff")
    if rewrite_diff is not None and not isinstance(rewrite_diff, dict):
        report.errors.append("evaluation.rewrite_diff must be an object")
    if isinstance(rewrite_diff, dict):
        enabled = rewrite_diff.get("enabled")
        if enabled is not None and not isinstance(enabled, bool):
            report.errors.append("evaluation.rewrite_diff.enabled must be boolean")
        for key in ("max_queries", "clause_spike_threshold"):
            value = rewrite_diff.get(key)
            if value is not None:
                try:
                    if int(value) <= 0:
                        raise ValueError
                except (TypeError, ValueError):
                    report.errors.append(f"evaluation.rewrite_diff.{key} must be an integer > 0")
        debug_mode = rewrite_diff.get("debug_mode")
        if debug_mode is not None and debug_mode not in {"debugQuery", "results"}:
            report.errors.append(
                "evaluation.rewrite_diff.debug_mode must be 'debugQuery' or 'results'"
            )
        always_for_high_risk = rewrite_diff.get("always_for_high_risk")
        if always_for_high_risk is not None and not isinstance(always_for_high_risk, bool):
            report.errors.append("evaluation.rewrite_diff.always_for_high_risk must be boolean")

    vector_cfg = raw.get("vector")
    if vector_cfg is not None and not isinstance(vector_cfg, dict):
        report.errors.append("vector must be an object")
        vector_cfg = {}
    if isinstance(vector_cfg, dict):
        enabled = vector_cfg.get("enabled")
        if enabled is not None and not isinstance(enabled, bool):
            report.errors.append("vector.enabled must be boolean")

        if vector_cfg.get("enabled"):
            field = vector_cfg.get("field")
            if not isinstance(field, str) or not field.strip():
                report.errors.append("vector.field is required when vector.enabled=true")

            dimension = vector_cfg.get("dimension")
            if dimension is not None:
                try:
                    if int(dimension) <= 0:
                        raise ValueError
                except (TypeError, ValueError):
                    report.errors.append("vector.dimension must be an integer > 0")

            similarity = vector_cfg.get("similarity")
            if similarity is not None and similarity not in VECTOR_SIMILARITIES:
                report.errors.append(
                    f"vector.similarity must be one of {sorted(VECTOR_SIMILARITIES)}"
                )

            qv_policy = vector_cfg.get("query_vector_policy")
            if qv_policy is not None and qv_policy not in VECTOR_QUERY_VECTOR_POLICIES:
                report.errors.append(
                    "vector.query_vector_policy must be one of ['fail', 'skip']"
                )

            embedding_source = vector_cfg.get("embedding_source", {})
            if embedding_source is not None and not isinstance(embedding_source, dict):
                report.errors.append("vector.embedding_source must be an object")
                embedding_source = {}
            if isinstance(embedding_source, dict):
                source_type = str(embedding_source.get("type", "none"))
                if source_type not in {"file", "none"}:
                    report.errors.append("vector.embedding_source.type must be 'file' or 'none'")
                if source_type == "file":
                    if (
                        not isinstance(embedding_source.get("path"), str)
                        or not embedding_source.get("path")
                    ):
                        report.errors.append(
                            "vector.embedding_source.path is required when type=file"
                        )

            scenarios = vector_cfg.get("scenarios")
            if not isinstance(scenarios, list) or not scenarios:
                report.errors.append("vector.scenarios must be a non-empty list when enabled")
            else:
                seen_names: set[str] = set()
                for idx, scenario in enumerate(scenarios):
                    loc = f"vector.scenarios[{idx}]"
                    if not isinstance(scenario, dict):
                        report.errors.append(f"{loc} must be an object")
                        continue
                    name = scenario.get("name")
                    if not isinstance(name, str) or not name.strip():
                        report.errors.append(f"{loc}.name is required")
                    elif name in seen_names:
                        report.errors.append(f"{loc}.name must be unique (duplicate: {name})")
                    else:
                        seen_names.add(name)

                    mode = scenario.get("mode")
                    if mode not in VECTOR_SCENARIO_MODES:
                        report.errors.append(
                            f"{loc}.mode must be one of {sorted(VECTOR_SCENARIO_MODES)}"
                        )
                        continue

                    if mode in {"vector_only", "hybrid"}:
                        knn = scenario.get("knn")
                        if not isinstance(knn, dict):
                            report.errors.append(f"{loc}.knn must be an object")
                        else:
                            for key in ("k", "topK"):
                                value = knn.get(key)
                                if value is not None:
                                    try:
                                        if int(value) <= 0:
                                            raise ValueError
                                    except (TypeError, ValueError):
                                        report.errors.append(f"{loc}.knn.{key} must be integer > 0")
                    if mode == "hybrid":
                        blend = scenario.get("blend")
                        if not isinstance(blend, dict):
                            report.errors.append(f"{loc}.blend must be an object")
                        else:
                            method = blend.get("method")
                            if method is not None and method not in VECTOR_BLEND_METHODS:
                                report.errors.append(
                                    f"{loc}.blend.method must be one of "
                                    f"{sorted(VECTOR_BLEND_METHODS)}"
                                )
                            execution = blend.get("execution")
                            if execution is not None and execution not in VECTOR_BLEND_EXECUTION:
                                report.errors.append(
                                    f"{loc}.blend.execution must be one of "
                                    f"{sorted(VECTOR_BLEND_EXECUTION)}"
                                )
                            normalize = blend.get("normalize")
                            if normalize is not None and normalize not in VECTOR_NORMALIZE:
                                report.errors.append(
                                    f"{loc}.blend.normalize must be one of "
                                    f"{sorted(VECTOR_NORMALIZE)}"
                                )

    vector_eval = _get_in(raw, "evaluation.vector_hybrid")
    if vector_eval is not None and not isinstance(vector_eval, dict):
        report.errors.append("evaluation.vector_hybrid must be an object")
        vector_eval = {}
    if isinstance(vector_eval, dict):
        enabled = vector_eval.get("enabled")
        if enabled is not None and not isinstance(enabled, bool):
            report.errors.append("evaluation.vector_hybrid.enabled must be boolean")
        for key in ("topK", "candidate_pool"):
            value = vector_eval.get(key)
            if value is not None:
                try:
                    if int(value) <= 0:
                        raise ValueError
                except (TypeError, ValueError):
                    report.errors.append(f"evaluation.vector_hybrid.{key} must be integer > 0")

        sensitivity = vector_eval.get("sensitivity")
        if sensitivity is not None and not isinstance(sensitivity, dict):
            report.errors.append("evaluation.vector_hybrid.sensitivity must be an object")
        if isinstance(sensitivity, dict):
            enabled = sensitivity.get("enabled")
            if enabled is not None and not isinstance(enabled, bool):
                report.errors.append("evaluation.vector_hybrid.sensitivity.enabled must be boolean")
            weights = sensitivity.get("weights")
            if weights is not None:
                if not isinstance(weights, list) or not weights:
                    report.errors.append(
                        "evaluation.vector_hybrid.sensitivity.weights must be a non-empty list"
                    )
                else:
                    for idx, value in enumerate(weights):
                        try:
                            float(value)
                        except (TypeError, ValueError):
                            report.errors.append(
                                "evaluation.vector_hybrid.sensitivity.weights"
                                f"[{idx}] must be numeric"
                            )

    changes = raw.get("changes", [])
    if not isinstance(changes, list):
        report.errors.append("changes must be a list")
        changes = []

    if not changes:
        report.warnings.append("No changes specified; run will still execute query replay")

    configset_source_files: list[str] = []

    for idx, op in enumerate(changes):
        loc = f"changes[{idx}]"
        if not isinstance(op, dict):
            report.errors.append(f"{loc} must be an object")
            continue

        op_name = op.get("op")
        if op_name not in SUPPORTED_OPS:
            report.errors.append(f"{loc}.op unsupported: {op_name}")
            continue

        if op_name == "schema.field.update":
            if not op.get("field"):
                report.errors.append(f"{loc}.field is required")
            if not isinstance(op.get("set"), dict):
                report.errors.append(f"{loc}.set must be an object")

        if op_name == "schema.fieldType.replace":
            if not op.get("name") or not op.get("with"):
                report.errors.append(f"{loc}.name and {loc}.with are required")

        if op_name == "schema.analyzer.remove_filter":
            required_keys = ["fieldType", "analyzer", "filter_class"]
            for rk in required_keys:
                if not op.get(rk):
                    report.errors.append(f"{loc}.{rk} is required")
            if op.get("analyzer") not in (None, "index", "query"):
                report.errors.append(f"{loc}.analyzer must be 'index' or 'query'")

        if op_name == "queryparams.set" and not isinstance(op.get("set"), dict):
            report.errors.append(f"{loc}.set must be an object")

        if op_name in {"schema.synonym.update", "schema.stopwords.update"}:
            mode = op.get("mode")
            if mode not in CONFIGSET_UPDATE_MODES:
                report.errors.append(
                    f"{loc}.mode must be one of {sorted(CONFIGSET_UPDATE_MODES)}"
                )
            target = op.get("target")
            if not isinstance(target, dict):
                report.errors.append(f"{loc}.target must be an object")
                target = {}
            files = target.get("files")
            if not isinstance(files, list) or not files:
                report.errors.append(f"{loc}.target.files must be a non-empty list")
                files = []

            op_source_file = op.get("source_file")
            if op_source_file is not None and not isinstance(op_source_file, str):
                report.errors.append(f"{loc}.source_file must be a string path")
                op_source_file = None

            if isinstance(op_source_file, str):
                configset_source_files.append(op_source_file)

            for file_idx, entry in enumerate(files):
                file_loc = f"{loc}.target.files[{file_idx}]"
                if not isinstance(entry, dict):
                    report.errors.append(f"{file_loc} must be an object")
                    continue
                if not isinstance(entry.get("path"), str) or not entry.get("path"):
                    report.errors.append(f"{file_loc}.path is required")

                entry_mode = entry.get("mode")
                if entry_mode is not None and entry_mode not in CONFIGSET_UPDATE_MODES:
                    report.errors.append(
                        f"{file_loc}.mode must be one of {sorted(CONFIGSET_UPDATE_MODES)}"
                    )

                entry_source = entry.get("source_file")
                if entry_source is not None and not isinstance(entry_source, str):
                    report.errors.append(f"{file_loc}.source_file must be a string path")
                elif isinstance(entry_source, str):
                    configset_source_files.append(entry_source)

                if entry.get("source_file") is None and op_source_file is None:
                    report.errors.append(
                        f"{file_loc}.source_file is required when {loc}.source_file is not set"
                    )

    if check_paths:
        docs_path = _get_in(raw, "data.docs_source.path") if docs_source_type == "file" else None
        queries_path = _get_in(raw, "queries.source.path")
        path_entries = [("queries.source.path", queries_path)]
        if docs_path is not None:
            path_entries.append(("data.docs_source.path", docs_path))
        vector_embedding_path = _get_in(raw, "vector.embedding_source.path")
        vector_embedding_type = _get_in(raw, "vector.embedding_source.type")
        if (
            isinstance(vector_embedding_path, str)
            and str(vector_embedding_type or "none") == "file"
        ):
            path_entries.append(("vector.embedding_source.path", vector_embedding_path))
        for label, p in path_entries:
            if isinstance(p, str):
                fp = _resolve_input_path(changeset.path, p)
                if not fp.exists():
                    report.errors.append(f"{label} does not exist: {fp}")
        seen_cfg_paths: set[Path] = set()
        for raw_source in configset_source_files:
            fp = _resolve_input_path(changeset.path, raw_source)
            if fp in seen_cfg_paths:
                continue
            seen_cfg_paths.add(fp)
            if not fp.exists():
                report.errors.append(f"configset source_file does not exist: {fp}")

        baseline_cfg_dir = _get_in(raw, "shadow.baseline_configset_dir")
        if isinstance(baseline_cfg_dir, str):
            cfg_dir = _resolve_input_path(changeset.path, baseline_cfg_dir)
            if not cfg_dir.exists() or not cfg_dir.is_dir():
                report.errors.append(
                    f"shadow.baseline_configset_dir does not exist or is not a directory: {cfg_dir}"
                )

    return report

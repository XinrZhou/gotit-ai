"""Shared day/plan/note/claim/drill/resume/memory/prompt/harness operations.

Barrel re-exporting the subdomain modules so callers keep using
``from gotit.db import ops as day_ops`` and ``day_ops.<name>`` unchanged.
"""

from __future__ import annotations

from gotit.db.ops._common import (
    DEFAULT_USER_ID,
    EXCERPT_LEN,
    _claim_view,
    _excerpt,
    _note_view,
    _plan_item_view,
)
from gotit.db.ops.claim import (
    apply_examine_result,
    apply_examine_verdict,
    list_project_claims,
    list_topic_claims_today,
)
from gotit.db.ops.connectors import (
    delete_connector,
    get_connector,
    import_connectors,
    list_connectors,
    normalize_connector_config,
    parse_mcp_servers_json,
    set_connector_status,
    update_connector,
    upsert_connector,
)
from gotit.db.ops.day import (
    add_chat_message,
    delete_plan_item,
    ensure_day,
    fill_today_from_queue,
    get_plan,
    get_today,
    list_chat_messages,
    list_due_claims,
    update_plan_item,
    upsert_plan_item,
)
from gotit.db.ops.drill import (
    _drill_material_view,
    _drill_session_view,
    append_drill_message,
    create_drill_session,
    delete_drill_material,
    finish_drill_session,
    get_drill_session,
    list_drill_materials,
    list_drill_sessions,
    upsert_drill_material,
)
from gotit.db.ops.harness import (
    _harness_case_view,
    _harness_run_view,
    add_harness_case_result,
    add_harness_run,
    finalize_harness_run,
    list_harness_case_results,
    list_harness_runs,
)
from gotit.db.ops.identity import (
    get_identity,
    list_identities,
    seed_default_identities,
    upsert_identity,
)
from gotit.db.ops.memory import (
    _memory_view,
    add_memory,
    append_trajectory,
    count_prior_failures,
    list_memory,
    list_trajectory,
)
from gotit.db.ops.shell import (
    build_graph_v0,
    build_profile_v0,
    list_shell_activity,
    record_interest,
    record_shell_event,
)
from gotit.db.ops.note import (
    _strip_html,
    add_note,
    curate_claims,
    delete_note,
    delete_notes,
    get_note,
    ingest_note,
    list_all_notes,
    list_note_claims,
    list_notes,
    list_project_notes,
    stub_extract_claim,
)
from gotit.db.ops.project import (
    _project_view,
    archive_project,
    create_project,
    get_project,
    list_projects,
    project_progress,
    update_project,
)
from gotit.db.ops.prompt import (
    _prompt_view,
    get_active_prompt,
    list_prompts,
    register_prompts,
)
from gotit.db.ops.resume import (
    _resume_pk,
    _resume_view,
    apply_resume,
    get_resume,
    upsert_resume,
)
from gotit.db.ops.skills import (
    delete_user_skill,
    get_skill_detail,
    install_skill,
    list_skill_catalog,
    parse_skill_markdown,
    resolve_skill_body,
    set_skill_enabled,
    update_skill_markdown,
)
from gotit.db.ops.thread import (
    add_message,
    clear_ball,
    count_user_messages,
    create_thread,
    delete_thread,
    derive_thread_title,
    get_ball,
    get_thread,
    list_messages,
    list_threads,
    set_ball,
    touch_thread,
    update_thread_title,
)

__all__ = [
    "DEFAULT_USER_ID",
    "EXCERPT_LEN",
    # private helpers re-exported for legacy `day_ops._<name>` callers
    "_claim_view",
    "_excerpt",
    "_note_view",
    "_plan_item_view",
    "_drill_material_view",
    "_drill_session_view",
    "_harness_case_view",
    "_harness_run_view",
    "_memory_view",
    "_project_view",
    "_prompt_view",
    "_resume_pk",
    "_resume_view",
    "_strip_html",
    # day / plan / chat
    "ensure_day",
    "get_plan",
    "upsert_plan_item",
    "update_plan_item",
    "delete_plan_item",
    "list_due_claims",
    "fill_today_from_queue",
    "get_today",
    "list_chat_messages",
    "add_chat_message",
    # note / ingest
    "add_note",
    "list_notes",
    "list_all_notes",
    "get_note",
    "delete_note",
    "delete_notes",
    "stub_extract_claim",
    "ingest_note",
    "curate_claims",
    "list_note_claims",
    "list_project_notes",
    # claim / examine
    "apply_examine_result",
    "apply_examine_verdict",
    "list_topic_claims_today",
    "list_project_claims",
    # project
    "create_project",
    "list_projects",
    "get_project",
    "update_project",
    "archive_project",
    "project_progress",
    # resume
    "upsert_resume",
    "get_resume",
    "apply_resume",
    # drill
    "list_drill_materials",
    "upsert_drill_material",
    "delete_drill_material",
    "create_drill_session",
    "append_drill_message",
    "finish_drill_session",
    "list_drill_sessions",
    "get_drill_session",
    # prompt
    "register_prompts",
    "get_active_prompt",
    "list_prompts",
    # memory
    "add_memory",
    "list_memory",
    "append_trajectory",
    "list_trajectory",
    "count_prior_failures",
    # shell / obs (OpenClaw bridge)
    "record_shell_event",
    "record_interest",
    "list_shell_activity",
    "build_profile_v0",
    "build_graph_v0",
    # harness
    "add_harness_run",
    "add_harness_case_result",
    "finalize_harness_run",
    "list_harness_runs",
    "list_harness_case_results",
    # identity
    "upsert_identity",
    "get_identity",
    "list_identities",
    "seed_default_identities",
    # thread / message / ball custody
    "create_thread",
    "list_threads",
    "get_thread",
    "update_thread_title",
    "touch_thread",
    "delete_thread",
    "derive_thread_title",
    "add_message",
    "count_user_messages",
    "list_messages",
    "get_ball",
    "set_ball",
    "clear_ball",
    # skills / connectors (profile center)
    "list_skill_catalog",
    "get_skill_detail",
    "resolve_skill_body",
    "install_skill",
    "update_skill_markdown",
    "set_skill_enabled",
    "delete_user_skill",
    "parse_skill_markdown",
    "list_connectors",
    "get_connector",
    "upsert_connector",
    "update_connector",
    "set_connector_status",
    "delete_connector",
    "import_connectors",
    "normalize_connector_config",
    "parse_mcp_servers_json",
]

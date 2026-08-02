"""MCP stdio entry — tools live in ``gotit.mcp.tools``."""

from __future__ import annotations

import anyio

from gotit.mcp import tools as _tools  # noqa: F401 — register tools
from gotit.mcp.app import mcp
from gotit.mcp.common import (  # noqa: F401 — re-export helpers
    _finalize_claim_mcp,
    _user_id,
    _verify_meta,
)
from gotit.mcp.tools.calibration import (
    gotit_calibration_answer,
    gotit_calibration_get,
    gotit_calibration_start,
    gotit_calibration_synthetic,
)
from gotit.mcp.tools.connectors import (
    gotit_delete_connector,
    gotit_import_connectors,
    gotit_list_connectors,
    gotit_upsert_connector,
)
from gotit.mcp.tools.day import (
    gotit_close_day,
    gotit_delete_plan_item,
    gotit_fill_today_from_queue,
    gotit_get_plan,
    gotit_today,
    gotit_update_plan_item,
    gotit_upsert_plan_item,
)
from gotit.mcp.tools.drill import (
    gotit_continue_drill_session,
    gotit_delete_drill_material,
    gotit_get_drill_session,
    gotit_list_drill_materials,
    gotit_list_drill_sessions,
    gotit_start_drill_session,
    gotit_upsert_drill_material,
)
from gotit.mcp.tools.examine import gotit_examine, gotit_ingest, gotit_start_verify
from gotit.mcp.tools.graph import (
    gotit_add_depends_on,
    gotit_list_depends_on,
    gotit_remove_depends_on,
)
from gotit.mcp.tools.health import gotit_health
from gotit.mcp.tools.interviews import (
    gotit_get_interview_ramp_prefs,
    gotit_list_due_interview_reminders,
    gotit_list_interview_ramp_nudges,
    gotit_list_interviews,
    gotit_list_upcoming_interviews,
    gotit_mark_interview_ramp_nudged,
    gotit_mark_interview_reminded,
    gotit_put_interview_ramp_prefs,
    gotit_update_interview_status,
    gotit_upsert_interview,
)
from gotit.mcp.tools.memory import (
    gotit_add_memory,
    gotit_list_memory,
    gotit_list_pending_failure_digests,
    gotit_mark_failure_digest_notified,
)
from gotit.mcp.tools.notes import (
    gotit_add_note,
    gotit_curate,
    gotit_delete_notes,
    gotit_ingest_note,
    gotit_list_all_notes,
    gotit_list_notes,
)
from gotit.mcp.tools.projects import (
    gotit_delete_project,
    gotit_get_project,
    gotit_list_projects,
    gotit_project_progress,
    gotit_update_project,
)
from gotit.mcp.tools.prompts import gotit_list_prompts, gotit_register_prompts
from gotit.mcp.tools.resume import gotit_apply_resume, gotit_get_resume, gotit_upload_resume
from gotit.mcp.tools.shell import (
    gotit_get_digest_prefs,
    gotit_list_shell_activity,
    gotit_obs_graph,
    gotit_obs_profile,
    gotit_promote_interest,
    gotit_put_digest_prefs,
    gotit_record_interest,
    gotit_record_shell_event,
    gotit_sync_digest_cron,
)
from gotit.mcp.tools.skills import (
    gotit_delete_skill,
    gotit_get_skill,
    gotit_install_skill,
    gotit_list_skills,
    gotit_set_skill_enabled,
    gotit_update_skill,
)
from gotit.mcp.tools.teach import gotit_teach
from gotit.mcp.tools.thread import (
    gotit_create_thread,
    gotit_delete_thread,
    gotit_list_messages,
    gotit_list_threads,
    gotit_post_message,
    gotit_seed_identities,
)

__all__ = [
    "mcp",
    "main",
    "gotit_health",
    "gotit_ingest",
    "gotit_examine",
    "gotit_start_verify",
    "gotit_today",
    "gotit_close_day",
    "gotit_get_plan",
    "gotit_upsert_plan_item",
    "gotit_fill_today_from_queue",
    "gotit_update_plan_item",
    "gotit_delete_plan_item",
    "gotit_list_notes",
    "gotit_list_all_notes",
    "gotit_add_note",
    "gotit_ingest_note",
    "gotit_delete_notes",
    "gotit_curate",
    "gotit_teach",
    "gotit_list_memory",
    "gotit_add_memory",
    "gotit_list_pending_failure_digests",
    "gotit_mark_failure_digest_notified",
    "gotit_record_shell_event",
    "gotit_record_interest",
    "gotit_promote_interest",
    "gotit_list_shell_activity",
    "gotit_get_digest_prefs",
    "gotit_put_digest_prefs",
    "gotit_sync_digest_cron",
    "gotit_obs_profile",
    "gotit_obs_graph",
    "gotit_add_depends_on",
    "gotit_remove_depends_on",
    "gotit_list_depends_on",
    "gotit_list_prompts",
    "gotit_register_prompts",
    "gotit_list_projects",
    "gotit_get_project",
    "gotit_update_project",
    "gotit_delete_project",
    "gotit_project_progress",
    "gotit_upload_resume",
    "gotit_apply_resume",
    "gotit_get_resume",
    "gotit_list_drill_materials",
    "gotit_upsert_drill_material",
    "gotit_delete_drill_material",
    "gotit_list_drill_sessions",
    "gotit_get_drill_session",
    "gotit_start_drill_session",
    "gotit_continue_drill_session",
    "gotit_list_interviews",
    "gotit_upsert_interview",
    "gotit_update_interview_status",
    "gotit_list_due_interview_reminders",
    "gotit_mark_interview_reminded",
    "gotit_list_upcoming_interviews",
    "gotit_list_interview_ramp_nudges",
    "gotit_mark_interview_ramp_nudged",
    "gotit_get_interview_ramp_prefs",
    "gotit_put_interview_ramp_prefs",
    "gotit_create_thread",
    "gotit_list_threads",
    "gotit_delete_thread",
    "gotit_list_messages",
    "gotit_post_message",
    "gotit_seed_identities",
    "gotit_list_skills",
    "gotit_get_skill",
    "gotit_install_skill",
    "gotit_update_skill",
    "gotit_set_skill_enabled",
    "gotit_delete_skill",
    "gotit_list_connectors",
    "gotit_upsert_connector",
    "gotit_import_connectors",
    "gotit_delete_connector",
    "gotit_calibration_start",
    "gotit_calibration_answer",
    "gotit_calibration_get",
    "gotit_calibration_synthetic",
]


def main() -> None:
    # stdio transport for local OpenClaw / MCP hosts
    anyio.run(mcp.run_stdio_async)


if __name__ == "__main__":
    main()

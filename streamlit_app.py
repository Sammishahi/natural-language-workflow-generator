"""Streamlit UI: requirement -> generate workflow -> validate -> execute -> approve/reject -> result."""
import json

import streamlit as st

from app.config import get_settings
from app.engine.validator import validate_workflow
from app.engine.workflow_engine import WorkflowEngine
from app.errors import LLMError, WorkflowError
from app.llm.workflow_generator import WorkflowGenerator
from app.models.run_state import Status
from app.models.workflow_schema import Workflow
from app.samples import SAMPLES
from app.tools.registry import build_default_registry
from app.utils.diagram import workflow_to_dot

st.set_page_config(page_title="Natural Language Workflow Generator", page_icon="🔀", layout="wide")

ICONS = {"COMPLETED": "✅", "FAILED": "❌", "REJECTED": "⛔", "SKIPPED": "⏭️",
         "WAITING_FOR_APPROVAL": "⏳", "RUNNING": "🔄", "PENDING": "⚪"}


@st.cache_resource
def get_registry():
    return build_default_registry()


registry = get_registry()
settings = get_settings()
engine = WorkflowEngine(registry)

for key, default in {"requirement": "", "workflow": None, "report": None, "raw_json": "",
                     "run": None, "gen_error": None, "sample_id": None}.items():
    st.session_state.setdefault(key, default)


def load_sample(sample_id: str) -> None:
    st.session_state.requirement = SAMPLES[sample_id]["requirement"]
    st.session_state.sample_id = sample_id


def on_decision(approved: bool) -> None:
    comment = st.session_state.get("approval_comment", "")
    try:
        engine.submit_approval(st.session_state.run, approved, comment)
    except WorkflowError as exc:
        st.session_state.gen_error = str(exc)


# ------------------------------------------------------------------ sidebar
with st.sidebar:
    st.header("Demo scenarios")
    for sid, sample in SAMPLES.items():
        st.button(sample["title"], key=f"load_{sid}", on_click=load_sample, args=(sid,), width="stretch")
    st.divider()
    st.subheader("LLM")
    st.caption(f"Model: `{settings.llm_model}`")
    has_key = bool(settings.llm_api_key)
    st.caption("API key: " + ("✅ found in .env" if has_key else "❌ missing (see .env.example)"))
    offline = st.checkbox("Offline mode: use the built-in sample workflow (no LLM call)", value=not has_key,
                          help="Only works for the demo scenarios. Real generation always uses the cloud LLM.")
    st.divider()
    st.subheader("Allowed tools")
    st.caption(", ".join(registry.names()))

st.title("🔀 Natural Language Workflow Generator")
st.caption("Requirement → Cloud LLM → JSON workflow → validation → controlled execution (with human approval).")

# ------------------------------------------------------------------ 1. requirement
st.subheader("1. Describe what you want to automate")
st.text_area("Requirement", key="requirement", height=100,
             placeholder="e.g. Check an order amount. If it is greater than ₹50,000, ask a manager to approve "
                         "before sending a confirmation email.")

if st.button("Generate Workflow", type="primary"):
    st.session_state.update(
        workflow=None,
        report=None,
        raw_json="",
        run=None,
        gen_error=None
    )

    try:
        with st.status("Generating and validating workflow...", expanded=True) as status:

            if offline:
                st.write("📋 Loading selected demo workflow...")
                sid = st.session_state.sample_id

                if not sid or SAMPLES[sid]["requirement"] != st.session_state.requirement:
                    raise LLMError(
                        "Offline mode only works with a demo scenario. "
                        "Click one in the sidebar, or add an API key to use the cloud LLM."
                    )

                st.write("🔍 Validating workflow schema...")
                wf = Workflow.model_validate(SAMPLES[sid]["workflow"])

                st.write("🔧 Checking tools and dependencies...")
                st.session_state.report = validate_workflow(wf, registry)
                st.session_state.workflow = st.session_state.report.workflow
                st.session_state.raw_json = json.dumps(
                    SAMPLES[sid]["workflow"],
                    indent=2,
                    ensure_ascii=False
                )

            else:
                st.write("🤖 Asking cloud LLM to design the workflow...")

                result = WorkflowGenerator(
                    registry, settings
                ).generate(st.session_state.requirement)

                st.write("🔍 Validating generated workflow...")

                st.session_state.workflow = result.workflow
                st.session_state.report = result.report
                st.session_state.raw_json = result.raw_json
                st.session_state.gen_error = result.error

            status.update(
                label="✅ Workflow generated and validated successfully",
                state="complete",
                expanded=False
            )

    except LLMError as exc:
        st.session_state.gen_error = str(exc)

# ------------------------------------------------------------------ 2. generated workflow
workflow = st.session_state.workflow
if workflow:
    report = st.session_state.report
    st.subheader("2. Generated workflow")
    st.success(f"Validation passed: schema OK, all tools registered, references and dependencies OK "
               f"({len(workflow.steps)} steps).")
    for warning in report.warnings:
        st.warning(warning)
    st.markdown(f"**{workflow.workflow_name}** — {workflow.description}")

    run = st.session_state.run
    statuses = {sid: rec.status.value for sid, rec in run.steps.items()} if run else None
    left, right = st.columns([1, 1])
    with left:
        st.dataframe([{"step": s.id, "type": s.type.value, "tool": s.tool or "-",
                       "depends_on": ", ".join(s.depends_on) or "-",
                       "error handling": s.on_error.strategy} for s in workflow.steps],
                     hide_index=True, width="stretch")
    with right:
        st.graphviz_chart(workflow_to_dot(workflow, statuses), width="stretch")
    with st.expander("Workflow JSON"):
        st.json(workflow.model_dump(mode="json", exclude_none=True))

    # -------------------------------------------------------------- 3. execution
    st.subheader("3. Execute")
    if st.button("Execute Workflow", type="primary"):
        try:
            st.session_state.run = engine.start(workflow)
            st.session_state.gen_error = None
        except WorkflowError as exc:
            st.session_state.gen_error = str(exc)
        st.rerun()

    run = st.session_state.run
    if run:
        icon = ICONS[run.state.value]
        st.markdown(f"### Status: {icon} `{run.state.value}`")

        if run.state == Status.WAITING_FOR_APPROVAL and run.pending_approval:
            with st.container(border=True):
                st.warning(f"**{run.pending_approval.approver_role.title()} approval required**\n\n"
                           f"{run.pending_approval.message}")
                st.text_input("Comment (optional)", key="approval_comment")
                c1, c2, _ = st.columns([1, 1, 4])
                c1.button("✅ APPROVE", type="primary", on_click=on_decision, args=(True,))
                c2.button("⛔ REJECT", on_click=on_decision, args=(False,))

        if run.state == Status.COMPLETED:
            st.success("Workflow completed successfully.")
        elif run.state == Status.FAILED:
            st.error(f"Workflow FAILED. {run.error}")
        elif run.state == Status.REJECTED:
            st.error(f"Workflow REJECTED. {run.error}")

        for item in run.displays:
            st.info(f"**{item['label']}:** {item['value']}")

        tab_steps, tab_logs, tab_data = st.tabs(["Step status", "Execution log", "Step outputs"])
        with tab_steps:
            st.dataframe([{"step": sid, "status": f"{ICONS[r.status.value]} {r.status.value}",
                           "attempts": r.attempts, "error": r.error or "", "note": r.note}
                          for sid, r in run.steps.items()], hide_index=True, width="stretch")
        with tab_logs:
            st.code("\n".join(f"{e.timestamp} {e.level:<7} [{e.step_id or '-'}] {e.message}" for e in run.logs),
                    language="text")
        with tab_data:
            st.json(json.loads(json.dumps(run.context, default=str)))

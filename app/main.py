"""Command-line runner (handy for quick checks without the UI).

Examples:
  python -m app.main --list
  python -m app.main --sample 2 --decision approve
  python -m app.main --prompt "Get customer C001 and display the email"     (uses the cloud LLM)
"""
import argparse
import json
import logging
import sys

from app.engine.workflow_engine import WorkflowEngine
from app.llm.workflow_generator import WorkflowGenerator
from app.models.run_state import Status
from app.models.workflow_schema import Workflow
from app.samples import SAMPLES
from app.tools.registry import build_default_registry


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Natural Language Workflow Generator (CLI)")
    parser.add_argument("--list", action="store_true", help="list demo scenarios")
    parser.add_argument("--sample", choices=sorted(SAMPLES), help="run a built-in sample workflow (no LLM)")
    parser.add_argument("--prompt", help="natural-language requirement (uses the cloud LLM)")
    parser.add_argument("--decision", choices=["ask", "approve", "reject"], default="ask",
                        help="what to do when human approval is required")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.WARNING)

    if args.list:
        for key, sample in SAMPLES.items():
            print(f"{key}: {sample['title']}\n   {sample['requirement']}")
        return 0

    registry = build_default_registry()
    if args.sample:
        workflow = Workflow.model_validate(SAMPLES[args.sample]["workflow"])
    elif args.prompt:
        result = WorkflowGenerator(registry).generate(args.prompt)
        if result.workflow is None:
            print("Generation failed:", result.error)
            return 1
        workflow = result.workflow
    else:
        parser.print_help()
        return 1

    print("WORKFLOW JSON:\n" + json.dumps(workflow.model_dump(mode="json", exclude_none=True), indent=2, ensure_ascii=False))
    engine = WorkflowEngine(registry)
    run = engine.start(workflow)
    while run.state == Status.WAITING_FOR_APPROVAL:
        print("\nAPPROVAL REQUIRED:", run.pending_approval.message)
        choice = args.decision if args.decision != "ask" else input("Approve? [y/n]: ").strip().lower()
        approved = choice in ("approve", "y", "yes")
        run = engine.submit_approval(run, approved, "CLI decision")

    print("\nLOGS")
    for entry in run.logs:
        print(f"  {entry.timestamp} {entry.level:<7} [{entry.step_id or '-'}] {entry.message}")
    print(f"\nFINAL STATE: {run.state.value}")
    if run.error:
        print("ERROR:", run.error)
    for item in run.displays:
        print(f"RESULT  {item['label']}: {item['value']}")
    return 0 if run.state == Status.COMPLETED else 2


if __name__ == "__main__":
    sys.exit(main())

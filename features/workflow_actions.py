from __future__ import annotations

from dataclasses import dataclass

from .app_actions import open_app
from .file_actions import open_file_or_folder
from .web_actions import open_website


@dataclass(slots=True)
class WorkflowStep:
    kind: str
    target: str


WORKFLOW_MODES: dict[str, list[WorkflowStep]] = {
    'study': [
        WorkflowStep('app', 'brave'),
        WorkflowStep('app', 'notion'),
        WorkflowStep('folder', 'documents'),
    ],
    'editing': [
        WorkflowStep('app', 'photoshop'),
        WorkflowStep('folder', 'downloads'),
        WorkflowStep('app', 'spotify'),
    ],
    'gaming': [
        WorkflowStep('app', 'steam'),
        WorkflowStep('app', 'discord'),
    ],
    'work': [
        WorkflowStep('app', 'vs code'),
        WorkflowStep('app', 'brave'),
        WorkflowStep('folder', 'documents'),
    ],
}


def run_workflow_mode(mode_name: str) -> tuple[bool, str]:
    normalized_mode = mode_name.strip().lower().replace(' mode', '')
    steps = WORKFLOW_MODES.get(normalized_mode)
    if not steps:
        return False, f"I do not know a workflow mode named {mode_name} yet."

    opened: list[str] = []
    failed: list[str] = []

    for step in steps:
        success, _message = run_step(step)
        label = step.target.title()
        if success:
            opened.append(label)
        else:
            failed.append(label)

    if opened and not failed:
        return True, f"Starting {normalized_mode} mode with {', '.join(opened)}."
    if opened:
        return True, f"Starting {normalized_mode} mode. I opened {', '.join(opened)}, but could not open {', '.join(failed)}."
    return False, f"I tried to start {normalized_mode} mode, but nothing opened."


def run_step(step: WorkflowStep) -> tuple[bool, str]:
    if step.kind == 'app':
        return open_app(step.target)
    if step.kind == 'folder':
        return open_file_or_folder(step.target)
    if step.kind == 'website':
        return open_website(step.target)
    return False, f'Unsupported workflow step type: {step.kind}'

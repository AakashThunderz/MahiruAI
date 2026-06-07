from __future__ import annotations

from dataclasses import dataclass

from .app_actions import get_resolved_app_command, open_app
from .file_actions import open_file_or_folder
from .media_actions import play_media
from .resolver import ActionRequest, classify_user_request
from .system_actions import perform_system_action
from .web_actions import open_top_search_result, open_website
from .workflow_actions import run_workflow_mode
from .window_actions import control_application_window


@dataclass(slots=True)
class ActionResult:
    handled: bool
    success: bool
    message: str | None = None


def handle_action_request(command: str) -> ActionResult:
    request = classify_user_request(command)
    if request is None:
        return ActionResult(handled=False, success=False)

    if request.kind == "app":
        success, message = open_app(request.target)
        return ActionResult(handled=True, success=success, message=message)

    if request.kind == "app_control":
        success, message = control_application_window(
            request.target,
            request.action or "close",
            get_resolved_app_command(request.target),
        )
        return ActionResult(handled=True, success=success, message=message)

    if request.kind == "system_control":
        success, message = perform_system_action(request.action or "", target=request.target)
        return ActionResult(handled=True, success=success, message=message)

    if request.kind == "workflow_mode":
        success, message = run_workflow_mode(request.target)
        return ActionResult(handled=True, success=success, message=message)

    if request.kind == "file":
        success, message = open_file_or_folder(request.target)
        return ActionResult(handled=True, success=success, message=message)

    if request.kind == "media":
        success, message = play_media(request.target, request.media_type, request.platform)
        return ActionResult(handled=True, success=success, message=message)

    if request.kind == "website":
        success, message = handle_website_request(request)
        return ActionResult(handled=True, success=success, message=message)

    return ActionResult(handled=False, success=False)


def handle_website_request(request: ActionRequest) -> tuple[bool, str]:
    target = request.target.strip()
    if not target:
        return False, "I need a website name to open."

    if "." in target and " " not in target:
        return open_website(target)

    return open_top_search_result(target)

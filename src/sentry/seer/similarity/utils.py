import logging
from typing import Any

from sentry.utils.safe import get_path

logger = logging.getLogger(__name__)

MAX_FRAME_COUNT = 50


def _get_value_if_exists(exception_value: dict[str, Any]) -> str:
    return exception_value["values"][0] if exception_value.get("values") else ""


def get_stacktrace_string(data: dict[str, Any]) -> str:
    """Format a stacktrace string from the grouping information."""
    if not (
        get_path(data, "app", "hash") and get_path(data, "app", "component", "values")
    ) and not (
        get_path(data, "system", "hash") and get_path(data, "system", "component", "values")
    ):
        return ""

    # Get the data used for grouping
    if get_path(data, "app", "hash"):
        exceptions = data["app"]["component"]["values"]
    else:
        exceptions = data["system"]["component"]["values"]

    # Handle chained exceptions
    if exceptions and exceptions[0].get("id") == "chained-exception":
        exceptions = exceptions[0].get("values")

    frame_count = 0
    stacktrace_str = ""
    for exception in reversed(exceptions):
        if exception.get("id") not in ["exception", "threads"] or not exception.get("contributes"):
            continue

        # For each exception, extract its type, value, and up to 50 stacktrace frames
        exc_type, exc_value, frame_str = "", "", ""
        for exception_value in exception.get("values", []):
            if exception_value.get("id") == "type":
                exc_type = _get_value_if_exists(exception_value)
            elif exception_value.get("id") == "value":
                exc_value = _get_value_if_exists(exception_value)
            elif exception_value.get("id") == "stacktrace" and frame_count < MAX_FRAME_COUNT:
                contributing_frames = [
                    frame
                    for frame in exception_value["values"]
                    if frame.get("id") == "frame" and frame.get("contributes")
                ]
                num_frames = len(contributing_frames)
                if frame_count + num_frames > MAX_FRAME_COUNT:
                    remaining_frame_count = MAX_FRAME_COUNT - frame_count
                    contributing_frames = contributing_frames[-remaining_frame_count:]
                    num_frames = remaining_frame_count
                frame_count += num_frames

                for frame in contributing_frames:
                    frame_dict = {"filename": "", "function": "", "context-line": ""}
                    for frame_values in frame.get("values", []):
                        if frame_values.get("id") in frame_dict:
                            frame_dict[frame_values["id"]] = _get_value_if_exists(frame_values)

                    frame_str += f'  File "{frame_dict["filename"]}", function {frame_dict["function"]}\n    {frame_dict["context-line"]}\n'

        # Only exceptions have the type and value properties, so we don't need to handle the threads
        # case here
        if exception.get("id") == "exception":
            stacktrace_str += f"{exc_type}: {exc_value}\n"
        if frame_str:
            stacktrace_str += frame_str

    return stacktrace_str.strip()

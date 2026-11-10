"""Public operations shared by tools, the loose REST module and cron scripts."""
from . import db, errors, projects, records, grants, sessions, logs, limits, migrations, bridge
from .errors import SpacesError
from .projects import (create_space, resolve_space, list_spaces, get_space, read_file,
                       list_files, write_files, edit_file, list_revisions,
                       restore_revision, bundle, set_status, delete_space,
                       touch_opened, set_pinned)
from .records import query, batch, changes_since
from .grants import list_grants, decide, audit_log
from .sessions import open_session, close_session, require
from .logs import read_logs
from .bridge import dispatch
_UPKEEP_EXPORTS = {
    "list_runs": "runs", "start_refresh": "runs",
    "get_schedule": "schedules", "request_schedule": "schedules",
    "decide_schedule": "schedules", "pause_schedule": "schedules",
}


def __getattr__(name):
    from importlib import import_module

    if name not in _UPKEEP_EXPORTS:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    value = getattr(import_module(f".{_UPKEEP_EXPORTS[name]}", __name__), name)
    globals()[name] = value
    return value

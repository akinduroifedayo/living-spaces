import re

_SPACE_ID = re.compile(r"[a-z0-9][a-z0-9-]{1,47}\Z")


def register_desktop_rpc(ctx, load_core):
    def close_session(params, *, session_id, **kwargs):
        core = load_core()
        try:
            if (not isinstance(params, dict) or set(params) != {"space_id", "session"}
                    or not isinstance(params["space_id"], str)
                    or not _SPACE_ID.fullmatch(params["space_id"])
                    or not isinstance(params["session"], str) or not params["session"]):
                raise core.SpacesError("invalid", "Expected space_id and session only.")
            core.require(params["space_id"], params["session"])
            return core.close_session(params["session"])
        except core.SpacesError as error:
            if error.code == "session_invalid":
                return {"closed": True}
            return {"error": error.to_dict()}

    return ctx.register_rpc("close_session", close_session)

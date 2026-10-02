"""Sign-in boundary for the shared maintainer dashboard."""

import hashlib

import streamlit as st

from evalforge.access import access_key_matches, validate_access_configuration
from evalforge.config import Settings


def require_dashboard_access(settings: Settings) -> None:
    try:
        validate_access_configuration(settings)
    except ValueError:
        st.error("Dashboard access is not configured. Contact the deployment administrator.")
        st.stop()

    access_key = settings.access_key.get_secret_value() if settings.access_key else ""
    if not access_key.strip():
        return

    fingerprint = hashlib.sha256(access_key.encode("utf-8")).hexdigest()
    if st.session_state.get("_access_fingerprint") == fingerprint:
        st.sidebar.button("Sign out", on_click=st.session_state.clear)
        return

    def sign_in():
        submitted = st.session_state.pop("_access_key_input", "")
        if access_key_matches(submitted, settings):
            st.session_state["_access_fingerprint"] = fingerprint
            st.session_state.pop("_access_error", None)
        else:
            st.session_state["_access_error"] = True

    st.title("Sign in to EvalForge")
    st.caption("Enter the access key provided by your deployment administrator.")
    with st.form("access_sign_in"):
        st.text_input("Access key", type="password", key="_access_key_input")
        st.form_submit_button("Sign in", on_click=sign_in)
    if st.session_state.get("_access_error"):
        st.error("The access key is not valid.")
    st.stop()

"""
Job Pal auth — Supabase email/password + OTP magic link.
Session is stored in st.session_state["jp_auth"] to survive Streamlit reruns.
"""
import streamlit as st
from supabase import create_client
from config import SUPABASE_URL, SUPABASE_KEY


def _sb():
    return create_client(SUPABASE_URL, SUPABASE_KEY)


def get_user_id() -> str | None:
    return (st.session_state.get("jp_auth") or {}).get("user_id")


def get_user_email() -> str | None:
    return (st.session_state.get("jp_auth") or {}).get("email")


def is_logged_in() -> bool:
    return bool(get_user_id())


def _store_session(user, access_token: str):
    st.session_state["jp_auth"] = {
        "user_id": user.id,
        "email": user.email,
        "access_token": access_token,
    }


def sign_out():
    try:
        _sb().auth.sign_out()
    except Exception:
        pass
    for key in ("jp_auth", "resume_text", "session_uid", "target_roles",
                "min_salary", "_session_restored", "_user_session_restored_for",
                "otp_sent", "otp_pending_email", "_suggested_roles",
                "ev_manual_cities"):
        st.session_state.pop(key, None)


def restore_user_session():
    """After login, restore the user's saved resume from Supabase.

    Runs once per login (keyed to the current user_id) so a new login
    always reloads from the correct account — prevents stale resume leak
    across users on shared Streamlit instances.
    """
    if not is_logged_in():
        return
    user_id = get_user_id()
    restored_for = st.session_state.get("_user_session_restored_for")
    if restored_for == user_id:
        return  # already restored for this specific user
    st.session_state["_user_session_restored_for"] = user_id
    # Clear any resume left by a previous user before loading new one
    for key in ("resume_text", "session_uid", "target_roles", "min_salary", "ev_manual_cities"):
        st.session_state.pop(key, None)
    try:
        from sessions import load_session
        data = load_session(user_id)
        if data and data.get("resume_text"):
            st.session_state["resume_text"] = data["resume_text"]
            st.session_state["session_uid"] = user_id
            if data.get("target_roles"):
                st.session_state["target_roles"] = data["target_roles"]
    except Exception:
        pass


def render_auth_wall():
    """
    Show login/signup UI and call st.stop() until authenticated.
    Place this immediately after the CSS block in ui_v2.py.
    """
    if is_logged_in():
        return

    # Minimal sidebar while logged out
    with st.sidebar:
        st.markdown("""
        <div class="tt-logo">
          <span class="bracket">[</span>techturi<span class="dot">.</span><span class="bracket">]</span>
        </div>
        <div class="tt-product">Job Pal</div>
        """, unsafe_allow_html=True)

    st.markdown("""
    <div style="max-width:440px;margin:72px auto 0;padding:0 16px">
      <div style="font-family:'JetBrains Mono',monospace;font-size:10px;color:#D4FF3A;
                  letter-spacing:0.25em;text-transform:uppercase;margin-bottom:10px">
        techturi · Job Pal
      </div>
      <div style="font-family:'Fraunces',serif;font-size:42px;font-weight:300;color:#F5F4EE;
                  letter-spacing:-0.03em;line-height:1.1;margin-bottom:40px">
        Your AI <em style="color:#D4FF3A;font-style:italic">job search</em><br>engine.
      </div>
    </div>
    """, unsafe_allow_html=True)

    # Constrain form width
    _, col, _ = st.columns([1, 2, 1])
    with col:
        tab_login, tab_signup, tab_otp = st.tabs(["Sign In", "Create Account", "Magic Link"])

        # ── Email / Password login ────────────────────────────────
        with tab_login:
            with st.form("login_form"):
                email = st.text_input("Email", placeholder="you@example.com")
                password = st.text_input("Password", type="password")
                submitted = st.form_submit_button(
                    "Sign In", type="primary", use_container_width=True
                )
            if submitted:
                if not email or not password:
                    st.error("Email and password required.")
                else:
                    try:
                        resp = _sb().auth.sign_in_with_password(
                            {"email": email, "password": password}
                        )
                        _store_session(resp.user, resp.session.access_token)
                        st.rerun()
                    except Exception as e:
                        st.error(f"Sign in failed: {e}")

        # ── Sign up ───────────────────────────────────────────────
        with tab_signup:
            with st.form("signup_form"):
                email_s = st.text_input("Email", placeholder="you@example.com", key="su_email")
                pw_s = st.text_input("Password", type="password", key="su_pw",
                                     help="At least 8 characters")
                pw_s2 = st.text_input("Confirm password", type="password", key="su_pw2")
                submitted_s = st.form_submit_button(
                    "Create Account", type="primary", use_container_width=True
                )
            if submitted_s:
                if not email_s or not pw_s:
                    st.error("Email and password required.")
                elif pw_s != pw_s2:
                    st.error("Passwords don't match.")
                elif len(pw_s) < 8:
                    st.error("Password must be at least 8 characters.")
                else:
                    try:
                        resp = _sb().auth.sign_up({"email": email_s, "password": pw_s})
                        if resp.user and resp.session:
                            _store_session(resp.user, resp.session.access_token)
                            st.rerun()
                        elif resp.user:
                            st.success(
                                "✓ Account created — check your email to confirm, then sign in. "
                                "(You can also disable email confirmation in Supabase > Auth > Settings.)"
                            )
                        else:
                            st.error("Sign up failed — try signing in if you already have an account.")
                    except Exception as e:
                        st.error(f"Sign up failed: {e}")

        # ── Magic link / OTP ──────────────────────────────────────
        with tab_otp:
            st.caption("Enter your email — we'll send a one-time code. No password needed.")
            if not st.session_state.get("otp_sent"):
                with st.form("otp_send_form"):
                    otp_email = st.text_input("Email", placeholder="you@example.com")
                    send_btn = st.form_submit_button("Send Code", use_container_width=True)
                if send_btn:
                    if not otp_email:
                        st.error("Email required.")
                    else:
                        try:
                            _sb().auth.sign_in_with_otp({
                                "email": otp_email,
                                "options": {"should_create_user": True},
                            })
                            st.session_state["otp_pending_email"] = otp_email
                            st.session_state["otp_sent"] = True
                            st.rerun()
                        except Exception as e:
                            st.error(f"Could not send code: {e}")
            else:
                pending = st.session_state.get("otp_pending_email", "")
                st.info(f"Code sent to **{pending}** — check your inbox (and spam).")
                with st.form("otp_verify_form"):
                    code = st.text_input("6-digit code", placeholder="123456", max_chars=6)
                    verify_btn = st.form_submit_button(
                        "Verify", type="primary", use_container_width=True
                    )
                if verify_btn:
                    try:
                        resp = _sb().auth.verify_otp({
                            "email": pending,
                            "token": code.strip(),
                            "type": "email",
                        })
                        _store_session(resp.user, resp.session.access_token)
                        st.session_state.pop("otp_sent", None)
                        st.session_state.pop("otp_pending_email", None)
                        st.rerun()
                    except Exception as e:
                        st.error(f"Verification failed — check the code and try again. ({e})")
                if st.button("Use a different email", key="otp_reset"):
                    st.session_state.pop("otp_sent", None)
                    st.session_state.pop("otp_pending_email", None)
                    st.rerun()

    st.stop()

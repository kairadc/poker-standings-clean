import gspread
import os
import json

import streamlit as st
from google.oauth2 import service_account

# Set page config as the first Streamlit call.
st.set_page_config(
    page_title="Friends Poker Standings",
    page_icon="🃏",
    layout="wide",
)

from src import data, ui

# Debug visibility for secrets in runtime (safe, key names only)
st.write("Secrets keys:", list(st.secrets.keys()))
st.write("Has SHEET_ID:", "SHEET_ID" in st.secrets)
st.write("Has gcp_service_account:", "gcp_service_account" in st.secrets)

# Load service account from any supported key to avoid KeyErrors in cloud/local.
raw_service_account = (
    st.secrets.get("gcp_service_account")
    or st.secrets.get("gcp_service_account_json")
    or st.secrets.get("GCP_SERVICE_ACCOUNT_JSON")
    or st.secrets.get("service_account")
    or st.secrets.get("service_account_json")
    or os.environ.get("gcp_service_account")
    or os.environ.get("gcp_service_account_json")
    or os.environ.get("GCP_SERVICE_ACCOUNT_JSON")
    or os.environ.get("service_account")
    or os.environ.get("service_account_json")
)

if raw_service_account is None and "sheets" in st.secrets:
    cfg = st.secrets["sheets"]
    raw_service_account = cfg.get("service_account") or cfg.get("service_account_json")

if raw_service_account is None:
    raise KeyError("Service account details not found in secrets.")

if isinstance(raw_service_account, str):
    try:
        service_account_info = json.loads(raw_service_account)
    except json.JSONDecodeError:
        # Handle pretty-printed or already-escaped JSON strings
        service_account_info = json.loads(raw_service_account.replace("\n", "\\n"))
else:
    service_account_info = dict(raw_service_account)

private_key = service_account_info.get("private_key")
if not private_key:
    raise ValueError("private_key missing in gcp_service_account secret.")
# Normalize PEM formatting: strip outer quotes, fix escaped newlines, and normalize line breaks.
normalized_pk = str(private_key).strip()
if (normalized_pk.startswith('"') and normalized_pk.endswith('"')) or (
    normalized_pk.startswith("'") and normalized_pk.endswith("'")
):
    normalized_pk = normalized_pk[1:-1].strip()
# Handle double-escaped \n first, then single-escaped, then CRLF/CR.
normalized_pk = normalized_pk.replace("\\\\n", "\\n")
normalized_pk = normalized_pk.replace("\\n", "\n").replace("\r\n", "\n").replace("\r", "\n")
# If header/footer are present but body is still single-line, insert newlines.
if "-----BEGIN PRIVATE KEY-----" in normalized_pk and "-----END PRIVATE KEY-----" in normalized_pk:
    if "-----BEGIN PRIVATE KEY-----\n" not in normalized_pk:
        normalized_pk = normalized_pk.replace("-----BEGIN PRIVATE KEY-----", "-----BEGIN PRIVATE KEY-----\n", 1)
    if "\n-----END PRIVATE KEY-----" not in normalized_pk:
        normalized_pk = normalized_pk.replace("-----END PRIVATE KEY-----", "\n-----END PRIVATE KEY-----", 1)
service_account_info["private_key"] = normalized_pk
if "BEGIN PRIVATE KEY" not in normalized_pk or "END PRIVATE KEY" not in normalized_pk:
    raise ValueError("private_key format looks invalid after normalization; confirm secrets TOML.")

creds = service_account.Credentials.from_service_account_info(
    service_account_info,
    scopes=["https://www.googleapis.com/auth/spreadsheets"],
)

gc = gspread.authorize(creds)
sheet_id = (
    st.secrets.get("SHEET_ID")
    or st.secrets.get("spreadsheet_id")
    or (st.secrets.get("sheets", {}).get("spreadsheet_id") if "sheets" in st.secrets else None)
    or os.environ.get("SHEET_ID")
    or os.environ.get("spreadsheet_id")
)
ws_name = (
    st.secrets.get("WORKSHEET_NAME")
    or st.secrets.get("worksheet_name")
    or (st.secrets.get("sheets", {}).get("worksheet_name") if "sheets" in st.secrets else None)
    or os.environ.get("WORKSHEET_NAME")
    or os.environ.get("worksheet_name")
    or "sessions"
)

# Store shared clients/ids for other pages
st.session_state["gc"] = gc
st.session_state["sheet_id"] = sheet_id
st.session_state["worksheet_name"] = ws_name

# Optional redirect to Overview; disable with ?no_redirect=1 for diagnostics
params = st.query_params
if "no_redirect" not in params:
    pass  # Keep the root page accessible; navigation is available in the sidebar

ui.apply_centered_layout()

st.title("Friends Poker Standings")
st.markdown(
    '<div class="arcade-marquee"><span>🎮 SEASON MODE • 🏆 LEADERBOARD LIVE • 💰 ENTER RESULTS TO UPDATE •</span></div>',
    unsafe_allow_html=True,
)
st.caption("Track group results with Google Sheets as the single source of truth.")

# Load data once; downstream pages will reuse cached data.
df, dq = data.load_dataset(gc=gc, sheet_id=sheet_id, worksheet_name=ws_name)
ui.show_mode_banner(dq)
ui.render_refresh_button()

st.write(
    "Use the sidebar to switch between Overview, Player Profile, Session History, and Data Setup Help. "
    "New rows can be added directly in Google Sheets from your phone."
)

if dq.issues:
    with st.expander("Data load notes"):
        for issue in dq.issues:
            st.warning(issue)

if df.empty:
    st.info("No data yet. Visit Data Setup Help to connect your Google Sheet or start with the sample template.")
else:
    st.success("Data loaded. Jump to Overview for KPIs, charts, and standings.")

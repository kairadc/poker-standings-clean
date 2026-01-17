import gspread
import json

import streamlit as st
from google.oauth2 import service_account

from src import data, ui

raw_service_account = st.secrets["gcp_service_account"]
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
normalized_pk = private_key.strip()
if (normalized_pk.startswith('"') and normalized_pk.endswith('"')) or (
    normalized_pk.startswith("'") and normalized_pk.endswith("'")
):
    normalized_pk = normalized_pk[1:-1].strip()
normalized_pk = normalized_pk.replace("\\n", "\n").replace("\r\n", "\n").replace("\r", "\n")
service_account_info["private_key"] = normalized_pk
if "BEGIN PRIVATE KEY" not in normalized_pk or "END PRIVATE KEY" not in normalized_pk:
    raise ValueError("private_key format looks invalid after normalization; confirm secrets TOML.")

creds = service_account.Credentials.from_service_account_info(
    service_account_info,
    scopes=["https://www.googleapis.com/auth/spreadsheets"],
)

gc = gspread.authorize(creds)
sheet_id = st.secrets.get("SHEET_ID")
ws_name = st.secrets.get("WORKSHEET_NAME", "sessions")

st.set_page_config(
    page_title="Friends Poker Standings",
    page_icon="🃏",
    layout="wide",
)

# Redirect root to Overview so it's the landing experience
try:
    st.switch_page("pages/1_Overview.py")
except Exception:
    pass

ui.apply_centered_layout()

st.title("Friends Poker Standings")
st.markdown(
    '<div class="arcade-marquee"><span>🎮 SEASON MODE • 🏆 LEADERBOARD LIVE • 💰 ENTER RESULTS TO UPDATE •</span></div>',
    unsafe_allow_html=True,
)
st.caption("Track group results with Google Sheets as the single source of truth.")

# Load data once; downstream pages will reuse cached data.
df, dq = data.load_dataset()
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

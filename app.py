from collections import defaultdict
import pandas as pd
import requests
import streamlit as st

st.set_page_config(page_title="Dynasty Tracker", page_icon="🏈", layout="wide")

st.title("🏈 Standings & Max PF Tracker")
st.markdown("Live Sleeper standings with traded pick tracking.")

league_id = st.sidebar.text_input("League ID:", "1314874337139904512")


@st.cache_data(ttl=30)
def fetch_league_data(lid):
  u_league = "https://api.sleeper.app/v1/league/" + lid
  res_l = requests.get(u_league)
  if res_l.status_code != 200 or not res_l.json():
    return None, "Invalid League ID."

  league_data = res_l.json()

  res_n = requests.get("https://api.sleeper.app/v1/state/nfl")
  if res_n.status_code == 200:
    nfl_state = res_n.json()
  else:
    nfl_state = {"week": 1, "season": "2026"}

  current_week = nfl_state.get("week", 1)
  playoff_start = league_data.get("settings", {}).get("playoff_week_start", 15)
  season = str(league_data.get("season", "2026"))

  if playoff_start and playoff_start > 1:
    regular_weeks = playoff_start - 1
  else:
    regular_weeks = max(1, min(current_week, 14))

  roster_pos = league_data.get("roster_positions", [])
  starters = [p for p in roster_pos if p not in ["BN", "IR", "TAXI"]]
  num_starters = len(starters)

  res_u = requests.get("https://api.sleeper.app/v1/league/" + lid + "/users")
  users = res_u.json() if res_u.status_code == 200 else []

  user_names = {}
  for u in users:
    uid = u.get("user_id")
    uname = u.get("display_name", u.get("username", "Unknown"))

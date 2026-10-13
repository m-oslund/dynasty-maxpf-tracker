from collections import defaultdict
import pandas as pd
import requests
import streamlit as st

st.set_page_config(
    page_title="Dynasty League Standings & Picks", page_icon="🏈", layout="wide"
)

st.title("🏈 League Standings, Max PF & Draft Board")
st.markdown(
    "Live standings dynamically fetched from the Sleeper API. Includes live"
    " traded pick tracking."
)

league_id = st.sidebar.text_input("Sleeper League ID:", "1314874337139904512")


@st.cache_data(ttl=30)
def fetch_league_data(lid):
  # 1. Fetch League & NFL State
  league_res = requests.get(f"https://api.sleeper.app/v1/league/{lid}")
  if league_res.status_code != 200 or not league_res.json():
    return None, "League not found or invalid League ID."

  league_data = league_res.json()

  nfl_state_res = requests.get("https://api.sleeper.app/v1/state/nfl")
  nfl_state = (
      nfl_state_res.json()
      if nfl_state_res.status_code == 200
      else {"week": 6, "season": "2026"}
  )

  current_week = nfl_state.get("week", 6)
  playoff_start = league_data.get("settings", {}).get("playoff_week_start", 15)
  season = str(league_data.get("season", "2026"))

  regular_season_weeks = (
      playoff_start - 1
      if (playoff_start and playoff_start > 1)
      else max(1, min(current_week, 14))
  )

  starter_positions = [
      p
      for p in league_data.get("roster_positions", [])
      if p not in ["BN", "IR", "TAXI"]
  ]
  num_starters = len(starter_positions)

  # 2. Users & Rosters
  users_res = requests.get(f"https://api.sleeper.app/v1/league/{lid}/users")
  users = users_res.json() if users_res.status_code == 200 else []
  user_names = {
      u["user_id"]: u.get("display_name", u.get("username", "Unknown"))
      for u in users
  }

  rosters_res = requests.get(

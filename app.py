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


@st.cache_data(ttl=30)  # Updates every 30 seconds
def fetch_league_data(lid):
  # 1. Fetch League & NFL State
  league_res = requests.get(f"https://api.sleeper.app/v1/league/{lid}")
  if league_res.status_code != 200 or not league_res.json():
    return None, "League not found."

  league_data = league_res.json()
  nfl_state = requests.get("https://api.sleeper.app/v1/state/nfl").json()

  current_week = nfl_state.get("week", 1)
  playoff_start = league_data.get("settings", {}).get("playoff_week_start", 15)
  season = league_data.get("season", "2026")

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
  users = requests.get(f"https://api.sleeper.app/v1/league/{lid}/users").json()
  user_names = {
      u["user_id"]: u.get("display_name", u.get("username", "Unknown"))
      for u in users
  }

  rosters = requests.get(
      f"https://api.sleeper.app/v1/league/{lid}/rosters"
  ).json()
  roster_to_owner = {
      r["roster_id"]: user_names.get(r.get("owner_id"), f"Team {r['roster_id']}")
      for r in rosters
  }

  total_bench_pf = defaultdict(float)
  max_pf = defaultdict(float)

  # 3. Calculate Scores
  for week in range(1, regular_season_weeks + 1):
    res = requests.get(
        f"https://api.sleeper.app/v1/league/{lid}/matchups/{week}"
    )
    if res.status_code != 200 or not res.json():
      continue

    for team in res.json():
      rid = team.get("roster_id")
      pts = team.get("players_points", {})
      if rid and pts:
        total_bench_pf[rid] += sum(pts.values())
        sorted_scores = sorted(pts.values(), reverse=True)
        max_pf[rid] += sum(sorted_scores[:num_starters])

  # 4. Fetch Traded Picks
  traded_picks_res = requests.get(
      f"https://api.sleeper.app/v1/league/{lid}/traded_picks"
  )
  traded_picks = (
      traded_picks_res.json() if traded_picks_res.status_code == 200 else []
  )

  # Map original roster_id to current owner display_name for 1st-round picks
  current_pick_owners = {}
  for rid in roster_to_owner:
    current_pick_owners[rid] = roster_to_owner[rid]

  next_season = str(int(season) + 1)
  for tp in traded_picks:
    if str(tp.get("season")) == next_season and tp.get("

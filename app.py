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
  league_url = f"https://api.sleeper.app/v1/league/{lid}"
  league_res = requests.get(league_url)
  if league_res.status_code != 200 or not league_res.json():
    return None, "League not found or invalid League ID."

  league_data = league_res.json()

  nfl_res = requests.get("https://api.sleeper.app/v1/state/nfl")
  nfl_state = (
      nfl_res.json()
      if nfl_res.status_code == 200
      else {"week": 6, "season": "2026"}
  )

  current_week = nfl_state.get("week", 6)
  playoff_start = league_data.get("settings", {}).get("playoff_week_start", 15)
  season = str(league_data.get("season", "2026"))

  if playoff_start and playoff_start > 1:
    regular_season_weeks = playoff_start - 1
  else:
    regular_season_weeks = max(1, min(current_week, 14))

  roster_pos = league_data.get("roster_positions", [])
  starter_positions = [p for p in roster_pos if p not in ["BN", "IR", "TAXI"]]
  num_starters = len(starter_positions)

  users_url = f"https://api.sleeper.app/v1/league/{lid}/users"
  users_res = requests.get(users_url)
  users = users_res.json() if users_res.status_code == 200 else []
  user_names = {
      u["user_id"]: u.get("display_name", u.get("username", "Unknown"))
      for u in users
  }

  rosters_url = f"https://api.sleeper.app/v1/league/{lid}/rosters"
  rosters_res = requests.get(rosters_url)
  rosters = rosters_res.json() if rosters_res.status_code == 200 else []

  roster_to_owner = {}
  for r in rosters:
    rid = r.get("roster_id")
    oid = r.get("owner_id")
    roster_to_owner[rid] = user_names.get(oid, f"Team {rid}")

  total_bench_pf = defaultdict(float)
  max_pf = defaultdict(float)

  for week in range(1, regular_season_weeks + 1):
    m_url = f"https://api.sleeper.app/v1/league/{lid}/matchups/{week}"
    res = requests.get(m_url)
    if res.status_code != 200 or not res.json():
      continue

    for team in res.json():
      rid = team.get("roster_id")
      pts = team.get("players_points", {})
      if rid and pts:
        total_bench_pf[rid] += sum(pts.values())
        sorted_scores = sorted(pts.values(), reverse=True)
        max_pf[rid] += sum(sorted_scores[:num_starters])

  current_pick_owners = {
      rid: owner_name for rid, owner_name in roster_to_owner.items()
  }

  try:
    tp_url = f"https://api.sleeper.app/v1/league/{lid}/traded_picks"
    tp_res = requests.get(tp_url)
    if tp_res.status_code == 200 and isinstance(tp_res.json(), list):
      next_season = str(int(season) + 1)
      for tp in tp_res.json():
        tp_s = str(tp.get("season"))
        tp_r = tp.get("round")
        orig_rid = tp.get("roster_id")
        if (
            tp_s == next_season
            and tp_r == 1

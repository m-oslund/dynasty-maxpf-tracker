from collections import defaultdict
import pandas as pd
import requests
import streamlit as st

st.set_page_config(
    page_title="Dynasty League Standings & Picks", page_icon="🏈", layout="wide"
)

st.title("🏈 League Standings, Max PF & Draft Board")
st.markdown(
    "Live standings dynamically fetched from the Sleeper API with live traded"
    " pick tracking."
)

league_id = st.sidebar.text_input("Sleeper League ID:", "1314874337139904512")


@st.cache_data(ttl=30)
def fetch_league_data(lid):
  league_res = requests.get(f"https://api.sleeper.app/v1/league/{lid}")
  if league_res.status_code != 200 or not league_res.json():
    return None, "League not found or invalid League ID."

  league_data = league_res.json()

  nfl_res = requests.get("https://api.sleeper.app/v1/state/nfl")
  if nfl_res.status_code == 200:
    nfl_state = nfl_res.json()
  else:
    nfl_state = {"week": 6, "season": "2026"}

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

  users_res = requests.get(f"https://api.sleeper.app/v1/league/{lid}/users")
  if users_res.status_code == 200:
    users = users_res.json()
  else:
    users = []

  user_names = {}
  for u in users:
    uid = u.get("user_id")
    uname = u.get("display_name", u.get("username", "Unknown"))
    user_names[uid] = uname

  rosters_res = requests.get(
      f"https://api.sleeper.app/v1/league/{lid}/rosters"
  )
  if rosters_res.status_code == 200:
    rosters = rosters_res.json()
  else:
    rosters = []

  roster_to_owner = {}
  roster_to_owner_id = {}
  for r in rosters:
    rid = r.get("roster_id")
    oid = r.get("owner_id")
    roster_to_owner[rid] = user_names.get(oid, f"Team {rid}")
    roster_to_owner_id[rid] = oid

  total_bench_pf = defaultdict(float)
  max_pf = defaultdict(float)

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

  current_pick_owners = {}
  for rid, owner_name in roster_to_owner.items():
    current_pick_owners[rid] = owner_name

  try:
    tp_res = requests.get(
        f"https://api.sleeper.app/v1/league/{lid}/traded_picks"
    )
    if tp_res.status_code == 200 and isinstance(tp_res.json(), list):
      next_season = str(int(season) + 1)
      for tp in tp_res.json():
        tp_s = str(tp.get("season"))
        tp_r = tp.get("round")
        orig_rid = tp.get("roster_id")
        if tp_s == next_season and tp_r == 1 and orig_rid in current_pick_owners:
          new_owner_id = tp.get("owner_id")
          current_pick_owners[orig_rid] = user_names.get(
              new_owner_id, "Traded Owner"
          )
  except Exception:
    pass

  data = []
  for rid, owner in roster_to_owner.items():
    data.append({
        "Original Team": owner,
        "Current Pick Owner": current_pick_owners.get(rid, owner),
        "Max PF": round(max_pf[rid], 2),
        "Total PF (Inc. Bench)": round(total_bench_pf[rid], 2),
    })

  return pd.DataFrame(data), None


if league_id:
  with st.spinner("Fetching

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
  u_league = f"https://api.sleeper.app/v1/league/{lid}"
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

  res_u = requests.get(f"https://api.sleeper.app/v1/league/{lid}/users")
  users = res_u.json() if res_u.status_code == 200 else []

  user_names = {}
  for u in users:
    uid = u.get("user_id")
    uname = u.get("display_name", u.get("username", "Unknown"))
    user_names[uid] = uname

  res_r = requests.get(f"https://api.sleeper.app/v1/league/{lid}/rosters")
  rosters = res_r.json() if res_r.status_code == 200 else []

  roster_to_owner = {}
  for r in rosters:
    rid = r.get("roster_id")
    oid = r.get("owner_id")
    roster_to_owner[rid] = user_names.get(oid, f"Team {rid}")

  total_bench_pf = defaultdict(float)
  max_pf = defaultdict(float)

  for week in range(1, regular_weeks + 1):
    u_m = f"https://api.sleeper.app/v1/league/{lid}/matchups/{week}"
    res_m = requests.get(u_m)
    if res_m.status_code != 200 or not res_m.json():
      continue

    for team in res_m.json():
      rid = team.get("roster_id")
      pts = team.get("players_points", {})
      if rid and pts:
        total_bench_pf[rid] += sum(pts.values())
        scores = sorted(pts.values(), reverse=True)
        max_pf[rid] += sum(scores[:num_starters])

  current_pick_owners = {}
  for rid, owner_name in roster_to_owner.items():
    current_pick_owners[rid] = owner_name

  try:
    u_tp = f"https://api.sleeper.app/v1/league/{lid}/traded_picks"
    res_tp = requests.get(u_tp)
    if res_tp.status_code == 200 and isinstance(res_tp.json(), list):
      next_season = str(int(season) + 1)
      for tp in res_tp.json():
        s_match = str(tp.get("season")) == next_season
        r_match = tp.get("round") == 1
        orig_rid = tp.get("roster_id")

        if s_match and r_match and orig_rid in current_pick_owners:
          new_oid = tp.get("owner_id")
          current_pick_owners[orig_rid] = user_names.get(new_oid, "Traded")
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


df, error = fetch_league_data(league_id)

if error:
  st.error(error)
elif df is not None and not df.empty:
  st.header("📋 1st Round Rookie Draft Board (Reverse Max PF)")
  st.caption("Lowest Max PF determines pick position.")

  df_draft = df.sort_values(by="Max PF", ascending=True).reset_index(drop=True)
  df_draft.index += 1
  df_draft.index.name = "Pick Slot"

  st.table(df_draft[["Original Team", "Current Pick Owner", "Max PF"]])

  st.write("---")

  col1, col2 = st.columns(2)

  with col1:
    st.subheader("📊 Ranked by Max PF")
    df_max = df.sort_values(by="Max PF", ascending=False).reset_index(drop=True)
    df_max.index += 1
    st.table(df_max[["Original Team", "Max PF"]])

  with col2:
    st.subheader("📈 Ranked by Total PF")
    df_total = df.sort_values(

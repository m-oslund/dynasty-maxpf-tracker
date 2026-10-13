from collections import defaultdict
import pandas as pd
import requests
import streamlit as st

st.set_page_config(page_title="Dynasty Standings", page_icon="🏈", layout="wide")

st.title("🏈 Dynasty Rookie Draft Board & Standings")
st.markdown("Live standings dynamically fetched from the Sleeper API.")

league_id = st.sidebar.text_input("Sleeper League ID:", "1314874337139904512")


@st.cache_data(ttl=30)
def fetch_league_data(lid):
  league_res = requests.get("https://api.sleeper.app/v1/league/" + str(lid))
  if league_res.status_code != 200 or not league_res.json():
    return None, "League not found or invalid League ID."

  league_data = league_res.json()
  nfl_res = requests.get("https://api.sleeper.app/v1/state/nfl")
  if nfl_res.status_code == 200:
    nfl_state = nfl_res.json()
  else:
    nfl_state = {"week": 1}

  current_week = nfl_state.get("week", 1)
  playoff_start = league_data.get("settings", {}).get("playoff_week_start", 15)

  if playoff_start and playoff_start > 1:
    regular_season_weeks = playoff_start - 1
  else:
    regular_season_weeks = max(1, min(current_week, 14))

  roster_positions = league_data.get("roster_positions", [])
  starter_positions = [
      p for p in roster_positions if p not in ["BN", "IR", "TAXI"]
  ]
  num_starters = len(starter_positions)

  users_res = requests.get(
      "https://api.sleeper.app/v1/league/" + str(lid) + "/users"
  )
  users = users_res.json() if users_res.status_code == 200 else []
  user_names = {}
  for u in users:
    uid = u.get("user_id")
    uname = u.get("display_name", u.get("username", "Unknown"))
    user_names[uid] = uname

  rosters_res = requests.get(
      "https://api.sleeper.app/v1/league/" + str(lid) + "/rosters"
  )
  rosters = rosters_res.json() if rosters_res.status_code == 200 else []

  roster_to_owner = {}
  roster_records = {}

  for r in rosters:
    rid = r.get("roster_id")
    oid = r.get("owner_id")
    owner_name = user_names.get(oid, "Team " + str(rid))
    roster_to_owner[rid] = owner_name

    settings = r.get("settings", {})
    wins = settings.get("wins", 0)
    losses = settings.get("losses", 0)
    ties = settings.get("ties", 0)

    if ties > 0:
      roster_records[rid] = str(wins) + "-" + str(losses) + "-" + str(ties)
    else:
      roster_records[rid] = str(wins) + "-" + str(losses)

  total_bench_pf = defaultdict(float)
  max_pf = defaultdict(float)

  for week in range(1, regular_season_weeks + 1):
    m_url = (
        "https://api.sleeper.app/v1/league/"
        + str(lid)
        + "/matchups/"
        + str(week)
    )
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

  data = []
  for rid, owner in roster_to_owner.items():
    data.append({
        "Team": owner,
        "Record": roster_records.get(rid, "0-0"),
        "Max PF Float": round(max_pf[rid], 2),
        "Total PF Float": round(total_bench_pf[rid], 2),
        "Max PF": f"{max_pf[rid]:,.2f}",
        "Total PF (Inc. Bench)": f"{total_bench_pf[rid]:,.2f}",
    })

  return pd.DataFrame(data), None


if league_id:
  df, error = fetch_league_data(league_id)

  if error:
    st.error(error)
  elif df is not None and not df.empty:
    col_left, col_right = st.columns(2)

    with col_left:
      st.subheader("📋 1st Round Rookie Draft Board")
      st.caption("Lowest Max PF determines rookie pick position.")

      df_draft = (
          df.sort_values(by="Max PF Float", ascending=True)
          .reset_index(drop=True)
          .copy()
      )
      df_draft.index += 1
      df_draft.index = [f"1.{i:02d}" for i in df_draft.index]
      df_draft.index.name = "Pick"

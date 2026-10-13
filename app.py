from collections import defaultdict
import pandas as pd
import requests
import streamlit as st

st.set_page_config(
    page_title="Dynasty League Standings", page_icon="🏈", layout="wide"
)

st.title("🏈 League Standings & Max PF Tracker")
st.markdown(
    "Live standings dynamically fetched from the Sleeper API. **Max PF** is"
    " calculated using optimal best-ball starting lineups each week."
)

league_id = st.sidebar.text_input("Sleeper League ID:", "1314874337139904512")


@st.cache_data(ttl=600)
def fetch_league_data(lid):
  league_res = requests.get(f"https://api.sleeper.app/v1/league/{lid}")
  if league_res.status_code != 200 or not league_res.json():
    return None, "League not found."

  league_data = league_res.json()
  nfl_state = requests.get("https://api.sleeper.app/v1/state/nfl").json()

  current_week = nfl_state.get("week", 1)
  playoff_start = league_data.get("settings", {}).get("playoff_week_start", 15)

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

  data = []
  for rid, owner in roster_to_owner.items():
    data.append({
        "Manager": owner,
        "Max PF": round(max_pf[rid], 2),
        "Total PF (Inc. Bench)": round(total_bench_pf[rid], 2),
    })

  return pd.DataFrame(data), None


if league_id:
  df, error = fetch_league_data(league_id)

  if error:
    st.error(error)
  else:
    st.subheader("📋 Reverse Max PF (Rookie Draft Order)")
    st.caption("Lowest Max PF receives the #1 overall pick.")

    df_draft = (
        df.sort_values(by="Max PF", ascending=True)
        .reset_index(drop=True)
        .copy()
    )
    df_draft.index += 1
    df_draft.index.name = "Pick Slot"
    st.dataframe(df_draft[["Manager", "Max PF"]], use_container_width=True)

    st.markdown("---")

    col1, col2 = st.columns(2)

    with col1:
      st.subheader("📊 Ranked by Max PF")
      df_max = (
          df.sort_values(by="Max PF", ascending=False)
          .reset_index(drop=True)
          .copy()
      )
      df_max.index += 1
      st.dataframe(df_max[["Manager", "Max PF"]], use_container_width=True)

    with col2:
      st.subheader("📈 Ranked by Total PF (Inc. Bench)")
      df_total = (
          df.sort_values(by="Total PF (Inc. Bench)", ascending=False)
          .reset_index(drop=True)
          .copy()
      )
      df_total.index += 1
      st.dataframe(
          df_total[["Manager", "Total PF (Inc. Bench)"]],
          use_container_width=True,
      )

from collections import defaultdict
import pandas as pd
import requests
import streamlit as st

st.set_page_config(
    page_title="AFL Standings and Draft Board",
    page_icon="🏈",
    layout="wide",
)

st.title("🏈 AFL Standings and Draft Board")
st.markdown("Live standings dynamically refreshed every 30 seconds from the Sleeper API.")

league_id = st.sidebar.text_input("Sleeper League ID:", "1314874337139904512")


@st.cache_data(ttl=30)
def fetch_league_data(lid):
    league_res = requests.get(f"https://api.sleeper.app/v1/league/{lid}")
    if league_res.status_code != 200 or not league_res.json():
        return None, "League not found or invalid League ID."

    league_data = league_res.json()
    nfl_res = requests.get("https://api.sleeper.app/v1/state/nfl")
    nfl_state = nfl_res.json() if nfl_res.status_code == 200 else {"week": 1}

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

    users_res = requests.get(f"https://api.sleeper.app/v1/league/{lid}/users")
    users = users_res.json() if users_res.status_code == 200 else []
    user_names = {
        u.get("user_id"): u.get("display_name", u.get("username", "Unknown"))
        for u in users
    }

    rosters_res = requests.get(
        f"https://api.sleeper.app/v1/league/{lid}/rosters"
    ).json()

    roster_to_owner = {}
    roster_records = {}
    roster_sort_data = {}

    for r in rosters_res:
        rid = r.get("roster_id")
        oid = r.get("owner_id")
        owner_name = user_names.get(oid, f"Team {rid}")
        roster_to_owner[rid] = owner_name

        settings = r.get("settings", {})
        wins = settings.get("wins", 0)
        losses = settings.get("losses", 0)
        ties = settings.get("ties", 0)
        fpts = settings.get("fpts", 0) + (settings.get("fpts_decimal", 0) / 100.0)

        roster_sort_data[rid] = {"wins": wins, "losses": losses, "ties": ties, "fpts": fpts}

        if ties > 0:
            roster_records[rid] = f"{wins}-{losses}-{ties}"
        else:
            roster_records[rid] = f"{wins}-{losses}"

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
        s = roster_sort_data[rid]
        data.append({
            "Team": owner,
            "Record": roster_records.get(rid, "0-0"),
            "Wins": s["wins"],
            "Ties": s["ties"],
            "FPTS": s["fpts"],
            "Max PF Float": round(max_pf[rid], 2),
            "Total PF Float": round(total_bench_pf[rid], 2),
            "Max PF": f"{max_pf[rid]:,.2f}",
            "Total PF": f"{total_bench_pf[rid]:,.2f}",
        })

    return pd.DataFrame(data), None


if league_id:
    df, error = fetch_league_data(league_id)

    if error:
        st.error(error)
    elif df is not None and not df.empty:
        # 1. League Standings (Tightened)
        st.subheader("🏆 League Standings")

        df_standings = (
            df.sort_values(by=["Wins", "Ties", "FPTS"], ascending=[False, False, False])
            .reset_index(drop=True)
            .copy()
        )
        df_standings.index += 1
        df_standings.index.name = "Rank"

        c1, c2, c3 = st.columns([1, 2, 1])
        with c2:
            st.table(df_standings[["Team", "Record"]])

        st.markdown("---")

        # 2. Rookie Draft Order (Tightened)
        st.subheader("📋 Rookie Draft Order")
        st.caption("Lowest Max PF determines rookie pick position.")

        df_draft = (
            df.sort_values(by="Max PF Float", ascending=True)
            .reset_index(drop=True)
            .copy()
        )
        df_draft.index += 1
        df_draft.index = [f"1.{i:02d}" for i in df_draft.index]
        df_draft.index.name = "Pick"

        d1, d2, d3 = st.columns([1, 2, 1])
        with d2:
            st.table(df_draft[["Team", "Max PF", "Record"]])

        st.markdown("<br>", unsafe_allow_html=True)

        # 3. Total PF (Tightened)
        st.subheader("📈 Total PF (Reverse Order)")
        st.caption("Lowest Total PF to highest Total PF.")

        df_total = (
            df.sort_values(by="Total PF Float", ascending=True)
            .reset_index(drop=True)
            .copy()
        )
        df_total.index += 1
        df_total.index = [f"1.{i:02d}" for i in df_total.index]
        df_total.index.name = "Pick"

        t1, t2, t3 = st.columns([1, 2, 1])
        with t2:
            st.table(df_total[["Team", "Total PF", "Record"]])
    else:
        st.warning("No data found for this league ID.")

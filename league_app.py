import streamlit as st
import sqlite3
import pandas as pd
import itertools

# ---------- Config ----------
DB_FILE = "results.db"
PLAYERS = [
    "James Blood",
    "Tee Osho",
    "Brenda McKeown",
    "Kushal Shah",
    "Andreas Oikonomou",
    "Andy Dazzo",
    "Bobby Reardon",
    "Jack Burton",
    "Riley Leonard",
    "Luke Geier",
    "Zachary Robbins",
    "Mohammed Namazi",
    "Andrew Mannon",
    "Herman Mondesir",
    "Jacob Wallack",
    "Nano Boakye",
    "Alfie Deller",
    "Ryan Belfer",
    "Carlos Lopez",
    "Felix Veletanga",
    "Michael Casillas",
    "Matthew Peknay"
]  
ADMIN_PASSWORD = "fanduel123"  # <-- Set your admin password here

# ---------- Database Setup ----------
def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            player_a TEXT,
            player_b TEXT,
            score_a INTEGER,
            score_b INTEGER
        )
    ''')
    conn.commit()
    conn.close()

# ---------- Submit Result ----------
def submit_result(player_a, player_b, score_a, score_b):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''
        SELECT COUNT(*) FROM results
        WHERE (player_a = ? AND player_b = ?) OR (player_a = ? AND player_b = ?)
    ''', (player_a, player_b, player_b, player_a))
    match_count = c.fetchone()[0]
    if match_count > 0:
        conn.close()
        return False
    else:
        c.execute('INSERT INTO results (player_a, player_b, score_a, score_b) VALUES (?, ?, ?, ?)',
                  (player_a, player_b, score_a, score_b))
        conn.commit()
        conn.close()
        return True

# ---------- Generate League Table ----------
def generate_league_table():
    conn = sqlite3.connect(DB_FILE)
    df = pd.read_sql_query('SELECT * FROM results', conn)
    conn.close()

    table = pd.DataFrame({'Player': PLAYERS})
    table.set_index('Player', inplace=True)
    table['Goals Scored'] = 0
    table['Goals Against'] = 0
    table['Points'] = 0
    table['Wins'] = 0
    table['Draws'] = 0
    table['Losses'] = 0
    table['Matches Played'] = 0

    for _, row in df.iterrows():
        a, b = row['player_a'], row['player_b']
        sa, sb = row['score_a'], row['score_b']

        table.at[a, 'Goals Scored'] += sa
        table.at[a, 'Goals Against'] += sb
        table.at[b, 'Goals Scored'] += sb
        table.at[b, 'Goals Against'] += sa

        table.at[a, 'Matches Played'] += 1
        table.at[b, 'Matches Played'] += 1

        if sa > sb:
            table.at[a, 'Points'] += 3
            table.at[a, 'Wins'] += 1
            table.at[b, 'Losses'] += 1
        elif sa < sb:
            table.at[b, 'Points'] += 3
            table.at[b, 'Wins'] += 1
            table.at[a, 'Losses'] += 1
        else:
            table.at[a, 'Points'] += 1
            table.at[b, 'Points'] += 1
            table.at[a, 'Draws'] += 1
            table.at[b, 'Draws'] += 1

    total_matches = len(PLAYERS) - 1
    table['Matches Remaining'] = total_matches - table['Matches Played']
    table['Goal Difference'] = table['Goals Scored'] - table['Goals Against']

    table = table.sort_values(
        by=['Points', 'Goal Difference', 'Goals Scored'],
        ascending=[False, False, False]
    ).reset_index()

    return table

# ---------- Fixtures Management ----------
def get_unplayed_fixtures():
    conn = sqlite3.connect(DB_FILE)
    played = pd.read_sql_query('SELECT player_a, player_b FROM results', conn)
    conn.close()

    played_set = set()
    for _, row in played.iterrows():
        played_set.add(tuple(sorted((row['player_a'], row['player_b']))))

    all_possible = set(tuple(sorted(pair)) for pair in itertools.combinations(PLAYERS, 2))
    unplayed = all_possible - played_set

    return sorted(list(unplayed))

def split_fixtures():
    conn = sqlite3.connect(DB_FILE)
    played = pd.read_sql_query('SELECT player_a, player_b, score_a, score_b FROM results', conn)
    conn.close()

    all_fixtures = pd.DataFrame(itertools.combinations(PLAYERS, 2), columns=["Player A", "Player B"])

    played_matches = set()
    for _, row in played.iterrows():
        played_matches.add(tuple(sorted((row['player_a'], row['player_b']))))

    unplayed_fixtures = []
    for _, row in all_fixtures.iterrows():
        match = tuple(sorted((row['Player A'], row['Player B'])))
        if match not in played_matches:
            unplayed_fixtures.append(match)

    return pd.DataFrame(unplayed_fixtures, columns=["Player A", "Player B"]), played

# ---------- Streamlit App ----------
st.title("🏀 Tournament Manager")

# Admin login
st.sidebar.header("Admin Login")
admin_password = st.sidebar.text_input("Enter admin password", type="password")
is_admin = admin_password == ADMIN_PASSWORD

init_db()

with st.expander("📜 Rules"):
    st.markdown("""
    - Each player plays every other player once.
    - 3 points for a win, 1 point for a draw.
    - League ranking: Points > Goal Difference > Goals Scored.
    - Remember your skill rankings! For every one level you are above your opponent, you get a 0.5 team star rating penalty. For example, if you are a Newcastle rated Player, playing against a Bournemouth rated Player, you will have a 0.5 star rating penalty. If you are a Bournemouth rated Player playing against a Newcastle rated Player, you will must choose a 4.5 star team if your opponent chooses a 5 star team.
    - Skill levels can change through the season if needed.
    - Default game settings apply to all matches.
    - If you are playing a match, please make sure to record the result here.
    """)

# --- Submit Match Result ---
st.header("Input Match Result")
unplayed_fixtures = get_unplayed_fixtures()

with st.form("result_form"):
    if unplayed_fixtures:
        match = st.selectbox("Select a match to input", [f"{a} vs {b}" for a, b in unplayed_fixtures])
        selected_a, selected_b = match.split(" vs ")

        score_col1, score_col2 = st.columns(2)
        score_a = score_col1.number_input(f"{selected_a} Score", min_value=0, step=1)
        score_b = score_col2.number_input(f"{selected_b} Score", min_value=0, step=1)

        if st.form_submit_button("Submit Result"):
            success = submit_result(selected_a, selected_b, int(score_a), int(score_b))
            if success:
                st.success(f"Result submitted: {selected_a} {score_a} - {score_b} {selected_b}")
            else:
                st.error("⚠️ This match has already been recorded.")
    else:
        st.info("🎉 All matches have been played!")

st.markdown("---")

# --- Tabs ---
tab1, tab2 = st.tabs(["🏆 League Table", "📋 Fixtures & Results"])

with tab1:
    st.subheader("League Table")
    table = generate_league_table()
    st.dataframe(table, use_container_width=True)

    # Export buttons
    csv_league = table.to_csv(index=False).encode('utf-8')
    st.download_button("Download League Table as CSV", data=csv_league, file_name="league_table.csv", mime="text/csv")

with tab2:
    st.subheader("Unplayed Fixtures")
    unplayed, played = split_fixtures()

    if not unplayed.empty:
        st.dataframe(unplayed, use_container_width=True)
    else:
        st.success("🎉 All fixtures have been played!")

    st.subheader("Completed Results")
    if not played.empty:
        played['Result'] = played['player_a'] + " " + played['score_a'].astype(str) + " - " + played['score_b'].astype(str) + " " + played['player_b']
        st.dataframe(played[['Result']], use_container_width=True)

        csv_results = played.to_csv(index=False).encode('utf-8')
        st.download_button("Download Match Results as CSV", data=csv_results, file_name="match_results.csv", mime="text/csv")
    else:
        st.info("No results recorded yet.")

# --- Admin Only ---
if is_admin:
    st.markdown("---")
    st.header("Admin: Edit or Delete Results")

    conn = sqlite3.connect(DB_FILE)
    matches = pd.read_sql_query('SELECT id, player_a, player_b, score_a, score_b FROM results', conn)
    conn.close()

    if matches.empty:
        st.info("No matches to edit or delete.")
    else:
        matches['label'] = matches['player_a'] + " " + matches['score_a'].astype(str) + " - " + matches['score_b'].astype(str) + " " + matches['player_b']

        match_to_edit_label = st.selectbox("Select a match to edit", matches['label'])
        match_to_edit_id = matches.loc[matches['label'] == match_to_edit_label, 'id'].values[0]

        edit_col1, edit_col2 = st.columns(2)
        new_score_a = edit_col1.number_input("New Score for Player A", min_value=0, step=1, key="edit_score_a")
        new_score_b = edit_col2.number_input("New Score for Player B", min_value=0, step=1, key="edit_score_b")

        if st.button("Update Result"):
            conn = sqlite3.connect(DB_FILE)
            c = conn.cursor()
            c.execute('UPDATE results SET score_a = ?, score_b = ? WHERE id = ?', (int(new_score_a), int(new_score_b), int(match_to_edit_id)))
            conn.commit()
            conn.close()
            st.success("Result updated successfully!")

        if st.button("Delete Result"):
            conn = sqlite3.connect(DB_FILE)
            c = conn.cursor()
            c.execute('DELETE FROM results WHERE id = ?', (int(match_to_edit_id),))
            conn.commit()
            conn.close()
            st.success("Result deleted successfully!")
else:
    st.info("🔐 Admin login required to edit or delete results.")


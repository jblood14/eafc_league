import streamlit as st
import psycopg2
from psycopg2.extras import RealDictCursor
import pandas as pd
import itertools

# ---------- Config ----------

PLAYERS = [
    "James Blood",
    "Tee Osho",
    "Brendan McKeown",
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
    "Nana Boakye",
    "Alfie Deller",
    "Ryan Belfer",
    "Carlos Lopez",
    "Felix Veletanga",
    "Michael Casillas",
    "Matthew Peknay"
]  
ADMIN_PASSWORD = "fanduel123"  # <-- Set your admin password here

# ---------- Database Connection ----------
def get_connection():
    return psycopg2.connect(
        host=st.secrets["db_host"],
        database=st.secrets["db_name"],
        user=st.secrets["db_user"],
        password=st.secrets["db_password"],
        port=st.secrets["db_port"],
        cursor_factory=RealDictCursor
    )

# ---------- Database Setup ----------
def init_db():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute('''
        CREATE TABLE IF NOT EXISTS updated_results (
            id SERIAL PRIMARY KEY,
            player_a TEXT NOT NULL,
            player_b TEXT NOT NULL,
            score_a INTEGER NOT NULL,
            score_b INTEGER NOT NULL
        )
    ''')
    conn.commit()
    cur.close()
    conn.close()

# ---------- Submit Result ----------
def submit_result(player_a, player_b, score_a, score_b):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(f'''
        SELECT COUNT(*) FROM updated_results
        WHERE (player_a = '{player_a}' AND player_b = '{player_b}') OR (player_a = '{player_a}' AND player_b = '{player_b}')
    ''')
    match_count = cur.fetchone()["count"]
    if match_count > 0:
        cur.close()
        conn.close()
        return False
    else:
        cur.execute(f"INSERT INTO updated_results (player_a, player_b, score_a, score_b) VALUES ('{player_a}', '{player_b}', '{score_a}', '{score_b}')")
        conn.commit()
        cur.close()
        conn.close()
        return True
# ---------- Delete Database Table ----------
def delete_db():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute('DROP TABLE IF EXISTS results')
    conn.commit()
    cur.close()
    conn.close()

# ---------- Delete All Results ----------
#conn = get_connection()
#cur = conn.cursor()
#
#cur.execute('SELECT * FROM updated_results;')
#rows = cur.fetchall()
#colnames = [desc[0] for desc in cur.description]
#
#df = pd.DataFrame(rows, columns=colnames)
#
#cur.close()
#conn.close()
#
#st.dataframe(df)

# ---------- Generate League Table ----------
def fetch_results_table():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute('SELECT * FROM updated_results;')
    rows = cur.fetchall()
    colnames = [desc[0] for desc in cur.description]
    cur.close()
    conn.close()

    if not rows:
        return pd.DataFrame(columns=colnames)
    
    df = pd.DataFrame(rows, columns=colnames)
    return df

def generate_league_table():
    df = fetch_results_table()

    # Build empty League Table first
    table = pd.DataFrame({'Player': PLAYERS})
    table.set_index('Player', inplace=True)
    table['Goals Scored'] = 0
    table['Goals Against'] = 0
    table['Points'] = 0
    table['Wins'] = 0
    table['Draws'] = 0
    table['Losses'] = 0
    table['Matches Played'] = 0

    if not df.empty:
        for _, row in df.iterrows():
            a, b = row['player_a'].strip(), row['player_b'].strip()
            sa, sb = row['score_a'], row['score_b']

            if a not in table.index or b not in table.index:
                st.warning(f"Player not found in table: {a} or {b}")
                continue

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
    conn = get_connection()
    played = pd.read_sql_query('SELECT player_a, player_b FROM updated_results', conn)
    conn.close()

    played_set = set()
    for _, row in played.iterrows():
        played_set.add(tuple(sorted((row['player_a'], row['player_b']))))

    all_possible = set(tuple(sorted(pair)) for pair in itertools.combinations(PLAYERS, 2))
    unplayed = all_possible - played_set

    return sorted(list(unplayed))

def split_fixtures():
    # Fetch all played matches
    conn = get_connection()
    cur = conn.cursor()
    cur.execute('SELECT player_a, player_b, score_a, score_b FROM updated_results;')
    rows = cur.fetchall()
    colnames = [desc[0] for desc in cur.description]
    cur.close()
    conn.close()

    if not rows:
        played_df = pd.DataFrame(columns=colnames)
    else:
        played_df = pd.DataFrame(rows, columns=colnames)

    # Build all possible fixtures
    all_fixtures = pd.DataFrame(itertools.combinations(PLAYERS, 2), columns=["Player A", "Player B"])

    # Find which fixtures have been played
    played_matches = set()
    for _, row in played_df.iterrows():
        played_matches.add(tuple(sorted((row['player_a'].strip(), row['player_b'].strip()))))

    # Find unplayed fixtures
    unplayed_fixtures = []
    for _, row in all_fixtures.iterrows():
        match = tuple(sorted((row['Player A'], row['Player B'])))
        if match not in played_matches:
            unplayed_fixtures.append(match)

    unplayed_df = pd.DataFrame(unplayed_fixtures, columns=["Player A", "Player B"])

    return unplayed_df, played_df
def fetch_completed_results():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute('SELECT player_a, player_b, score_a, score_b FROM updated_results;')
    rows = cur.fetchall()
    colnames = [desc[0] for desc in cur.description]
    cur.close()
    conn.close()

    if not rows:
        return pd.DataFrame(columns=colnames)
    
    df = pd.DataFrame(rows, columns=colnames)
    return df

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
    """)

# --- Submit Match Result ---
st.header("Input Match Result")
unplayed_fixtures = get_unplayed_fixtures()

# First select the match (OUTSIDE the form)
if unplayed_fixtures:
    match = st.selectbox("Select a match to input", [f"{a} vs {b}" for a, b in unplayed_fixtures])
    selected_a, selected_b = match.split(" vs ")

    # THEN inside the form
    with st.form("result_form"):
        score_col1, score_col2 = st.columns(2)
        score_a = score_col1.number_input(f"{selected_a} Score", min_value=0, step=1, key="score_a")
        score_b = score_col2.number_input(f"{selected_b} Score", min_value=0, step=1, key="score_b")

        submitted = st.form_submit_button("Submit Result")
        if submitted:
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

    conn = get_connection()
    matches = pd.read_sql_query('SELECT id, player_a, player_b, score_a, score_b FROM updated_results', conn)
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
            conn = get_connection()
            cur = conn.cursor()
            cur.execute('UPDATE updated_results SET score_a = %s, score_b = %s WHERE id = %s', (int(new_score_a), int(new_score_b), int(match_to_edit_id)))
            conn.commit()
            cur.close()
            conn.close()
            st.success("Result updated successfully!")

        if st.button("Delete Result"):
            conn = get_connection()
            cur = conn.cursor()
            cur.execute('DELETE FROM updated_results WHERE id = %s', (int(match_to_edit_id),))
            conn.commit()
            cur.close()
            conn.close()
            st.success("Result deleted successfully!")
else:
    st.info("🔐 Admin login required to edit or delete results.")

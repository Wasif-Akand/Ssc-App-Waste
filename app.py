import streamlit as st
import pandas as pd
import sqlite3
import os

# ==========================================
# ⚙️ GLOBAL CONFIGURATION
# ==========================================
APP_NAME = "SSC ACADEMIC HUB (SQL Edition)"
APP_ICON = "⚡"
THEME_COLOR = "#00FFA3" 
BG_COLOR = "#050505"      
DB_FILE = "master_db.db"
CSV_BACKUP = "master_data.csv" # For initial migration
TOPIC_OPTIONS = ["Physics", "Chemistry", "Biology", "Higher Math", "General Math", "English", "ICT", "BGS"]

# ==========================================
# 1. SQL DATA ENGINE
# ==========================================
def get_connection():
    return sqlite3.connect(DB_FILE, check_same_thread=False)

def init_db():
    conn = get_connection()
    c = conn.cursor()
    # Create the table if it doesn't exist
    c.execute('''CREATE TABLE IF NOT EXISTS study_cards 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  topic TEXT, subtopic TEXT, key TEXT, value TEXT, 
                  success INTEGER DEFAULT 0, failure INTEGER DEFAULT 0, 
                  bookmarked BOOLEAN DEFAULT 0)''')
    conn.commit()
    
    # --- AUTOMATIC MIGRATION FROM CSV ---
    if os.path.exists(CSV_BACKUP):
        try:
            df_old = pd.read_csv(CSV_BACKUP)
            # Basic cleanup of old names if needed
            if 'Subject' in df_old.columns: df_old.rename(columns={'Subject': 'topic'}, inplace=True)
            if 'Topic' in df_old.columns: df_old.rename(columns={'Topic': 'subtopic'}, inplace=True)
            # Rename other columns to lowercase to match SQL
            df_old.columns = [c.lower() for c in df_old.columns]
            
            # Insert into SQL
            df_old.to_sql('study_cards', conn, if_exists='append', index=False)
            conn.close()
            os.rename(CSV_BACKUP, "master_data_OLD_MIGRATED.csv") # Rename so it doesn't migrate twice
            st.success("Successfully migrated CSV data to SQLite!")
        except Exception as e:
            st.error(f"Migration error: {e}")

# Call init on start
init_db()

# Function to pull data from SQL into a DataFrame
def load_all_data():
    conn = get_connection()
    df = pd.read_sql_query("SELECT * FROM study_cards", conn)
    conn.close()
    return df

# Initialize Session States
if 'active_topic' not in st.session_state: st.session_state.active_topic = "Physics"
if 'active_subtopic' not in st.session_state: st.session_state.active_subtopic = "None"
if 'page' not in st.session_state: st.session_state.page = "Study Mode"
if 'card_index' not in st.session_state: st.session_state.card_index = 0
if 'show_answer' not in st.session_state: st.session_state.show_answer = False

# ==========================================
# 2. UI SETUP
# ==========================================
st.set_page_config(page_title=APP_NAME, page_icon=APP_ICON, layout="wide")
st.markdown(f"""
    <style>
    .stApp {{ background-color: {BG_COLOR}; color: #E0E0E0; }}
    section[data-testid="stSidebar"] {{ background-color: #0A0A0A !important; border-right: 1px solid #222; }}
    .stButton > button {{ width: 100%; border-radius: 8px; background-color: transparent; border: 1px solid #333; }}
    .stButton > button:hover {{ border-color: {THEME_COLOR}; color: {THEME_COLOR}; }}
    </style>
""", unsafe_allow_html=True)

# ==========================================
# 3. SIDEBAR (CRUD OPERATIONS)
# ==========================================
with st.sidebar:
    st.title(f"{APP_ICON} {APP_NAME}")
    if st.button("📖 Study Mode"): st.session_state.page = "Study Mode"; st.rerun()
    if st.button("🗂️ Master Database"): st.session_state.page = "Master Database"; st.rerun()
    st.divider()

    df_master = load_all_data()

    if st.session_state.page == "Study Mode":
        with st.expander("➕ **Add New Subtopic**"):
            t_in = st.selectbox("Select Topic", TOPIC_OPTIONS)
            s_in = st.text_input("Subtopic Name").strip()
            if st.button("Initialize"):
                if s_in:
                    conn = get_connection()
                    conn.execute("INSERT INTO study_cards (topic, subtopic, key, value) VALUES (?,?,?,?)", 
                                 (t_in, s_in, "Definition", "Answer"))
                    conn.commit(); conn.close()
                    st.session_state.active_topic, st.session_state.active_subtopic = t_in, s_in
                    st.rerun()

        st.subheader("📚 Library")
        topics = sorted(df_master['topic'].unique()) if not df_master.empty else []
        for t in topics:
            with st.expander(f"**{t}**"):
                subtopics = sorted(df_master[df_master['topic'] == t]['subtopic'].unique())
                for s in subtopics:
                    c1, c2 = st.columns([4, 1])
                    if c1.button(f"• {s}", key=f"nav_{t}_{s}"):
                        st.session_state.active_topic, st.session_state.active_subtopic = t, s
                        st.session_state.card_index = 0; st.session_state.show_answer = False; st.rerun()
                    if c2.button("🗑️", key=f"del_{t}_{s}"):
                        conn = get_connection()
                        conn.execute("DELETE FROM study_cards WHERE topic=? AND subtopic=?", (t, s))
                        conn.commit(); conn.close(); st.rerun()

# ==========================================
# 4. MAIN INTERFACE
# ==========================================
df_master = load_all_data() # Refresh data

if st.session_state.page == "Study Mode":
    st.title(f"{st.session_state.active_topic} : {st.session_state.active_subtopic}")
    tabs = st.tabs(["⚡ Flash Card", "📥 Add Content", "📂 Local Data", "📊 Topic Overview", "🔖 Bookmarks"])

    mask = (df_master['topic'] == st.session_state.active_topic) & (df_master['subtopic'] == st.session_state.active_subtopic)
    sub_df = df_master[mask].reset_index()

    with tabs[0]: # FLASH CARDS
        mode = st.radio("Study Focus:", ["All", "Wrong", "Right", "Bookmarks"], horizontal=True)
        filtered_df = sub_df
        if mode == "Wrong": filtered_df = sub_df[sub_df['failure'] > 0]
        elif mode == "Right": filtered_df = sub_df[sub_df['success'] > 0]
        elif mode == "Bookmarks": filtered_df = sub_df[sub_df['bookmarked'] == 1]

        if filtered_df.empty: st.warning("No cards matching criteria.")
        else:
            card = filtered_df.iloc[st.session_state.card_index % len(filtered_df)]
            st.info(f"**Question:** {card['key']}")
            if st.session_state.show_answer: st.success(f"**Answer:** {card['value']}")

            col1, col2, col3, col4 = st.columns(4)
            if not st.session_state.show_answer:
                if col1.button("✅ Right"):
                    conn = get_connection(); conn.execute("UPDATE study_cards SET success = success + 1 WHERE id=?", (int(card['id']),)); conn.commit(); conn.close()
                    st.session_state.show_answer = True; st.rerun()
                if col2.button("❌ Wrong"):
                    conn = get_connection(); conn.execute("UPDATE study_cards SET failure = failure + 1 WHERE id=?", (int(card['id']),)); conn.commit(); conn.close()
                    st.session_state.show_answer = True; st.rerun()
            else:
                if col1.button("➡️ Next Card"): st.session_state.card_index += 1; st.session_state.show_answer = False; st.rerun()

            if col3.button("🔖 Bookmark"):
                new_val = 0 if card['bookmarked'] else 1
                conn = get_connection(); conn.execute("UPDATE study_cards SET bookmarked = ? WHERE id=?", (new_val, int(card['id']))); conn.commit(); conn.close(); st.rerun()
            if col4.button("⏭️ Skip"): st.session_state.card_index += 1; st.session_state.show_answer = False; st.rerun()

    with tabs[1]: # BULK ADD
        bulk = st.text_area("Question -!- Answer")
        if st.button("🚀 Process"):
            if bulk:
                conn = get_connection()
                for line in bulk.strip().split('\n'):
                    if "-!-" in line:
                        p = line.split("-!-")
                        conn.execute("INSERT INTO study_cards (topic, subtopic, key, value) VALUES (?,?,?,?)", 
                                     (st.session_state.active_topic, st.session_state.active_subtopic, p[0].strip(), p[1].strip()))
                conn.commit(); conn.close(); st.rerun()

    with tabs[2]: # LOCAL DATA
        edited = st.data_editor(sub_df.drop(columns=['index']), use_container_width=True, num_rows="dynamic", key="sql_ed")
        if st.button("💾 Save Changes"):
            conn = get_connection()
            # Simplest way: Delete current subtopic and re-insert edited data
            conn.execute("DELETE FROM study_cards WHERE topic=? AND subtopic=?", (st.session_state.active_topic, st.session_state.active_subtopic))
            edited.to_sql('study_cards', conn, if_exists='append', index=False)
            conn.commit(); conn.close(); st.rerun()

    with tabs[3]: # OVERVIEW
        st.bar_chart(sub_df.set_index('key')[['success', 'failure']])
        if st.button("🗑️ Reset Stats"):
            conn = get_connection(); conn.execute("UPDATE study_cards SET success=0, failure=0 WHERE topic=? AND subtopic=?", (st.session_state.active_topic, st.session_state.active_subtopic)); conn.commit(); conn.close(); st.rerun()

    with tabs[4]: # BOOKMARKS
        st.table(sub_df[sub_df['bookmarked'] == 1][['key', 'value']])

else: # MASTER DATABASE
    st.title("🗂️ Master Database")
    m_edited = st.data_editor(df_master, use_container_width=True, num_rows="dynamic")
    if st.button("💾 Save All"):
        conn = get_connection()
        m_edited.to_sql('study_cards', conn, if_exists='replace', index=False)
        conn.commit(); conn.close(); st.rerun()
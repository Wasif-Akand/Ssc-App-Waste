import streamlit as st
import pandas as pd
import sqlite3
import os
from contextlib import contextmanager

# ==========================================
# ⚙️ GLOBAL CONFIGURATION
# ==========================================
APP_NAME = "SSC ACADEMIC HUB (SQL Edition)"
APP_ICON = "⚡"
THEME_COLOR = "#00FFA3" 
BG_COLOR = "#050505"      
DB_FILE = "master_db.db"
CSV_BACKUP = "master_data.csv"
TOPIC_OPTIONS = ["Physics", "Chemistry", "Biology", "Higher Math", "General Math", "English", "ICT", "BGS"]

# ==========================================
# 1. SQL DATA ENGINE WITH CONNECTION POOLING
# ==========================================
@st.cache_resource
def get_connection():
    """Cached connection to avoid multiple connections."""
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

@contextmanager
def get_db_cursor():
    """Context manager for safe database operations."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        yield cursor
        conn.commit()
    except Exception as e:
        conn.rollback()
        st.error(f"❌ Database error: {str(e)}")
        raise
    finally:
        pass  # Connection stays cached

def init_db():
    """Initialize database and migrate from CSV if needed."""
    try:
        conn = get_connection()
        c = conn.cursor()
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
                if 'Subject' in df_old.columns: 
                    df_old.rename(columns={'Subject': 'topic'}, inplace=True)
                if 'Topic' in df_old.columns: 
                    df_old.rename(columns={'Topic': 'subtopic'}, inplace=True)
                df_old.columns = [c.lower() for c in df_old.columns]
                
                df_old.to_sql('study_cards', conn, if_exists='append', index=False)
                os.rename(CSV_BACKUP, "master_data_OLD_MIGRATED.csv")
                st.success("✅ Successfully migrated CSV data to SQLite!")
            except Exception as e:
                st.error(f"❌ Migration error: {str(e)}")
    except Exception as e:
        st.error(f"❌ Database initialization error: {str(e)}")

# Call init on start
init_db()

@st.cache_data(ttl=300)
def load_all_data():
    """Load all data from database with caching (5 min TTL)."""
    try:
        conn = get_connection()
        df = pd.read_sql_query("SELECT * FROM study_cards", conn)
        return df if not df.empty else pd.DataFrame(columns=['id', 'topic', 'subtopic', 'key', 'value', 'success', 'failure', 'bookmarked'])
    except Exception as e:
        st.error(f"❌ Error loading data: {str(e)}")
        return pd.DataFrame()

def clear_data_cache():
    """Clear cached data after modifications."""
    st.cache_data.clear()

# Initialize Session States
if 'active_topic' not in st.session_state: 
    st.session_state.active_topic = "Physics"
if 'active_subtopic' not in st.session_state: 
    st.session_state.active_subtopic = "None"
if 'page' not in st.session_state: 
    st.session_state.page = "Study Mode"
if 'card_index' not in st.session_state: 
    st.session_state.card_index = 0
if 'show_answer' not in st.session_state: 
    st.session_state.show_answer = False

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
    if st.button("📖 Study Mode"): 
        st.session_state.page = "Study Mode"
        st.rerun()
    if st.button("🗂️ Master Database"): 
        st.session_state.page = "Master Database"
        st.rerun()
    st.divider()

    df_master = load_all_data()

    if st.session_state.page == "Study Mode":
        with st.expander("➕ **Add New Subtopic**"):
            t_in = st.selectbox("Select Topic", TOPIC_OPTIONS)
            s_in = st.text_input("Subtopic Name").strip()
            if st.button("Initialize"):
                if s_in:
                    try:
                        with get_db_cursor() as cursor:
                            cursor.execute("INSERT INTO study_cards (topic, subtopic, key, value) VALUES (?,?,?,?)", 
                                         (t_in, s_in, "Definition", "Answer"))
                        clear_data_cache()
                        st.session_state.active_topic, st.session_state.active_subtopic = t_in, s_in
                        st.success("✅ Subtopic created!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"❌ Error creating subtopic: {str(e)}")
                else:
                    st.warning("⚠️ Please enter a subtopic name.")

        st.subheader("📚 Library")
        if df_master.empty:
            st.info("ℹ️ No topics yet. Create one above!")
        else:
            topics = sorted(df_master['topic'].unique())
            for t in topics:
                with st.expander(f"**{t}**"):
                    subtopics = sorted(df_master[df_master['topic'] == t]['subtopic'].unique())
                    for s in subtopics:
                        c1, c2 = st.columns([4, 1])
                        if c1.button(f"• {s}", key=f"nav_{t}_{s}"):
                            st.session_state.active_topic, st.session_state.active_subtopic = t, s
                            st.session_state.card_index = 0
                            st.session_state.show_answer = False
                            st.rerun()
                        if c2.button("🗑️", key=f"del_{t}_{s}"):
                            try:
                                with get_db_cursor() as cursor:
                                    cursor.execute("DELETE FROM study_cards WHERE topic=? AND subtopic=?", (t, s))
                                clear_data_cache()
                                st.success("✅ Deleted!")
                                st.rerun()
                            except Exception as e:
                                st.error(f"❌ Error deleting: {str(e)}")

# ==========================================
# 4. MAIN INTERFACE
# ==========================================
df_master = load_all_data()

if st.session_state.page == "Study Mode":
    st.title(f"{st.session_state.active_topic} : {st.session_state.active_subtopic}")
    tabs = st.tabs(["⚡ Flash Card", "📥 Add Content", "📂 Local Data", "📊 Topic Overview", "🔖 Bookmarks"])

    mask = (df_master['topic'] == st.session_state.active_topic) & (df_master['subtopic'] == st.session_state.active_subtopic)
    sub_df = df_master[mask].reset_index(drop=True)

    with tabs[0]:  # FLASH CARDS
        if sub_df.empty:
            st.warning("⚠️ No cards in this subtopic. Add content in the 'Add Content' tab.")
        else:
            mode = st.radio("Study Focus:", ["All", "Wrong", "Right", "Bookmarks"], horizontal=True)
            filtered_df = sub_df.copy()
            if mode == "Wrong": 
                filtered_df = sub_df[sub_df['failure'] > 0]
            elif mode == "Right": 
                filtered_df = sub_df[sub_df['success'] > 0]
            elif mode == "Bookmarks": 
                filtered_df = sub_df[sub_df['bookmarked'] == 1]

            if filtered_df.empty: 
                st.warning("⚠️ No cards matching criteria.")
            else:
                card = filtered_df.iloc[st.session_state.card_index % len(filtered_df)]
                st.info(f"**Question:** {card['key']}")
                if st.session_state.show_answer: 
                    st.success(f"**Answer:** {card['value']}")

                col1, col2, col3, col4 = st.columns(4)
                if not st.session_state.show_answer:
                    if col1.button("✅ Right"):
                        try:
                            with get_db_cursor() as cursor:
                                cursor.execute("UPDATE study_cards SET success = success + 1 WHERE id=?", (int(card['id']),))
                            clear_data_cache()
                            st.session_state.show_answer = True
                            st.rerun()
                        except Exception as e:
                            st.error(f"❌ Error updating: {str(e)}")
                    if col2.button("❌ Wrong"):
                        try:
                            with get_db_cursor() as cursor:
                                cursor.execute("UPDATE study_cards SET failure = failure + 1 WHERE id=?", (int(card['id']),))
                            clear_data_cache()
                            st.session_state.show_answer = True
                            st.rerun()
                        except Exception as e:
                            st.error(f"❌ Error updating: {str(e)}")
                else:
                    if col1.button("➡️ Next Card"): 
                        st.session_state.card_index += 1
                        st.session_state.show_answer = False
                        st.rerun()

                if col3.button("🔖 Bookmark"):
                    try:
                        new_val = 0 if card['bookmarked'] else 1
                        with get_db_cursor() as cursor:
                            cursor.execute("UPDATE study_cards SET bookmarked = ? WHERE id=?", (new_val, int(card['id'])))
                        clear_data_cache()
                        st.rerun()
                    except Exception as e:
                        st.error(f"❌ Error bookmarking: {str(e)}")
                if col4.button("⏭️ Skip"): 
                    st.session_state.card_index += 1
                    st.session_state.show_answer = False
                    st.rerun()

    with tabs[1]:  # BULK ADD
        st.subheader("Format: Question -!- Answer")
        bulk = st.text_area("Enter one Q&A per line", height=150)
        if st.button("🚀 Process"):
            if bulk.strip():
                try:
                    with get_db_cursor() as cursor:
                        for line in bulk.strip().split('\n'):
                            if "-!-" in line:
                                parts = line.split("-!-")
                                if len(parts) == 2:
                                    cursor.execute("INSERT INTO study_cards (topic, subtopic, key, value) VALUES (?,?,?,?)", 
                                                 (st.session_state.active_topic, st.session_state.active_subtopic, parts[0].strip(), parts[1].strip()))
                    clear_data_cache()
                    st.success("✅ Cards added!")
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ Error adding cards: {str(e)}")
            else:
                st.warning("⚠️ Please enter some content.")

    with tabs[2]:  # LOCAL DATA
        if sub_df.empty:
            st.info("ℹ️ No data to edit.")
        else:
            edited = st.data_editor(sub_df, use_container_width=True, num_rows="dynamic", key="sql_ed")
            if st.button("💾 Save Changes"):
                try:
                    with get_db_cursor() as cursor:
                        cursor.execute("DELETE FROM study_cards WHERE topic=? AND subtopic=?", 
                                     (st.session_state.active_topic, st.session_state.active_subtopic))
                        edited.to_sql('study_cards', cursor.connection, if_exists='append', index=False)
                    clear_data_cache()
                    st.success("✅ Changes saved!")
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ Error saving: {str(e)}")

    with tabs[3]:  # OVERVIEW
        if sub_df.empty:
            st.info("ℹ️ No data to display.")
        else:
            st.bar_chart(sub_df.set_index('key')[['success', 'failure']])
            if st.button("🗑️ Reset Stats"):
                try:
                    with get_db_cursor() as cursor:
                        cursor.execute("UPDATE study_cards SET success=0, failure=0 WHERE topic=? AND subtopic=?", 
                                     (st.session_state.active_topic, st.session_state.active_subtopic))
                    clear_data_cache()
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ Error resetting: {str(e)}")

    with tabs[4]:  # BOOKMARKS
        bookmarked = sub_df[sub_df['bookmarked'] == 1]
        if bookmarked.empty:
            st.info("ℹ️ No bookmarks yet.")
        else:
            st.table(bookmarked[['key', 'value']])

else:  # MASTER DATABASE
    st.title("🗂️ Master Database")
    if df_master.empty:
        st.info("ℹ️ Database is empty.")
    else:
        m_edited = st.data_editor(df_master, use_container_width=True, num_rows="dynamic")
        if st.button("💾 Save All"):
            try:
                with get_db_cursor() as cursor:
                    cursor.execute("DROP TABLE IF EXISTS study_cards")
                    cursor.execute('''CREATE TABLE study_cards 
                                     (id INTEGER PRIMARY KEY AUTOINCREMENT,
                                      topic TEXT, subtopic TEXT, key TEXT, value TEXT, 
                                      success INTEGER DEFAULT 0, failure INTEGER DEFAULT 0, 
                                      bookmarked BOOLEAN DEFAULT 0)''')
                    m_edited.to_sql('study_cards', cursor.connection, if_exists='append', index=False)
                clear_data_cache()
                st.success("✅ All changes saved!")
                st.rerun()
            except Exception as e:
                st.error(f"❌ Error saving: {str(e)}")
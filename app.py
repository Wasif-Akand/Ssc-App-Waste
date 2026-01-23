import streamlit as st
import pandas as pd
import sqlite3
import os
from contextlib import contextmanager
import numpy as np
from pathlib import Path

# ==========================================
# ⚙️ GLOBAL CONFIGURATION
# ==========================================
APP_NAME = "SSC ACADEMIC HUB"
APP_TAGLINE = "by £Akand~"
APP_VERSION = "v1.0.0"
APP_ICON = "⚡"
THEME_COLOR = "#00FFA3" 
BG_COLOR = "#050505"      

# Use cache directory for database (works on mobile)
CACHE_DIR = Path.home() / ".streamlit_cache"
CACHE_DIR.mkdir(exist_ok=True)
DB_FILE = "master_db.db"  # Use original location
CSV_BACKUP = "master_data.csv"
TOPIC_OPTIONS = ["Physics", "Chemistry", "Biology", "Higher Math", "General Math", "English", "ICT", "BGS"]

# ==========================================
# 1. SQL DATA ENGINE WITH CONNECTION POOLING
# ==========================================
@st.cache_resource
def get_connection():
    """Cached connection - works on mobile."""
    try:
        conn = sqlite3.connect(DB_FILE, check_same_thread=False, timeout=30.0)
        conn.execute('PRAGMA journal_mode=WAL')
        conn.execute('PRAGMA synchronous=NORMAL')
        conn.row_factory = sqlite3.Row
        return conn
    except Exception as e:
        st.error(f"❌ Database connection failed: {str(e)}")
        return None

@contextmanager
def get_db_cursor():
    """Context manager for safe database operations."""
    conn = get_connection()
    if conn is None:
        st.error("❌ Cannot connect to database")
        raise Exception("Database connection failed")
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
    """Initialize database once."""
    # Check if already initialized
    if 'db_initialized' in st.session_state:
        return
    
    try:
        conn = get_connection()
        if conn is None:
            return
        
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS study_cards 
                     (id INTEGER PRIMARY KEY AUTOINCREMENT,
                      topic TEXT, subtopic TEXT, key TEXT, value TEXT, 
                      success INTEGER DEFAULT 0, failure INTEGER DEFAULT 0, 
                      bookmarked BOOLEAN DEFAULT 0)''')
        conn.commit()
        st.session_state.db_initialized = True
        
        # Remove duplicates on startup
        try:
            df = pd.read_sql_query("SELECT * FROM study_cards", conn)
            if not df.empty:
                duplicates = df.duplicated(subset=['topic', 'subtopic', 'key'], keep='first')
                if duplicates.sum() > 0:
                    dup_ids = df[duplicates]['id'].tolist()
                    placeholders = ','.join('?' * len(dup_ids))
                    c.execute(f"DELETE FROM study_cards WHERE id IN ({placeholders})", dup_ids)
                    conn.commit()
                    st.warning(f"⚠️ Cleaned {len(dup_ids)} duplicates!")
        except Exception as e:
            st.warning(f"⚠️ Could not clean duplicates: {str(e)}")
            
    except Exception as e:
        st.error(f"❌ Database init error: {str(e)}")

# Initialize DB on app start
init_db()

@st.cache_data(ttl=300)
def load_all_data():
    """Load all data from database with caching (5 min TTL)."""
    try:
        conn = get_connection()
        if conn is None:
            return pd.DataFrame()
        df = pd.read_sql_query("SELECT * FROM study_cards ORDER BY id", conn)
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
if 'card_order' not in st.session_state:
    st.session_state.card_order = None  # Will store randomized card indices
if 'expanded_topic' not in st.session_state:
    st.session_state.expanded_topic = "Physics"  # Track which topic expands

# Force re-migration attempt
if 'old_db_migrated' not in st.session_state:
    st.session_state.old_db_migrated = False

# ==========================================
# 2. UI SETUP
# ==========================================
st.set_page_config(page_title=f"{APP_NAME} {APP_VERSION}", page_icon=APP_ICON, layout="wide", initial_sidebar_state="auto")
st.markdown(f"""
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=5.0">
    <style>
    * {{ margin: 0; padding: 0; box-sizing: border-box; }}
    html, body, .stApp {{ background-color: {BG_COLOR}; color: #E0E0E0; width: 100%; }}
    section[data-testid="stSidebar"] {{ background-color: #0A0A0A !important; border-right: 1px solid #222; }}
    .stButton > button {{ width: 100%; border-radius: 8px; background-color: transparent; border: 1px solid #444 !important; padding: 12px 10px !important; font-size: 14px; line-height: 1.5; display: flex; align-items: center; justify-content: center; }}
    .stButton > button > * {{ display: flex; align-items: center; justify-content: center; }}
    .stButton > button p {{ margin: 0; padding: 0; }}
    .stButton > button:hover {{ border-color: {THEME_COLOR} !important; color: {THEME_COLOR}; border: 1.5px solid {THEME_COLOR} !important; }}
    .stButton > button:focus {{ border: 1.5px solid {THEME_COLOR} !important; }}
    @media (max-width: 768px) {{
        .stApp {{ padding: 8px; }}
        .stButton > button {{ padding: 10px 8px !important; font-size: 12px; }}
        h1, h2, h3 {{ font-size: 16px !important; }}
        .stMetric {{ font-size: 12px; }}
        [data-testid="column"] {{ padding: 2px !important; }}
    }}
    </style>
""", unsafe_allow_html=True)

# ==========================================
# 3. SIDEBAR (CRUD OPERATIONS)
# ==========================================
with st.sidebar:
    st.title(f"{APP_ICON} {APP_NAME}")
    st.caption(f"{APP_TAGLINE} • {APP_VERSION}", help="Made by Wasif Akand")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("📖 Study Mode", use_container_width=True): 
            st.session_state.page = "Study Mode"
            st.rerun()
    with col2:
        if st.button("🗂️ Database", use_container_width=True): 
            st.session_state.page = "Master Database"
            st.rerun()
    st.divider()

    df_master = load_all_data()

    if st.session_state.page == "Study Mode":
        # ===== ADD NEW SUBTOPIC =====
        with st.expander("➕ **Add New Subtopic**", expanded=False):
            t_in = st.selectbox("Select Topic", TOPIC_OPTIONS, key="new_topic_select")
            s_in = st.text_input("Subtopic Name", placeholder="e.g., Motion & Forces").strip()
            if st.button("✅ Create", use_container_width=True):
                if s_in:
                    try:
                        with get_db_cursor() as cursor:
                            # Check if subtopic already exists
                            cursor.execute("SELECT COUNT(*) FROM study_cards WHERE topic=? AND subtopic=?", (t_in, s_in))
                            exists = cursor.fetchone()[0] > 0
                            
                            if exists:
                                st.warning(f"⚠️ Subtopic '{s_in}' already exists in {t_in}!")
                            else:
                                cursor.execute("INSERT INTO study_cards (topic, subtopic, key, value) VALUES (?,?,?,?)", 
                                             (t_in, s_in, "Definition", "Answer"))
                                clear_data_cache()
                                st.session_state.active_topic, st.session_state.active_subtopic = t_in, s_in
                                st.session_state.expanded_topic = t_in
                                st.success("✅ Subtopic created!")
                                st.rerun()
                    except Exception as e:
                        st.error(f"❌ Error: {str(e)}")
                else:
                    st.warning("⚠️ Please enter a subtopic name.")

        st.divider()

        # ===== SEARCH LIBRARY =====
        search_query = st.text_input("🔍 Search Subtopics", placeholder="Type to filter...").lower()

        st.subheader("📚 My Library")
        if df_master.empty:
            st.info("ℹ️ No topics yet. Create one above!")
        else:
            topics = sorted(df_master['topic'].unique())
            
            for t in topics:
                topic_cards = df_master[df_master['topic'] == t]
                subtopics = sorted(topic_cards['subtopic'].unique())
                
                # Filter by search
                filtered_subtopics = [s for s in subtopics if search_query in s.lower()]
                
                if not filtered_subtopics and search_query:
                    continue
                
                # Calculate topic stats
                topic_total = len(topic_cards)
                topic_success = topic_cards['success'].sum()
                topic_failure = topic_cards['failure'].sum()
                topic_accuracy = (topic_success / (topic_success + topic_failure) * 100) if (topic_success + topic_failure) > 0 else 0
                
                # Color code based on accuracy
                if topic_accuracy < 50 and (topic_success + topic_failure) > 0:
                    topic_color = "🔴"  # Weak
                elif topic_accuracy < 80 and (topic_success + topic_failure) > 0:
                    topic_color = "🟡"  # Medium
                else:
                    topic_color = "🟢"  # Strong
                
                # Auto-expand active topic
                is_active_topic = (st.session_state.active_topic == t)
                
                with st.expander(f"{topic_color} **{t}** ({topic_total})", expanded=is_active_topic):
                    for s in filtered_subtopics:
                        sub_cards = topic_cards[topic_cards['subtopic'] == s]
                        sub_total = len(sub_cards)
                        sub_success = sub_cards['success'].sum()
                        sub_failure = sub_cards['failure'].sum()
                        sub_accuracy = (sub_success / (sub_success + sub_failure) * 100) if (sub_success + sub_failure) > 0 else 0
                        
                        # Highlight active subtopic
                        is_active = (st.session_state.active_topic == t and st.session_state.active_subtopic == s)
                        
                        # Color code subtopic
                        if sub_accuracy < 50 and sub_total > 0:
                            sub_color = "🔴"
                        elif sub_accuracy < 80 and sub_total > 0:
                            sub_color = "🟡"
                        else:
                            sub_color = "🟢"
                        
                        # Layout - subtopic button with delete icon on right
                        col_main = st.columns([1])
                        
                        with col_main[0]:
                            # Active indicator
                            prefix = "→ " if is_active else "  "
                            
                            # Container for button and delete
                            inner_col1, inner_col2 = st.columns([19, 1])
                            
                            with inner_col1:
                                if st.button(
                                    f"{prefix}{sub_color} {s}\n({sub_total} cards) • ✅{int(sub_success)} • 📊{sub_accuracy:.0f}%", 
                                    key=f"nav_{t}_{s}",
                                    use_container_width=True,
                                    help=f"Accuracy: {sub_accuracy:.0f}%"
                                ):
                                    st.session_state.active_topic = t
                                    st.session_state.active_subtopic = s
                                    st.session_state.card_index = 0
                                    st.session_state.show_answer = False
                                    st.session_state.card_order = None  # Reset randomization
                                    st.session_state.expanded_topic = t
                                    st.rerun()
                            
                            with inner_col2:
                                if st.button("🗑️", key=f"del_{t}_{s}", help="Delete", use_container_width=True):
                                    st.session_state[f"confirm_delete_{t}_{s}"] = True
                        
                        # Confirmation dialog (outside button, no rerun)
                        if st.session_state.get(f"confirm_delete_{t}_{s}", False):
                            st.warning(f"⚠️ Really delete '{s}'? This cannot be undone!")
                            col_confirm1, col_confirm2 = st.columns(2)
                            with col_confirm1:
                                if st.button("✅ Yes, Delete", key=f"confirm_yes_{t}_{s}", use_container_width=True):
                                    try:
                                        with get_db_cursor() as cursor:
                                            cursor.execute("DELETE FROM study_cards WHERE topic=? AND subtopic=?", (t, s))
                                        clear_data_cache()
                                        st.session_state[f"confirm_delete_{t}_{s}"] = False
                                        st.success("✅ Deleted!")
                                        st.rerun()
                                    except Exception as e:
                                        st.error(f"❌ Error: {str(e)}")
                            with col_confirm2:
                                if st.button("❌ Cancel", key=f"confirm_no_{t}_{s}", use_container_width=True):
                                    st.session_state[f"confirm_delete_{t}_{s}"] = False
                                    st.rerun()

# ==========================================
# 4. MAIN INTERFACE
# ==========================================
df_master = load_all_data()

if st.session_state.page == "Study Mode":
    st.markdown(f"## {st.session_state.active_topic} : {st.session_state.active_subtopic}")
    st.markdown(f"<p style='text-align: right; font-size: 12px; color: #666;'>{APP_TAGLINE}</p>", unsafe_allow_html=True)
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
                # Initialize or regenerate random card order
                if st.session_state.card_order is None or len(st.session_state.card_order) != len(filtered_df):
                    st.session_state.card_order = np.random.permutation(len(filtered_df)).tolist()
                
                card_num = st.session_state.card_index % len(filtered_df)
                actual_index = st.session_state.card_order[card_num]
                card = filtered_df.iloc[actual_index]
                
                # ===== PROGRESS BAR =====
                progress_col1, progress_col2 = st.columns([3, 1])
                with progress_col1:
                    st.progress((card_num + 1) / len(filtered_df), text=f"Card {card_num + 1}/{len(filtered_df)}")
                with progress_col2:
                    st.metric("✅ Correct", int(card['success']))

                st.divider()

                # ===== FLASHCARD DISPLAY =====
                st.markdown(f"""
                    <style>
                    .flashcard-container {{
                        margin: 30px auto;
                        text-align: center;
                    }}
                    .flashcard {{
                        background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
                        border: 2px solid {THEME_COLOR};
                        border-radius: 15px;
                        padding: 50px 30px;
                        min-height: 300px;
                        display: flex;
                        flex-direction: column;
                        justify-content: center;
                        align-items: center;
                        box-shadow: 0 10px 40px rgba(0,255,163,0.1);
                        transition: all 0.3s ease;
                    }}
                    .card-label {{
                        font-size: 12px;
                        color: {THEME_COLOR};
                        text-transform: uppercase;
                        letter-spacing: 2px;
                        margin-bottom: 20px;
                        opacity: 0.7;
                    }}
                    .card-content {{
                        font-size: 28px;
                        color: #E0E0E0;
                        font-weight: 500;
                        line-height: 1.6;
                        word-wrap: break-word;
                    }}
                    .card-content-answer {{
                        color: {THEME_COLOR};
                        font-weight: 600;
                    }}
                    </style>
                    <div class="flashcard-container">
                        <div class="flashcard">
                            <div class="card-label">{"QUESTION" if not st.session_state.show_answer else "ANSWER"}</div>
                            <div class="card-content {"card-content-answer" if st.session_state.show_answer else ""}">{card['value'] if st.session_state.show_answer else card['key']}</div>
                        </div>
                    </div>
                """, unsafe_allow_html=True)

                # ===== FLIP BUTTON =====
                col_flip = st.columns([1, 2, 1])
                with col_flip[1]:
                    if not st.session_state.show_answer:
                        if st.button("👁️ Reveal Answer", use_container_width=True, key="reveal"):
                            st.session_state.show_answer = True
                            st.rerun()

                st.divider()

                # ===== ACTION BUTTONS =====
                if not st.session_state.show_answer:
                    # Before reveal - waiting to see answer
                    st.markdown("<p style='text-align: center; color: #888; font-size: 12px;'>Try to answer first, then reveal!</p>", unsafe_allow_html=True)
                else:
                    # After reveal - self-check and mark
                    st.markdown("<p style='text-align: center; color: #888; font-size: 12px;'>Did you get it right? Self-check now.</p>", unsafe_allow_html=True)
                    feedback_col1, feedback_col2, feedback_col3, feedback_col4 = st.columns(4)
                    
                    with feedback_col1:
                        if st.button("✅ Got it Right!", use_container_width=True, key="got_right"):
                            try:
                                with get_db_cursor() as cursor:
                                    cursor.execute("UPDATE study_cards SET success = success + 1 WHERE id=?", (int(card['id']),))
                                clear_data_cache()
                                st.session_state.card_index += 1
                                st.session_state.show_answer = False
                                st.rerun()
                            except Exception as e:
                                st.error(f"❌ Error: {str(e)}")
                    
                    with feedback_col2:
                        if st.button("❌ Got it Wrong", use_container_width=True, key="got_wrong"):
                            try:
                                with get_db_cursor() as cursor:
                                    cursor.execute("UPDATE study_cards SET failure = failure + 1 WHERE id=?", (int(card['id']),))
                                clear_data_cache()
                                st.session_state.card_index += 1
                                st.session_state.show_answer = False
                                st.rerun()
                            except Exception as e:
                                st.error(f"❌ Error: {str(e)}")
                    
                    with feedback_col3:
                        bookmark_icon = "💛" if card['bookmarked'] else "🤍"
                        if st.button(f"{bookmark_icon} Bookmark", use_container_width=True, key="bookmark_ans"):
                            try:
                                new_val = 0 if card['bookmarked'] else 1
                                with get_db_cursor() as cursor:
                                    cursor.execute("UPDATE study_cards SET bookmarked = ? WHERE id=?", (new_val, int(card['id'])))
                                clear_data_cache()
                                st.rerun()
                            except Exception as e:
                                st.error(f"❌ Error bookmarking: {str(e)}")
                    
                    with feedback_col4:
                        if st.button("⏭️ Skip", use_container_width=True, key="skip_ans"):
                            st.session_state.card_index += 1
                            st.session_state.show_answer = False
                            st.rerun()
                
                # ===== STATS BAR =====
                st.divider()
                stats_col1, stats_col2, stats_col3 = st.columns(3)
                with stats_col1:
                    st.metric("📌 Bookmarked", len(sub_df[sub_df['bookmarked'] == 1]))
                with stats_col2:
                    st.metric("❌ Need Help", len(filtered_df[filtered_df['failure'] > 0]))
                with stats_col3:
                    accuracy = (int(card['success']) / (int(card['success']) + int(card['failure'])) * 100) if (int(card['success']) + int(card['failure'])) > 0 else 0
                    st.metric("📊 Accuracy", f"{accuracy:.0f}%")

    with tabs[1]:  # BULK ADD
        st.subheader("Format: Question -!- Answer")
        bulk = st.text_area("Enter one Q&A per line", height=150)
        if st.button("🚀 Process"):
            if bulk.strip():
                try:
                    added = 0
                    skipped = 0
                    with get_db_cursor() as cursor:
                        for line in bulk.strip().split('\n'):
                            if "-!-" in line:
                                parts = line.split("-!-")
                                if len(parts) == 2:
                                    q = parts[0].strip()
                                    a = parts[1].strip()
                                    
                                    # Check if this card already exists
                                    cursor.execute("SELECT COUNT(*) FROM study_cards WHERE topic=? AND subtopic=? AND key=?", 
                                                 (st.session_state.active_topic, st.session_state.active_subtopic, q))
                                    exists = cursor.fetchone()[0] > 0
                                    
                                    if exists:
                                        skipped += 1
                                    else:
                                        cursor.execute("INSERT INTO study_cards (topic, subtopic, key, value) VALUES (?,?,?,?)", 
                                                     (st.session_state.active_topic, st.session_state.active_subtopic, q, a))
                                        added += 1
                    
                    clear_data_cache()
                    if added > 0:
                        st.success(f"✅ Added {added} cards!")
                    if skipped > 0:
                        st.warning(f"⚠️ Skipped {skipped} duplicates")
                    if added > 0 or skipped > 0:
                        st.rerun()
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
    st.markdown(f"<p style='text-align: right; font-size: 12px; color: #666;'>{APP_TAGLINE}</p>", unsafe_allow_html=True)
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

# ==========================================
# FOOTER
# ==========================================
st.divider()
st.markdown(f"""
    <div style='text-align: center; color: #666; font-size: 12px; padding: 20px 0;'>
        <p>⚡ <strong>{APP_NAME}</strong> {APP_VERSION}</p>
        <p>Created by <strong>Wasif Akand</strong> • {APP_TAGLINE}</p>
        <p style='margin-top: 10px; opacity: 0.7;'>Study smarter, not harder • Made with ❤️</p>
    </div>
""", unsafe_allow_html=True)
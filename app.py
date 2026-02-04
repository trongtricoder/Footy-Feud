import streamlit as st
import time
import random
import uuid
import extra_streamlit_components as stx
from datetime import date
from src.utils import load_players, get_random_player

# --- 1. FIREBASE & PERISTENCE CONFIG ---
def get_manager():
    if "cookie_manager" not in st.session_state:
        st.session_state.cookie_manager = stx.CookieManager()
    return st.session_state.cookie_manager

def get_user_id():
    cookie_manager = get_manager()
    
    # 1. Give the browser a moment to send cookies (Streamlit is fast!)
    # We loop a few times to give the component time to "handshake"
    retries = 5
    uuid_cookie = None
    while retries > 0 and uuid_cookie is None:
        uuid_cookie = cookie_manager.get("footyfeud_uid")
        if uuid_cookie:
            break
        time.sleep(0.1) # Small pause
        retries -= 1

    if uuid_cookie:
        st.session_state.user_id = uuid_cookie
    else:
        # 2. ONLY if we checked 5 times and found nothing, we make a new one
        new_id = str(uuid.uuid4())[:8]
        # We use a key that Streamlit won't refresh easily
        cookie_manager.set("footyfeud_uid", new_id, expires_at=date(2030, 1, 1))
        st.session_state.user_id = new_id
        
    return st.session_state.user_id

def init_db():
    if "db" not in st.session_state:
        try:
            from google.cloud import firestore
            from google.oauth2 import service_account
            import json

            if "firebase" in st.secrets:
                raw_key = st.secrets["firebase"]["textkey"]
                raw_key = raw_key.strip()
                
                key_dict = json.loads(raw_key)
                creds = service_account.Credentials.from_service_account_info(key_dict)
                st.session_state.db = firestore.Client(credentials=creds)
            else:
                print("Error: [firebase] section not found in secrets!")
                st.session_state.db = None
        except Exception as e:
            print(f"🔥 Firebase Connection Failed: {e}")
            st.session_state.db = None

def load_stats():
    user_id = st.session_state.user_id
    if st.session_state.db:
        doc = st.session_state.db.collection("users").document(user_id).get()
        if doc.exists:
            data = doc.to_dict()
            
            # 1. Restore the distribution stats (ints as keys)
            for mode in ['daily', 'random']:
                if mode in data:
                    data[mode]['distribution'] = {int(k): v for k, v in data[mode].get('distribution', {}).items()}
            
            # 2. Restore Guesses (if they exist for the current daily game)
            # We only restore guesses if the date matches today
            if data.get('daily', {}).get('last_played_date') == str(date.today()):
                st.session_state.guesses = data.get('current_guesses', [])
                # If they already finished, ensure game_over is set
                if len(st.session_state.guesses) >= 6 or (
                    len(st.session_state.guesses) > 0 and 
                    st.session_state.guesses[-1]['name'] == data.get('secret_name_for_day')
                ):
                    st.session_state.game_over = True
            
            return data
            
    # Default Stats Structure if no user found
    return {
        "daily": {
            "played": 0, "won": 0, "current_streak": 0, "max_streak": 0,
            "distribution": {i: 0 for i in range(1, 7)},
            "last_played_date": None
        },
        "random": {
            "played": 0, "won": 0, "current_streak": 0,
            "distribution": {i: 0 for i in range(1, 7)}
        }
    }

def save_stats():
    if st.session_state.db and "user_id" in st.session_state:
        user_id = st.session_state.user_id
        save_data = {}
        for mode in ['daily', 'random']:
            save_data[mode] = st.session_state.stats[mode].copy()
            # Convert keys to strings for Firestore
            save_data[mode]['distribution'] = {str(k): v for k, v in save_data[mode]['distribution'].items()}
        
        # ADD THIS: Save the current session's guesses so they persist!
        # Add to the existing save_data block
        save_data['current_guesses'] = st.session_state.guesses
        if st.session_state.game_mode == "Daily":
            save_data['secret_name_for_day'] = st.session_state.secret_player['name']
        save_data['last_mode'] = st.session_state.game_mode
        
        st.session_state.db.collection("users").document(user_id).set(save_data)

# --- 2. GAME INITIALIZATION ---
init_db()
cookie_manager = get_manager()

# 1. Aggressive Cookie Handshake
if 'user_id' not in st.session_state:
    # IMPORTANT: We use a placeholder to tell the app "We are waiting, don't make a new ID yet"
    uid = None
    
    # Increase wait time and retries for slower connections
    with st.spinner("Connecting to your profile..."):
        for i in range(15):  # Try for 1.5 seconds
            uid = cookie_manager.get("footyfeud_uid")
            if uid:
                break
            time.sleep(0.1)
        
        # ONLY if after 1.5s we definitely have no cookie, we create a new one
        if not uid:
            # Check one last time to be absolutely sure
            uid = cookie_manager.get("footyfeud_uid")
            if not uid:
                import uuid
                uid = str(uuid.uuid4())[:8]
                # Set the cookie with a long expiry
                cookie_manager.set("footyfeud_uid", uid, expires_at=date(2030, 1, 1))
        
        st.session_state.user_id = uid
        # Force a small rerun here to ensure the ID is locked into state before stats load
        st.rerun()

# 2. Once ID is locked, load stats and RESTORE game state
if 'user_id' in st.session_state and 'stats' not in st.session_state:
    data = load_stats()
    st.session_state.stats = data
    
    # Restore Progress
    if data.get('daily', {}).get('last_played_date') == str(date.today()):
        if st.session_state.get('game_mode') is None:
            st.session_state.game_mode = "Daily"
            st.session_state.guesses = data.get('current_guesses', [])
            
            # Re-check win/loss state
            secret_name = data.get('secret_name_for_day')
            if len(st.session_state.guesses) >= 6 or (
                len(st.session_state.guesses) > 0 and 
                st.session_state.guesses[-1]['name'] == secret_name
            ):
                st.session_state.game_over = True

# 3. Flags
if 'has_seen_help' not in st.session_state:
    st.session_state.has_seen_help = False
if 'game_mode' not in st.session_state:
    st.session_state.game_mode = None

# --- 3. HELPER FUNCTIONS ---

def show_stats_dashboard():
    st.markdown("---")
    mode_key = st.session_state.game_mode.lower()
    s = st.session_state.stats[mode_key]
    
    st.subheader(f"📊 {st.session_state.game_mode} Summary")
    
    cols = st.columns(4)
    win_rate = int((s["won"] / s["played"] * 100)) if s["played"] > 0 else 0
    cols[0].metric("Played", s["played"])
    cols[1].metric("Win %", f"{win_rate}%")
    cols[2].metric("Streak", s["current_streak"])
    if mode_key == "daily":
        cols[3].metric("Best Streak", s["max_streak"])

    st.write("**Guess Distribution**")
    dist = s["distribution"]
    max_val = max(dist.values()) if max(dist.values()) > 0 else 1
    chart_cols = st.columns(6)
    
    for i in range(1, 7):
        count = dist[i]
        bar_height = int((count / max_val) * 100) if count > 0 else 0
        is_current = (st.session_state.game_over and len(st.session_state.guesses) == i and 
                      st.session_state.guesses[-1]['name'] == st.session_state.secret_player['name'])
        color = "#28a745" if is_current else "#555"
        
        with chart_cols[i-1]:
            st.markdown(f"""
                <div style="display: flex; flex-direction: column; align-items: center; height: 130px; justify-content: flex-end;">
                    <div style="font-size: 0.8em; margin-bottom: 5px; font-weight: bold;">{count}</div>
                    <div style="background-color: {color}; width: 25px; height: {max(bar_height, 5)}%; border-radius: 4px 4px 0 0;"></div>
                    <div style="border-top: 1px solid #888; width: 100%; text-align: center; padding-top: 5px; font-weight: bold;">{i}</div>
                </div>
            """, unsafe_allow_html=True)
    st.write("")

def display_player_reveal(image_url, won):
    placeholder = "https://cdn-icons-png.flaticon.com/512/2102/2102633.png"
    img_src = image_url if image_url and image_url != "" else placeholder
    filter_style = "filter: brightness(1) grayscale(0%);" if won else "filter: brightness(0); opacity: 0.6;"
    bg_color = "#28a745" if won else "#222"

    st.markdown(f"""
        <div style="display: flex; justify-content: center; margin-bottom: 25px;">
            <div style="width: 160px; height: 160px; border-radius: 50%; overflow: hidden; background-color: {bg_color};
                border: 3px solid rgba(255,255,255,0.1); display: flex; justify-content: center; align-items: center;">
                <img src="{img_src}" style="width: 80%; height: 80%; object-fit: contain; {filter_style}">
            </div>
        </div>
    """, unsafe_allow_html=True)

def attribute_box(label, value, color_code, show_label=True):
    label_opacity = "0.8" if show_label else "0"
    st.markdown(f"""
        <div style="background-color: {color_code}; padding: 10px; border-radius: 8px; text-align: center; color: white; 
            margin-bottom: 10px; border: 1px solid rgba(255,255,255,0.1); min-height: 105px; display: flex; 
            flex-direction: column; justify-content: center;">
            <small style="opacity: {label_opacity}; font-size: 0.75em; margin-bottom: 5px; display: block;">{label}</small>
            <strong style="font-size: 0.9em; display: block; line-height: 1.2;">{value}</strong>
        </div>
    """, unsafe_allow_html=True)

@st.dialog("📖 How to Play")
def help_modal():
    st.write("### How to Play\nGuess the footballer in 6 tries! Silhouette clears as you guess.")
    st.write("- **Green (🟩)**: Exact match.\n- **Yellow (🟨)**: Age within 2 years.\n- **Arrows**: Mystery player is older (↑) or younger (↓).")
    if st.button("Close"): st.rerun()

def reset_to_menu():
    for key in ['secret_player', 'guesses', 'game_over', 'game_mode']:
        if key in st.session_state: del st.session_state[key]
    st.rerun()

def play_another_random():
    st.session_state.secret_player = get_random_player(st.session_state.all_players)
    st.session_state.guesses = []
    st.session_state.game_over = False
    st.rerun()

def handle_guess():
    selected = st.session_state.player_selector
    if selected and not st.session_state.game_over:
        guessed_player = next(p for p in st.session_state.all_players if p["name"] == selected)
        if guessed_player['name'] not in [g['name'] for g in st.session_state.guesses]:
            guessed_player['is_new'] = True
            st.session_state.guesses.append(guessed_player)
            
            mode = st.session_state.game_mode.lower()
            
            # WIN
            if guessed_player['name'] == st.session_state.secret_player['name']:
                st.session_state.game_over = True
                st.session_state.stats[mode]["played"] += 1
                st.session_state.stats[mode]["won"] += 1
                st.session_state.stats[mode]["current_streak"] += 1
                st.session_state.stats[mode]["distribution"][len(st.session_state.guesses)] += 1
                if mode == "daily":
                    st.session_state.stats[mode]["last_played_date"] = str(date.today())
                    if st.session_state.stats[mode]["current_streak"] > st.session_state.stats[mode]["max_streak"]:
                        st.session_state.stats[mode]["max_streak"] = st.session_state.stats[mode]["current_streak"]
                save_stats()
            # LOSS
            elif len(st.session_state.guesses) >= 6:
                st.session_state.game_over = True
                st.session_state.stats[mode]["played"] += 1
                st.session_state.stats[mode]["current_streak"] = 0
                if mode == "daily":
                    st.session_state.stats[mode]["last_played_date"] = str(date.today())
                save_stats()
        st.session_state.player_selector = ""

# --- 4. UI LAYOUT ---
if "last_checked_date" not in st.session_state:
    st.session_state.last_checked_date = date.today()

if st.session_state.last_checked_date != date.today():
    st.session_state.last_checked_date = date.today()
    # Force a reset of the daily game state for the new day
    if st.session_state.get('game_mode') == "Daily":
        for key in ['secret_player', 'guesses', 'game_over']:
            if key in st.session_state: del st.session_state[key]
    st.rerun()

h_col1, h_col2 = st.columns([0.85, 0.15])
with h_col1: st.title("⚽ FootyFeud")
with h_col2: 
    if st.button("❓"): help_modal()

if not st.session_state.has_seen_help:
    st.subheader("Welcome to FootyFeud! 🏆")
    if st.button("Let's Play!", use_container_width=True):
        st.session_state.has_seen_help = True
        st.rerun()

elif st.session_state.game_mode is None:
    st.subheader("Choose your challenge:")
    m_col1, m_col2 = st.columns(2)
    with m_col1:
        if st.button("📅 Daily Challenge", use_container_width=True):
            st.session_state.game_mode = "Daily"
            st.rerun()
    with m_col2:
        if st.button("🎲 Random Mode", use_container_width=True):
            st.session_state.game_mode = "Random"
            st.rerun()

else:
    # --- SAFETY CHECK: Initialize mode-specific data before rendering UI ---
    if 'all_players' not in st.session_state:
        st.session_state.all_players = load_players()

    if 'secret_player' not in st.session_state or st.session_state.secret_player is None:
        if st.session_state.game_mode == "Daily":
            # --- SEEDING LOGIC: Same player for everyone today ---
            today_seed = int(date.today().strftime("%Y%m%d"))
            random.seed(today_seed)
            st.session_state.secret_player = random.choice(st.session_state.all_players)
            random.seed() # Reset seed so Random Mode stays random
        else:
            # Logic for Random: Pick any player
            st.session_state.secret_player = get_random_player(st.session_state.all_players)
        
        # Ensure guesses are ready
        if 'guesses' not in st.session_state:
            st.session_state.guesses = []
        if 'game_over' not in st.session_state:
            st.session_state.game_over = False

    # --- GAMEPLAY ---
    st.caption(f"Mode: {st.session_state.game_mode} | Guess: {len(st.session_state.guesses)}/6")
    
    # Calculate win state safely
    is_win = (len(st.session_state.guesses) > 0 and 
              st.session_state.guesses[-1]['name'] == st.session_state.secret_player['name'])
    
    display_player_reveal(st.session_state.secret_player['img_url'], is_win)

    # LOCK CHECK FOR DAILY
    if st.session_state.game_mode == "Daily" and st.session_state.stats["daily"]["last_played_date"] == str(date.today()):
        st.info("Daily Challenge completed! See you tomorrow.")
        show_stats_dashboard()
        if st.button("🏠 Menu", use_container_width=True): reset_to_menu()
    else:
        # SEARCH INPUT
        player_names = [""] + [p["name"] for p in st.session_state.all_players]
        st.selectbox("Search player:", options=player_names, key="player_selector", on_change=handle_guess, disabled=st.session_state.game_over)

        if st.session_state.game_over:
            if is_win:
                st.balloons()
                st.success(f"GOAL! It was {st.session_state.secret_player['name']}!")
            else:
                st.error(f"HARD LUCK! It was {st.session_state.secret_player['name']}.")
            
            show_stats_dashboard()
            
            e_col1, e_col2 = st.columns(2)
            with e_col1:
                if st.button("🏠 Menu", use_container_width=True): reset_to_menu()
            with e_col2:
                if st.button("🔄 Next Round", use_container_width=True):
                    if st.session_state.game_mode == "Random": 
                        play_another_random()
                    else: 
                        reset_to_menu()

    # --- GUESS GRID ---
    if st.session_state.guesses:
        secret = st.session_state.secret_player
        for i, guess in enumerate(reversed(st.session_state.guesses)):
            if i == 0: st.write("### Latest Guess")
            elif i == 1: st.write("### History")
            
            cols = st.columns(5)
            items = [
                ("Nationality", guess['nationality'], "#28a745" if guess['nationality'] == secret['nationality'] else "#dc3545"),
                ("League", guess['league'], "#28a745" if guess['league'] == secret['league'] else "#dc3545"),
                ("Club", guess['club'], "#28a745" if guess['club'] == secret['club'] else "#dc3545"),
                ("Position", guess['position'], "#28a745" if guess['position'] == secret['position'] else "#dc3545"),
                ("Age", f"{guess['age']} {'↑' if guess['age'] < secret['age'] else '↓' if guess['age'] > secret['age'] else ''}", 
                 "#28a745" if guess['age'] == secret['age'] else "#ffc107" if abs(guess['age'] - secret['age']) <= 2 else "#dc3545")
            ]
            for j, (label, val, color) in enumerate(items):
                with cols[j]: attribute_box(label, val, color, show_label=(i == 0))
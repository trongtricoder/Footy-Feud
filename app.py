import streamlit as st
import streamlit.components.v1 as components
import time
import random
from datetime import date, datetime, timedelta
from src.utils import load_players, get_random_player
from src.auth_streamlit import AuthManager

# --- 1. FIREBASE & AUTHENTICATION CONFIG ---
def init_db():
    """Initialize Firestore connection"""
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
                st.session_state.auth_manager = AuthManager(st.session_state.db)
            else:
                print("Error: [firebase] section not found in secrets!")
                st.session_state.db = None
                st.session_state.auth_manager = None
        except Exception as e:
            print(f"🔥 Firebase Connection Failed: {e}")
            st.session_state.db = None
            st.session_state.auth_manager = None

def load_user_stats(user_id):
    """Load stats for authenticated user"""
    if st.session_state.db and st.session_state.auth_manager:
        user_data = st.session_state.auth_manager.get_user_by_id(user_id)
        if user_data:
            # Extract just the stats portion
            stats = {
                'daily': user_data.get('daily', {
                    "played": 0, "won": 0, "current_streak": 0, "max_streak": 0,
                    "distribution": {str(i): 0 for i in range(1, 7)},
                    "last_played_date": None
                }),
                'random': user_data.get('random', {
                    "played": 0, "won": 0, "current_streak": 0,
                    "distribution": {str(i): 0 for i in range(1, 7)}
                })
            }
            # Convert distribution keys to int
            for mode in ['daily', 'random']:
                stats[mode]['distribution'] = {int(k): v for k, v in stats[mode]['distribution'].items()}
            return stats
    
    # Default stats if DB unavailable
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
    """Save stats for authenticated user"""
    if st.session_state.db and st.session_state.auth_manager and 'user_id' in st.session_state:
        for mode in ['daily', 'random']:
            mode_data = st.session_state.stats[mode].copy()
            # Convert int keys to strings for Firestore
            mode_data['distribution'] = {str(k): v for k, v in mode_data['distribution'].items()}
            st.session_state.auth_manager.update_user_stats(
                st.session_state.user_id,
                mode,
                mode_data
            )

def check_and_fix_streak():
    """Reset streak if user missed playing yesterday"""
    last_played = st.session_state.stats["daily"]["last_played_date"]
    
    if last_played:
        try:
            last_date = datetime.strptime(last_played, "%Y-%m-%d").date()
            today = date.today()
            yesterday = today - timedelta(days=1)
            
            # If last played was NOT yesterday and NOT today, reset streak to 0
            if last_date != yesterday and last_date != today:
                if st.session_state.stats["daily"]["current_streak"] > 0:
                    st.session_state.stats["daily"]["current_streak"] = 0
                    # Save the fixed streak to database
                    save_stats()
        except Exception as e:
            print(f"Error checking streak: {e}")

def save_session_to_localstorage(user_id):
    """Save session to localStorage for cross-tab persistence"""
    components.html(f"""
        <script>
            localStorage.setItem('footyfeud_uid', '{user_id}');
            // Also update URL
            if (!window.location.search.includes('uid=')) {{
                const url = new URL(window.location);
                url.searchParams.set('uid', '{user_id}');
                window.history.replaceState({{}}, '', url);
            }}
        </script>
    """, height=0)

def get_session_from_localstorage():
    """Try to retrieve session from localStorage"""
    uid = components.html("""
        <script>
            const uid = localStorage.getItem('footyfeud_uid');
            if (uid) {
                window.parent.postMessage({type: 'streamlit:setComponentValue', value: uid}, '*');
            }
        </script>
    """, height=0)
    return uid

def clear_session_from_localstorage():
    """Clear session from localStorage on logout"""
    components.html("""
        <script>
            localStorage.removeItem('footyfeud_uid');
        </script>
    """, height=0)

# --- 2. AUTHENTICATION UI ---
def show_login_page():
    """Display login/signup page"""
    st.title("⚽ FootyFeud")
    st.markdown("### Welcome! Please login or create an account")
    
    tab1, tab2 = st.tabs(["Login", "Sign Up"])
    
    with tab1:
        st.markdown("#### Login to your account")
        with st.form("login_form"):
            username = st.text_input("Username", key="login_username")
            password = st.text_input("Password", type="password", key="login_password")
            submit = st.form_submit_button("Login", use_container_width=True)
            
            if submit:
                if not username or not password:
                    st.error("Please enter both username and password")
                else:
                    success, message, user_data = st.session_state.auth_manager.authenticate_user(
                        username, password
                    )
                    
                    if success:
                        st.session_state.authenticated = True
                        st.session_state.user_id = user_data['user_id']
                        st.session_state.username = user_data['username']
                        st.session_state.stats = load_user_stats(user_data['user_id'])
                        
                        # Save session in URL AND localStorage
                        st.query_params["uid"] = user_data['user_id']
                        save_session_to_localstorage(user_data['user_id'])
                        
                        st.success(message)
                        time.sleep(0.5)
                        st.rerun()
                    else:
                        st.error(message)
    
    with tab2:
        st.markdown("#### Create a new account")
        with st.form("signup_form"):
            new_username = st.text_input("Username", key="signup_username")
            st.caption("3-20 characters, letters, numbers, _ and - only")
            new_password = st.text_input("Password", type="password", key="signup_password")
            st.caption("Minimum 6 characters")
            confirm_password = st.text_input("Confirm Password", type="password", key="confirm_password")
            submit = st.form_submit_button("Create Account", use_container_width=True)
            
            if submit:
                if not new_username or not new_password:
                    st.error("Please fill in all fields")
                elif new_password != confirm_password:
                    st.error("Passwords do not match")
                else:
                    success, message, user_id = st.session_state.auth_manager.create_user(
                        new_username, new_password
                    )
                    
                    if success:
                        st.session_state.authenticated = True
                        st.session_state.user_id = user_id
                        st.session_state.username = new_username
                        st.session_state.stats = load_user_stats(user_id)
                        
                        # Save session in URL AND localStorage
                        st.query_params["uid"] = user_id
                        save_session_to_localstorage(user_id)
                        
                        st.success(message)
                        time.sleep(0.5)
                        st.rerun()
                    else:
                        st.error(message)

# --- 3. AUTO-LOGIN & GAME INITIALIZATION ---
init_db()

# Check authentication
if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False

# Try auto-login from URL query params OR localStorage
if not st.session_state.authenticated:
    saved_user_id = st.query_params.get("uid")
    
    # If no UID in URL, try localStorage
    if not saved_user_id:
        saved_user_id = get_session_from_localstorage()
        if saved_user_id:
            # Update URL with the UID from localStorage
            st.query_params["uid"] = saved_user_id
    
    if saved_user_id and st.session_state.db and st.session_state.auth_manager:
        # Validate saved user ID
        user_data = st.session_state.auth_manager.get_user_by_id(saved_user_id)
        if user_data:
            # Auto-login successful!
            st.session_state.authenticated = True
            st.session_state.user_id = user_data['user_id']
            st.session_state.username = user_data['username']
            st.session_state.stats = load_user_stats(user_data['user_id'])
            # Make sure session is saved
            save_session_to_localstorage(user_data['user_id'])

# If not authenticated and DB is available, show login
if not st.session_state.authenticated:
    if st.session_state.db and st.session_state.auth_manager:
        show_login_page()
        st.stop()
    else:
        st.error("Database connection failed. Please contact support.")
        st.stop()

# Load user stats if not loaded
if 'stats' not in st.session_state:
    st.session_state.stats = load_user_stats(st.session_state.user_id)

# Fix streak: Check if user missed days on Daily mode
# Run streak check once per session
if 'streak_checked' not in st.session_state:
    check_and_fix_streak()
    st.session_state.streak_checked = True

if 'has_seen_help' not in st.session_state:
    st.session_state.has_seen_help = False

if 'game_mode' not in st.session_state:
    st.session_state.game_mode = None

if st.session_state.game_mode and 'secret_player' not in st.session_state:
    players = load_players()
    st.session_state.all_players = players
    
    if st.session_state.game_mode == "Daily":
        random.seed(date.today().toordinal())
        st.session_state.secret_player = get_random_player(players)
        random.seed() 
        # Check if already played today
        if st.session_state.stats["daily"]["last_played_date"] == str(date.today()):
            st.session_state.game_over = True
            st.session_state.guesses = [] 
        else:
            st.session_state.guesses = []
            st.session_state.game_over = False
    else:
        st.session_state.secret_player = get_random_player(players)
        st.session_state.guesses = []
        st.session_state.game_over = False

# --- 4. HELPER FUNCTIONS ---

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

def attribute_box(label, value, color_code, show_label=True, animation_delay=0):
    label_opacity = "0.8" if show_label else "0"
    st.markdown(f"""
        <style>
        @keyframes slideIn {{
            from {{
                opacity: 0;
                transform: translateX(-20px);
            }}
            to {{
                opacity: 1;
                transform: translateX(0);
            }}
        }}
        </style>
        <div style="background-color: {color_code}; padding: 10px; border-radius: 8px; text-align: center; color: white; 
            margin-bottom: 10px; border: 1px solid rgba(255,255,255,0.1); min-height: 105px; display: flex; 
            flex-direction: column; justify-content: center;
            animation: slideIn 0.4s ease-out {animation_delay}s both;">
            <small style="opacity: {label_opacity}; font-size: 0.75em; margin-bottom: 5px; display: block;">{label}</small>
            <strong style="font-size: 0.9em; display: block; line-height: 1.2;">{value}</strong>
        </div>
    """, unsafe_allow_html=True)

@st.dialog("📖 How to Play")
def help_modal():
    st.write("### How to Play\nGuess the footballer in 6 tries! Silhouette clears as you guess.")
    st.write("- **Green (🟩)**: Exact match.\n- **Yellow (🟨)**: Age within 2 years.\n- **Arrows**: Mystery player is older (↑) or younger (↓).")
    if st.button("Close"): st.rerun()

def logout():
    """Logout user"""
    # Clear localStorage
    clear_session_from_localstorage()
    # Clear the session from URL
    st.query_params.clear()
    # Clear all session state
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.rerun()

def reset_to_menu():
    for key in ['secret_player', 'guesses', 'game_over', 'game_mode', 'search_results', 'last_search_term']:
        if key in st.session_state: del st.session_state[key]
    st.rerun()

def play_another_random():
    for key in ['secret_player', 'guesses', 'game_over', 'search_results', 'last_search_term']:
        if key in st.session_state: del st.session_state[key]
    st.session_state.secret_player = get_random_player(st.session_state.all_players)
    st.session_state.guesses = []
    st.session_state.game_over = False
    st.rerun()

# --- 5. UI LAYOUT ---
# Header with username and logout
col1, col2, col3 = st.columns([0.6, 0.3, 0.1], vertical_alignment="bottom")
with col1: 
    st.title("⚽ FootyFeud")
with col2:
    if st.session_state.get('authenticated'):
        st.caption(f"👤 {st.session_state.get('username', '')}")
with col3: 
    if st.button("❓"): 
        help_modal()

# Logout button in sidebar
with st.sidebar:
    st.markdown("### Account")
    st.write(f"**{st.session_state.get('username', '')}**")
    if st.button("🚪 Logout", use_container_width=True):
        logout()

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
    # --- GAMEPLAY ---
    st.caption(f"Mode: {st.session_state.game_mode} | Guess: {len(st.session_state.guesses)}/6")
    
    is_win = len(st.session_state.guesses) > 0 and st.session_state.guesses[-1]['name'] == st.session_state.secret_player['name']
    display_player_reveal(st.session_state.secret_player['img_url'], is_win)

    # LOCK CHECK FOR DAILY
    if st.session_state.game_mode == "Daily" and st.session_state.stats["daily"]["last_played_date"] == str(date.today()):
        st.info("Daily Challenge completed! See you tomorrow.")
        show_stats_dashboard()
        if st.button("🏠 Menu", use_container_width=True): reset_to_menu()
    else:
        # SINGLE AUTOCOMPLETE SEARCH with randomized 10 results
        # Initialize search results
        if 'search_results' not in st.session_state:
            # Start with 10 random players
            st.session_state.search_results = random.sample(st.session_state.all_players, 
                                                           min(10, len(st.session_state.all_players)))
            st.session_state.last_search_term = ""
        
        # Single selectbox with type-to-search functionality
        def update_search_results():
            """Update search results based on selectbox selection"""
            selected = st.session_state.player_search_box
            
            # Check if this is a search term (user typing) or a selection
            if selected and selected not in ["🔍 Type to search...", "No results found"]:
                # User selected a player
                guessed_player = next((p for p in st.session_state.all_players if p["name"] == selected), None)
                
                if guessed_player and not st.session_state.game_over:
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
                        
                        # Reset search after guess
                        st.session_state.search_results = random.sample(st.session_state.all_players, 
                                                                       min(10, len(st.session_state.all_players)))
                        st.session_state.last_search_term = ""
        
        # Text input for filtering
        search_term = st.text_input(
            "🔍 Type player name to filter:",
            value="",
            placeholder="e.g. Haaland, Messi, Ronaldo...",
            key="search_filter_input",
            disabled=st.session_state.game_over
        )
        
        # Update results if search changed
        if search_term != st.session_state.last_search_term:
            if search_term:
                # Filter and randomize
                filtered = [p for p in st.session_state.all_players 
                           if search_term.lower() in p['name'].lower()]
                if filtered:
                    random.shuffle(filtered)
                    st.session_state.search_results = filtered[:10]
                else:
                    st.session_state.search_results = []
            else:
                # No search term - show 10 random
                st.session_state.search_results = random.sample(st.session_state.all_players, 
                                                               min(10, len(st.session_state.all_players)))
            
            st.session_state.last_search_term = search_term
        
        # Show results count
        if st.session_state.search_results:
            result_count = len(st.session_state.search_results)
            all_filtered = [p for p in st.session_state.all_players 
                           if search_term.lower() in p['name'].lower()] if search_term else st.session_state.all_players
            
            if search_term:
                if len(all_filtered) > 10:
                    st.caption(f"✨ Showing 10 random results from {len(all_filtered)} matches")
                else:
                    st.caption(f"✨ {result_count} result{'s' if result_count != 1 else ''} found")
            else:
                st.caption("🎲 10 random players (start typing to filter)")
            
            # Selectbox with results
            player_options = ["Select a player..."] + [p['name'] for p in st.session_state.search_results]
        else:
            st.caption("❌ No players found")
            player_options = ["No results found"]
        
        selected_player = st.selectbox(
            "Choose from results:",
            options=player_options,
            key="player_search_box",
            on_change=update_search_results,
            disabled=st.session_state.game_over,
            label_visibility="collapsed"
        )

        if st.session_state.game_over:
            if is_win:
                st.balloons()
                st.success(f"✅ GOAL! It was **{st.session_state.secret_player['name']}**!")
            else:
                # Show the correct answer prominently
                st.error(f"❌ Game Over! You used all 6 guesses.")
                st.markdown(f"""
                    <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                         padding: 20px; border-radius: 12px; text-align: center; margin: 20px 0;">
                        <h3 style="color: white; margin: 0 0 10px 0;">The Correct Answer Was:</h3>
                        <h1 style="color: #ffd700; margin: 0; font-size: 2.5em;">{st.session_state.secret_player['name']}</h1>
                        <p style="color: white; margin: 10px 0 0 0; opacity: 0.9;">
                            {st.session_state.secret_player['club']} • {st.session_state.secret_player['position']} • {st.session_state.secret_player['age']} years old
                        </p>
                    </div>
                """, unsafe_allow_html=True)
            
            show_stats_dashboard()
            
            e_col1, e_col2 = st.columns(2)
            with e_col1:
                if st.button("🏠 Menu", use_container_width=True): reset_to_menu()
            with e_col2:
                if st.button("🔄 Next Round", use_container_width=True):
                    if st.session_state.game_mode == "Random": play_another_random()
                    else: reset_to_menu()

    # --- GUESS GRID ---
    if st.session_state.guesses:
        secret = st.session_state.secret_player
        for i, guess in enumerate(reversed(st.session_state.guesses)):
            if i == 0: 
                st.write("### 🎯 Latest Guess")
            elif i == 1: 
                st.write("### 📜 History")
            
            cols = st.columns(5)
            items = [
                ("Nationality", guess['nationality'], "#28a745" if guess['nationality'] == secret['nationality'] else "#dc3545"),
                ("League", guess['league'], "#28a745" if guess['league'] == secret['league'] else "#dc3545"),
                ("Club", guess['club'], "#28a745" if guess['club'] == secret['club'] else "#dc3545"),
                ("Position", guess['position'], "#28a745" if guess['position'] == secret['position'] else "#dc3545"),
                ("Age", f"{guess['age']} {'↑' if guess['age'] < secret['age'] else '↓' if guess['age'] > secret['age'] else ''}", 
                 "#28a745" if guess['age'] == secret['age'] else "#ffc107" if abs(guess['age'] - secret['age']) <= 2 else "#dc3545")
            ]
            
            # Only animate the latest guess (i == 0)
            for j, (label, val, color) in enumerate(items):
                # Stagger animation: 0s, 0.1s, 0.2s, 0.3s, 0.4s
                delay = j * 0.1 if i == 0 else 0
                with cols[j]: 
                    attribute_box(label, val, color, show_label=(i == 0), animation_delay=delay)
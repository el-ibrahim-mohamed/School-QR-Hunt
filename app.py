import streamlit as st
from streamlit_cookies_manager_ext import EncryptedCookieManager
import firebase_admin
from firebase_admin import credentials, db
from datetime import datetime
import re
import time

# ---------------------------------------------------------
# 🛠️ DEVELOPER TESTING CONFIGURATION
# ---------------------------------------------------------
# TRUE  = Simulates that the game has NOT started yet (Force Lock for Testing)
# FALSE = Uses the real system database time checking logic for production
DEV_OVERRIDE_LIVE = False

# -----------------------------------------
# 1. DATABASE INITIALIZATION
# -----------------------------------------

service_account_key_dict = dict(st.secrets["firebase_service_account"])

if not firebase_admin._apps:
    cred = credentials.Certificate(service_account_key_dict)
    firebase_admin.initialize_app(
        credential=cred,
        options={
            "databaseURL": "https://mels-qr-hunt-default-rtdb.europe-west1.firebasedatabase.app",
            "databaseAuthVariableOverride": {"uid": st.secrets["firebase"]["UID"]},
        },
    )

root_ref = db.reference("/")

# Page Styling and Configuration
st.set_page_config(page_title="QR Code Hunt", page_icon="🎯", layout="centered")

# Cyber-game themed custom CSS styling
st.markdown(
    """
    <style>
        .leaderboard-card { padding: 15px; border-radius: 8px; background-color: #1e2430; margin-bottom: 10px; border-left: 5px solid #00ff66; display: flex; justify-content: space-between; align-items: center; }
        .stat-box { 
            background-color: #0d1117; 
            border: 1px solid #2d3748; 
            padding: 15px; 
            border-radius: 8px; 
            text-align: center; 
            color: #58a6ff  !important; 
        }
        .stat-box h2 { margin: 10px 0 5px 0; font-size: 1.8rem; }
        .stat-subtext { font-size: 0.85em; color: #8b949e; margin-top: 2px; }
        .success-text { color: #00ff66; font-weight: bold; }
        .warning-text { color: #ffcc00; font-weight: bold; }
        .error-text { color: #ff4b4b; font-weight: bold; }
    </style>
    """,
    unsafe_allow_html=True,
)


# -----------------------------------------
# HELPER FUNCTIONS & UTILITIES
# -----------------------------------------
def sanitize_username(username: str) -> str:
    """Strips forbidden Firebase key characters to protect database paths."""
    return re.sub(r"[.$#\[\]/]", "", username).strip()


def check_game_started() -> tuple[bool, str]:
    """Evaluates system target launch timestamp vs current time with Dev Override."""
    settings = root_ref.child("system_settings").get() or {}
    start_time_str = settings.get("game_start_time", "2026-05-20T10:30:00")

    try:
        start_time = datetime.fromisoformat(start_time_str)
    except ValueError:
        start_time = datetime.fromisoformat("2026-05-20T10:30:00")

    current_time = datetime.now()

    # Apply dynamic evaluation based on hardcoded developer config switch
    if DEV_OVERRIDE_LIVE:
        is_live = True
    else:
        is_live = current_time >= start_time

    formatted_display_time = start_time.strftime("%I:%M %p")
    return is_live, formatted_display_time


# -----------------------------------------
# 2. STATE & COOKIE MANAGEMENT
# -----------------------------------------
query_params = st.query_params

if "username" not in st.session_state:
    st.session_state.username = None

if "cookies" not in st.session_state:
    cookies = EncryptedCookieManager(
        password=st.secrets["cookies"]["PASSWORD"], prefix="qrhunt/"
    )
    if not cookies.ready():
        st.stop()
    st.session_state["cookies"] = cookies

cookies: EncryptedCookieManager = st.session_state["cookies"]

uname_cookie = cookies.get("username")
if uname_cookie:
    st.session_state["username"] = uname_cookie

# Fetch operational engine checks
game_is_live, start_time_display = check_game_started()

# -----------------------------------------
# 3. GAME ROUTER
# -----------------------------------------
db_players = root_ref.child("players")
db_valid_codes = root_ref.child("valid_codes")

# --- CASE A: QR CODE SCANNED (?code=XXXXX) ---
if "code" in query_params:
    scanned_code = query_params["code"]

    # Step 1: Securely fetch nested dictionary from Firebase
    valid_codes_dict = db_valid_codes.get() or {}
    normal_list = valid_codes_dict.get("normal", [])
    special_list = valid_codes_dict.get("special", [])

    # Union evaluation to check presence across both lists safely
    if (scanned_code not in normal_list) and (scanned_code not in special_list):
        st.title("🚫 Access Denied")
        st.markdown(
            f"<p class='error-text'>Nice try, hacker! Code #{scanned_code} doesn't exist in our mainframe. Find a real hidden sheet!</p>",
            unsafe_allow_html=True,
        )
        if st.button("Go to Home Dashboard", type="primary"):
            st.query_params.clear()
            st.rerun()

    # Time Gate Intercept for Early Scans
    elif not game_is_live:
        st.title("🔒 Event Locked")
        st.markdown(
            f"""
            <div style='background-color: rgba(255, 75, 75, 0.1); border: 1px solid #ff4b4b; padding: 20px; border-radius: 8px; text-align: center;'>
                <p class='error-text' style='font-size: 1.15em; margin-bottom: 10px;'>🚨 ACCESS DENIED: EVENT DIDN'T START</p>
                <p style='color: #A2805D ; margin: 0;'>You found a physical node early, the even't didn't start yet.</p>
                <h4 style='color: #ffcc00; margin-top: 15px; margin-bottom: 0;'>The Event goes live at {start_time_display}!</h4>
            </div>
            """,
            unsafe_allow_html=True,
        )
        " "
        if st.button("Return to Dashboard", type="primary"):
            st.query_params.clear()
            st.rerun()

    else:
        # Step 2: Check if user is registered/logged in on this device
        if not st.session_state.username:
            st.title("🎯 Secure the Cache!")
            st.subheader("Enter your unique username below to claim your points.")

            with st.form("registration_form"):
                user_input = st.text_input(
                    "Unique Username",
                    help="Enter a real name and class to identify yourself! Special path characters are automatically cleaned.",
                    placeholder="e.g. Ibrahim_2PC , Ahmed3_1D",
                )

                if st.form_submit_button("Register & Claim Points", type="primary"):
                    cleaned_user = sanitize_username(user_input)
                    if not cleaned_user:
                        st.error(
                            "Username field cannot be blank or contain only special characters."
                        )
                    else:
                        existing_user = db_players.child(cleaned_user).get()
                        if existing_user:
                            st.error(
                                "That username is taken! Add a random number or class suffix."
                            )
                        else:
                            st.success("Username Created!")
                            db_players.child(cleaned_user).set(
                                {"score": 0, "scans": []}
                            )
                            st.session_state.username = cleaned_user

                            cookies["username"] = cleaned_user
                            cookies.save()
                            time.sleep(1.5)
                            st.rerun()

        # Step 3: User logged in, process point validation logic
        else:
            username = st.session_state.username
            player_profile = db_players.child(username).get() or {
                "score": 0,
                "scans": [],
            }

            user_score = player_profile.get("score", 0)
            user_scans = player_profile.get("scans", [])

            st.title("📟 Processing Scan...")

            if scanned_code in user_scans:
                st.warning("👀 Move along, Hunter!")
                st.markdown(
                    f"<p class='warning-text'>Hey {username}, you've already scanned node #{scanned_code}. Stop camping and go find another one!</p>",
                    unsafe_allow_html=True,
                )
            else:
                # Dynamic scoring assignment depending on branch location
                points_awarded = 30 if scanned_code in special_list else 10
                new_score = user_score + points_awarded

                user_scans.append(scanned_code)
                db_players.child(username).update(
                    {"score": new_score, "scans": user_scans}
                )

                st.balloons()
                if points_awarded == 30:
                    st.success("🔥 ULTRA CACHE SECURED!! 🔥")
                    st.markdown(
                        "<p class='success-text' style='color: #ffcc00; font-size: 1.2em;'>EPIC FIND! You uncovered a high-tier node. +30 Points added!</p>",
                        unsafe_allow_html=True,
                    )
                else:
                    st.success("💥 CACHE SECURED!")
                    st.markdown(
                        f"<p class='success-text'>Boom! Code #{scanned_code} processed. You gained +10 points!</p>",
                        unsafe_allow_html=True,
                    )

                st.metric(label="Your Updated Score", value=f"{new_score} PTS")

            if st.button("Return to Dashboard", type="primary"):
                st.query_params.clear()
                st.rerun()

# --- CASE B: CLEAN HOMEPAGE VIEW (No query parameter) ---
else:
    st.title("🏆 QR CODE HUNT 🏆", anchor=False)
    " "

    # Welcome banner / Early Registration option
    if st.session_state.username:
        st.subheader(
            f"👤 Logged in as :blue[**{st.session_state.username}**]", anchor=False
        )
    else:
        with st.expander("🔑 Create Your Username Before Hunting"):
            early_user = st.text_input(
                "Pre-register Username:",
                help="Enter a real name and class to identify yourself!",
                placeholder="e.g. Ibrahim_2PC , Ahmed3_1D",
            )

            if st.button("Register Username"):
                cleaned_early = sanitize_username(early_user)
                if cleaned_early:
                    user_exists = db_players.child(cleaned_early).get()
                    if user_exists:
                        st.session_state.username = cleaned_early
                        st.success(f"Welcome back, {cleaned_early}!")
                        st.rerun()
                    else:
                        db_players.child(cleaned_early).set({"score": 0, "scans": []})
                        st.session_state.username = cleaned_early
                        st.success(f"Profile {cleaned_early} compiled successfully!")

                        cookies["username"] = cleaned_early
                        cookies.save()
                        time.sleep(1.5)
                        st.rerun()
                else:
                    st.error("Invalid Username entry.")

    # Data Compute Block for Dashboard Columns
    players_data = db_players.get() or {}
    valid_codes_dict = db_valid_codes.get() or {}

    normal_list = valid_codes_dict.get("normal", [])
    special_list = valid_codes_dict.get("special", [])

    total_players = len(players_data)

    # Real-time scanning counter engine
    found_normal_count = 0
    found_special_count = 0
    scanned_globally_set = set()

    for p_id, p_info in players_data.items():
        user_scans = p_info.get("scans", [])
        for code in user_scans:
            if code in normal_list and code not in scanned_globally_set:
                found_normal_count += 1
            elif code in special_list and code not in scanned_globally_set:
                found_special_count += 1
            scanned_globally_set.add(code)

    # Calculate remaining untouched codes
    rem_normal = max(0, len(normal_list) - found_normal_count)
    rem_special = max(0, len(special_list) - found_special_count)

    # Rendering 3-Column Stats Row
    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown(
            f"""<div class='stat-box'>
                👥 <b>Active Hunters</b>
                <h2>{total_players}</h2>
                <div class='stat-subtext'>Registered Accounts</div>
            </div>""",
            unsafe_allow_html=True,
        )
        " "
    with col2:
        st.markdown(
            f"""<div class='stat-box'>
                📡 <b>Caches Found</b>
                <h2>{found_normal_count + found_special_count}</h2>
                <div class='stat-subtext'><b>{found_normal_count}</b> Normal | <b>{found_special_count}</b> Special</div>
            </div>""",
            unsafe_allow_html=True,
        )
        " "
    with col3:
        st.markdown(
            f"""<div class='stat-box'>
                🔓 <b>Remaining Caches</b>
                <h2>{rem_normal + rem_special}</h2>
                <div class='stat-subtext'><b>{rem_normal}</b> Normal | <b>{rem_special}</b> Special</div>
            </div>""",
            unsafe_allow_html=True,
        )

    # ---------------------------------------------------------
    # 🕒 4. TARGET START TIME SECTION (NEW SPECIFIED PLACEMENT)
    # ---------------------------------------------------------
    st.markdown("---")
    if not game_is_live:
        st.markdown(
            f"""
            <div style="background-color: #111b27; border: 1px solid #1f6feb; padding: 18px; border-radius: 8px; text-align: center;">
                <span style="color: #ffcc00; font-weight: bold; font-size: 1.1em; margin-left: 5px;">⏳ SYSTEM GOES LIVE AT {start_time_display}</span>
            </div>
            """,
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            f"""
            <div style="background-color: rgba(0, 255, 102, 0.05); border: 1px solid #00ff66; padding: 15px; border-radius: 8px; text-align: center;">
                <h3 style="color: #1F51FF; font-weight: bold; font-size: 1.3em;">📡 Mainframe Status: LIVE</span> 
            </div>
            """,
            unsafe_allow_html=True,
        )
    st.markdown("---")

    # ---------------------------------------------------------
    # 🏆 5. RESTORED REAL-TIME LEADERBOARD SECTION
    # ---------------------------------------------------------
    st.subheader("⚡ Real-Time Leaderboard", anchor=False)

    if st.button("Reload Leaderboard", icon="🔄️"):
        st.rerun()

    if players_data:
        sorted_board = sorted(
            players_data.items(), key=lambda x: x[1].get("score", 0), reverse=True
        )

        for rank, (player_name, data) in enumerate(sorted_board, start=1):
            score = data.get("score", 0)
            medal = (
                "🥇"
                if rank == 1
                else "🥈" if rank == 2 else "🥉" if rank == 3 else f"#{rank}"
            )

            # Append the dynamic (You) label string context safely if usernames match
            is_self = player_name == st.session_state.username
            you_label = (
                " <span style='color: #00ff66; font-weight: bold; font-size: 0.9em;'>(You)</span>"
                if is_self
                else ""
            )

            st.markdown(
                f"""
                <div class="leaderboard-card">
                    <div style="font-weight:bold; font-size:1.1em; color:#00f0ff;">{medal} &nbsp; {player_name}{you_label}</div>
                    <div style="color:#00ff66; font-weight:bold; font-size:1.1em;">{score} PTS</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
    else:
        st.info("The database mainframe is empty. No hunters registered yet!")

    # Game Instructions Section
    st.write("---")
    st.markdown(
        "<h3 style='text-align: center; color: #ff4b4b; margin-bottom: 20px;'>🎮 OPERATION: QR HUNT</h3>",
        unsafe_allow_html=True,
    )

    total_hidden_qrs = len(normal_list) + len(special_list)

    # Grid Layout for Steps
    col1, col2 = st.columns(2)

    with col1:
        st.markdown(
            f"""
            <div style="background-color: #161b22; border: 1px solid #30363d; padding: 15px; border-radius: 8px; min-height: 140px;">
                <h5 style="color: #58a6ff; margin-top:0;">🔍 1. SEARCH</h5>
                <p style="font-size: 0.9em; color: #8b949e; margin: 0;"><b>{total_hidden_qrs} unique QR codes</b> are physically hidden across the school grounds. Check the common areas, walls, and hidden corners.</p>
            </div>
        """,
            unsafe_allow_html=True,
        )
        st.write("")

    with col2:
        st.markdown(
            """
            <div style="background-color: #161b22; border: 1px solid #30363d; padding: 15px; border-radius: 8px; min-height: 140px;">
                <h5 style="color: #58a6ff; margin-top:0;">📸 2. SCAN</h5>
                <p style="font-size: 0.9em; color: #8b949e; margin: 0;">Use your phone camera to scan any code you find. It will automatically redirect you to this platform with a secure encrypted key.</p>
            </div>
        """,
            unsafe_allow_html=True,
        )
        st.write("")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown(
            """
            <div style="background-color: #161b22; border: 1px solid #30363d; padding: 15px; border-radius: 8px; min-height: 140px;">
                <h5 style="color: #00ff66; margin-top:0;">💎 3. CLAIM</h5>
                <p style="font-size: 0.9em; color: #8b949e; margin: 0;">Your first scan prompts profile creation. Normal caches add <b>+10 points</b>. Keep an eye out for 5 rare <b>Special Caches worth +30 points</b>!</p>
            </div>
        """,
            unsafe_allow_html=True,
        )
        st.write("")

    with col2:
        st.markdown(
            """
            <div style="background-color: #161b22; border: 1px solid #30363d; padding: 15px; border-radius: 8px; min-height: 140px;">
                <h5 style="color: #ff4b4b; margin-top:0;">🚨 4. NO CHEATING</h5>
                <p style="font-size: 0.9em; color: #8b949e; margin: 0;">Each physical code can only be claimed <b>once per user</b>. Sending screenshots to friends will only trigger duplicate error alerts.</p>
            </div>
        """,
            unsafe_allow_html=True,
        )
        st.write("")

    # Pro Tip Banner
    st.markdown(
        """
        <div style="background-color: rgba(255, 204, 0, 0.1); border: 1px solid #ffcc00; padding: 12px; border-radius: 8px; text-align: center; margin-top: 10px;">
            <span style="color: #ffcc00; font-weight: bold;">💡 PRO TIP:</span> 
            <span style="color: #c9d1d9; font-size: 0.95em;">Pre-register your account at the top of this page right now to ensure lightning-fast scans when the hunt officially starts!</span>
        </div>
    """,
        unsafe_allow_html=True,
    )

    # Personal Branding Section
    "---"
    st.markdown(
        """
        <div style="text-align: center; padding: 10px; margin-top: 10px;">
            <p style="margin: 0; font-size: 0.85em; color: #8b949e; letter-spacing: 1px;">DEVELOPED BY</p>
            <h4 style="margin: 5px 0 0 0; color: #58a6ff; font-weight: bold; font-family: 'Courier New', monospace;">IBRAHIM MOHAMED • CLASS 2PC</h4>
            <p style="margin: 2px 0 0 0; font-size: 0.75em; color: #00ff66; font-family: 'Courier New', monospace;">[ STATUS: CYBER-ADMIN ]</p>
        </div>
    """,
        unsafe_allow_html=True,
    )

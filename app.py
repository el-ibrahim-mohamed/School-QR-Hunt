import streamlit as st
from streamlit_cookies_manager_ext import EncryptedCookieManager
import firebase_admin
from firebase_admin import credentials, db
import time

# -----------------------------------------
# 1. DATABASE INITIALIZATION
# -----------------------------------------

# --- Setting up Firebase RTDB ---
# Fetch the service account key JSON file contents
service_account_key_dict = dict(st.secrets["firebase_service_account"])

# Check if no default app is already initialized
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
            color: #58a6ff  !important; /* Force high contrast white */
        }
        .success-text { color: #00ff66; font-weight: bold; }
        .warning-text { color: #ffcc00; font-weight: bold; }
        .error-text { color: #ff4b4b; font-weight: bold; }
        </style>
    """,
    unsafe_allow_html=True,
)


# -----------------------------------------
# 2. STATE & COOKIE MANAGEMENT
# -----------------------------------------

# Get active URL query parameters (?code=XXXXX)
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

# Retrieve username if saved
uname_cookie = cookies.get("username")
if uname_cookie:
    st.session_state["username"] = uname_cookie


# -----------------------------------------
# 3. GAME ROUTER
# -----------------------------------------
db_players = root_ref.child("players")
db_valid_codes = root_ref.child("valid_codes")

# --- CASE A: QR CODE SCANNED (?code=XXXXX) ---
if "code" in query_params:
    scanned_code = query_params["code"]

    # Step 1: Security Check: Verify code belongs in the master list
    valid_codes_list = db_valid_codes.get() or []

    if scanned_code not in valid_codes_list:
        st.title("🚫 Access Denied")
        st.markdown(
            f"<p class='error-text'>Nice try, hacker! Code #{scanned_code} doesn't exist in our mainframe. Find a real hidden sheet!</p>",
            unsafe_allow_html=True,
        )
        if st.button("Go to Home Dashboard"):
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
                    help="Enter a real name and class to identify yourself!",
                    placeholder="e.g. Ibrahim_2C , Ahmed3_1D",
                ).strip()

                if st.form_submit_button("Register & Claim +10 pts", type="primary"):
                    if not user_input:
                        st.error("Username field cannot be blank.")
                    else:
                        # Verify username unique availability
                        existing_user = db_players.child(user_input).get()
                        if existing_user:
                            st.error(
                                "That username is taken! Add a random number or class suffix."
                            )
                        else:
                            st.success("Username Created!")

                            # Save to DB
                            db_players.child(user_input).set({"score": 0, "scans": []})
                            st.session_state.username = user_input

                            # Save to cookies
                            cookies["username"] = user_input
                            cookies.save()
                            time.sleep(1.5)

                            st.rerun()  # Keep query parameters active during loop reload

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

            # Anti-duplicate verification
            if scanned_code in user_scans:
                st.warning("👀 Move along, Hunter!")
                st.markdown(
                    f"<p class='warning-text'>Hey {username}, you've already scanned node #{scanned_code}. Stop camping and go find another one!</p>",
                    unsafe_allow_html=True,
                )
            else:
                # Add code to player log, increment score value
                user_scans.append(scanned_code)
                new_score = user_score + 10

                db_players.child(username).update(
                    {"score": new_score, "scans": user_scans}
                )

                st.balloons()
                st.success("💥 CACHE SECURED!")
                st.markdown(
                    f"<p class='success-text'>Boom! Code #{scanned_code} processed. Your gained +10 points!</p>",
                    unsafe_allow_html=True,
                )
                st.metric(label="Your Updated Score", value=f"{new_score} PTS")

            if st.button("Return to Dashboard"):
                st.query_params.clear()
                st.rerun()

# --- CASE B: CLEAN HOMEPAGE VIEW (No query parameter) ---
else:
    st.title("🏆 QR CODE HUNT 🏆", anchor=False)
    " "

    # Welcome banner / Early Registration option
    if st.session_state.username:
        st.subheader(f"👤 Logged in as :blue[**{st.session_state.username}**]")
        # if st.button("Log Out", icon="⬅️"):
        #     st.session_state["username"] = ""
        #     cookies["username"] = ""
        #     cookies.save()
        #     time.sleep(1)
        #     st.rerun()
    else:
        with st.expander("🔑 Create Your Username Before Hunting"):
            early_user = st.text_input(
                "Pre-register Username:",
                help="Enter a real name and class to identify yourself!",
                placeholder="e.g. Ibrahim_2C , Ahmed3_1D",
            ).strip()

            if st.button("Register Username"):
                if early_user:
                    user_exists = db_players.child(early_user).get()
                    if user_exists:
                        st.session_state.username = early_user
                        st.success(f"Welcome back, {early_user}!")
                    else:
                        # Save to DB
                        db_players.child(early_user).set({"score": 0, "scans": []})
                        st.session_state.username = early_user
                        st.success(f"Profile {early_user} compiled successfully!")

                    # Save to cookies
                    cookies["username"] = early_user
                    cookies.save()
                    time.sleep(1.5)

                    st.rerun()

    # Live Stat Tracking Row
    " "
    players_data = db_players.get() or {}
    total_players = len(players_data)

    total_scans_count = 0
    for p_id, p_info in players_data.items():
        total_scans_count += len(p_info.get("scans", []))

    col1, col2 = st.columns(2)
    with col1:
        st.markdown(
            f"<div class='stat-box'>👥 <b>Active Hunters</b><br><h2>{total_players}</h2></div>",
            unsafe_allow_html=True,
        )
        " "
    with col2:
        st.markdown(
            f"<div class='stat-box'>📡 <b>Total Nodes Found</b><br><h2>{total_scans_count}</h2></div>",
            unsafe_allow_html=True,
        )

    "---"
    st.subheader("⚡ Real-Time Leaderboard", anchor=False)

    if st.button("Reload Leaderboard", icon="🔄️"):
        st.rerun()

    # Display Live Sorted Leaderboard
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

            st.markdown(
                f"""
                <div class="leaderboard-card">
                    <div style="font-weight:bold; font-size:1.1em; color:#00f0ff;">{medal} &nbsp; {player_name}</div>
                    <div style="color:#00ff66; font-weight:bold; font-size:1.1em;">{score} PTS</div>
                </div>
            """,
                unsafe_allow_html=True,
            )
    else:
        st.info("The database mainframe is empty. No codes scanned yet!")

    # Game Instructions Section
    st.write("---")
    st.markdown("<h3 style='text-align: center; color: #ff4b4b; margin-bottom: 20px;'>🎮 OPERATION: QR HUNT</h3>", unsafe_allow_html=True)
    
    # Total QR codes
    total_hidden_qrs = len(db_valid_codes.get() or [])

    # Grid Layout for Steps
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown(f"""
            <div style="background-color: #161b22; border: 1px solid #30363d; padding: 15px; border-radius: 8px; min-height: 140px;">
                <h5 style="color: #58a6ff; margin-top:0;">🔍 1. SEARCH</h5>
                <p style="font-size: 0.9em; color: #8b949e; margin: 0;"><b>{total_hidden_qrs} unique QR codes</b> are physically hidden across the school grounds. Check the common areas, walls, and hidden corners.</p>
            </div>
        """, unsafe_allow_html=True)
        st.write("")

    with col2:
        st.markdown("""
            <div style="background-color: #161b22; border: 1px solid #30363d; padding: 15px; border-radius: 8px; min-height: 140px;">
                <h5 style="color: #58a6ff; margin-top:0;">📸 2. SCAN</h5>
                <p style="font-size: 0.9em; color: #8b949e; margin: 0;">Use your phone camera to scan any code you find. It will automatically redirect you to this platform with a secure encrypted key.</p>
            </div>
        """, unsafe_allow_html=True)
        st.write("")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("""
            <div style="background-color: #161b22; border: 1px solid #30363d; padding: 15px; border-radius: 8px; min-height: 140px;">
                <h5 style="color: #00ff66; margin-top:0;">💎 3. CLAIM</h5>
                <p style="font-size: 0.9em; color: #8b949e; margin: 0;">Your first scan prompts profile creation. Every unique code secured instantly adds <b>+10 points</b> directly to your score.</p>
            </div>
        """, unsafe_allow_html=True)
        st.write("")

    with col2:
        st.markdown("""
            <div style="background-color: #161b22; border: 1px solid #30363d; padding: 15px; border-radius: 8px; min-height: 140px;">
                <h5 style="color: #ff4b4b; margin-top:0;">🚨 4. NO CHEATING</h5>
                <p style="font-size: 0.9em; color: #8b949e; margin: 0;">Each physical code can only be claimed <b>once per user</b>. Sending screenshots to friends will only trigger duplicate error alerts.</p>
            </div>
        """, unsafe_allow_html=True)
        st.write("")

    # Pro Tip Banner
    st.markdown("""
        <div style="background-color: rgba(255, 204, 0, 0.1); border: 1px solid #ffcc00; padding: 12px; border-radius: 8px; text-align: center; margin-top: 10px;">
            <span style="color: #ffcc00; font-weight: bold;">💡 PRO TIP:</span> 
            <span style="color: #c9d1d9; font-size: 0.95em;">Pre-register your account at the top of this page right now to ensure lightning-fast scans when the hunt officially starts!</span>
        </div>
    """, unsafe_allow_html=True)

    # Personal Branding Section
    "---"
    st.markdown("""
        <div style="text-align: center; padding: 10px; margin-top: 10px;">
            <p style="margin: 0; font-size: 0.85em; color: #8b949e; letter-spacing: 1px;">DEVELOPED BY</p>
            <h4 style="margin: 5px 0 0 0; color: #58a6ff; font-weight: bold; font-family: 'Courier New', monospace;">IBRAHIM MOHAMED • CLASS 2PC</h4>
            <p style="margin: 2px 0 0 0; font-size: 0.75em; color: #00ff66; font-family: 'Courier New', monospace;">[ STATUS: CYBER-ADMIN ]</p>
        </div>
    """, unsafe_allow_html=True)
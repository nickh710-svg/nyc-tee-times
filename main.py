import streamlit as st
import requests
import datetime
from zoneinfo import ZoneInfo

# --- 1. Page Setup ---
# CHANGED to "wide" layout so our side-by-side columns look good!
st.set_page_config(page_title="NYC Tee Times", page_icon="⛳", layout="wide")
st.title("⛳ NYC Municipal Tee Times")

# --- 2. The View Toggle ---
view_mode = st.radio(
    "Select View",
    ["One Course Detailed View", "All Courses Daily View"],
    horizontal=True, # Makes it look like a nice toggle bar
    label_visibility="collapsed"
)
st.divider()

# Map the selected course to its specific API IDs and headers
course_data = {
    "Pelham Bay": {
        "facility_id": "4111", 
        "course_id": "54f14cc00c8ad60378b02cc5", 
        "alias": "pelham-bay-split-rock", 
        "url": "pelham-bay-split-rock.book.teeitup.com"
    },
    "Split Rock": {
        "facility_id": "4111", 
        "course_id": "PENDING", 
        "alias": "pelham-bay-split-rock", 
        "url": "pelham-bay-split-rock.book.teeitup.com"
    },
    "Van Cortlandt": {
        "facility_id": "5043", 
        "course_id": "ANY", 
        "alias": "golf-nyc", 
        "url": "golf-nyc.book.teeitup.com"
    },
    "Dyker Beach": {
        "facility_id": "4048", 
        "course_id": "ANY", 
        "alias": "dyker-beach-golf-course", 
        "url": "dyker-beach-golf-course.book.teeitup.com"
    },
    "Forest Park": {
        "facility_id": "5045", 
        "course_id": "ANY", 
        "alias": "golf-nyc", 
        "url": "golf-nyc.book.teeitup.com"
    },
    "Douglaston": {
        "facility_id": "5044", 
        "course_id": "ANY", 
        "alias": "douglaston-golf-course", 
        "url": "douglaston-golf-course.book.teeitup.com"
    },
    "Dunwoodie": {
        "facility_id": "5814", 
        "course_id": "ANY", 
        "alias": "westchester-county", 
        "url": "westchester-county.book.teeitup.com"
    }
}

# ==========================================
# VIEW 1: ONE COURSE DETAILED VIEW
# ==========================================
if view_mode == "One Course Detailed View":
    st.write("View detailed pricing and rates for a specific course.")

    col1, col2, col3 = st.columns(3)
    with col1:
        course_name = st.selectbox("Course", list(course_data.keys()))
    with col2:
        selected_date = st.date_input("Date", datetime.date.today())
    with col3:
        players_needed = st.selectbox("Players", ["Any", 1, 2, 3, 4])

    active_course = course_data[course_name]

    if st.button("Search Available Times", type="primary"):
        with st.spinner(f"Searching the database for {course_name}..."):
            api_date = selected_date.strftime("%Y-%m-%d")
            url = f"https://phx-api-be-east-1b.kenna.io/v2/tee-times?date={api_date}&facilityIds={active_course['facility_id']}"

            headers = {
                "accept": "application/json",
                "origin": f"https://{active_course['url']}",
                "referer": f"https://{active_course['url']}/",
                "user-agent": "Mozilla/5.0",
                "x-be-alias": active_course["alias"]
            }

            response = requests.get(url, headers=headers)

            if response.status_code == 200:
                data = response.json()

                if data and len(data) > 0 and 'teetimes' in data[0]:
                    tee_times = data[0]['teetimes']
                    matches_found = 0

                    for slot in tee_times:
                        this_course_id = slot.get('courseId')

                        if active_course['course_id'] == "PENDING": continue
                        if active_course['course_id'] != "ANY" and this_course_id != active_course['course_id']: continue

                        rates = slot.get('rates', [])
                        if not rates: continue

                        first_rate = rates[0]
                        players_list = first_rate.get('allowedPlayers', [])
                        if players_needed != "Any" and players_needed not in players_list: continue 

                        matches_found += 1

                        utc_time_str = slot.get('teetime')
                        utc_time = datetime.datetime.strptime(utc_time_str, "%Y-%m-%dT%H:%M:%S.000Z")
                        utc_time = utc_time.replace(tzinfo=ZoneInfo("UTC"))
                        ny_time = utc_time.astimezone(ZoneInfo("America/New_York"))
                        formatted_time = ny_time.strftime("%I:%M %p")

                        rate_name = first_rate.get('name', 'Standard')
                        possible_keys = ['greenFeeCart', 'greenFee', 'price', 'tradeValue', 'dueAtCourse']
                        raw_price = 0
                        for key in possible_keys:
                            if first_rate.get(key):
                                raw_price = first_rate.get(key)
                                break

                        price = f"${raw_price / 100:.2f}"
                        players_str = f"{min(players_list)}-{max(players_list)}" if players_list else "N/A"

                        with st.container():
                            col_time, col_details, col_btn = st.columns([1.5, 3, 1.5])
                            with col_time: st.subheader(f"⏰ {formatted_time}")
                            with col_details:
                                st.write(f"**{course_name}** | {rate_name}")
                                st.caption(f"🏌️ {players_str} players | 💵 {price}")
                            with col_btn:
                                link_id = active_course['course_id'] if active_course['course_id'] not in ["ANY", "PENDING"] else active_course['facility_id']
                                booking_url = f"https://{active_course['url']}/?course={link_id}&date={api_date}"
                                st.link_button("Book Now", booking_url)
                            st.divider()

                    if matches_found > 0: st.success(f"Found {matches_found} times!")
                    elif active_course['course_id'] == "PENDING": st.info(f"{course_name} is currently closed.")
                    else: st.info("No times available for that course and number of players.")
                else: st.info("No tee times available for this date.")
            else: st.error(f"Failed to fetch data. Status: {response.status_code}")

# ==========================================
# VIEW 2: ALL COURSES DAILY VIEW
# ==========================================
elif view_mode == "All Courses Daily View":
    st.write("Compare all courses side-by-side for a specific day.")

    # Filter Controls
    col_date, col_players = st.columns(2)
    with col_date: selected_date = st.date_input("Select Date", datetime.date.today())
    with col_players: players_needed = st.selectbox("Players Needed", ["Any", 1, 2, 3, 4])

    if st.button("Search All Courses", type="primary"):
        with st.spinner("Pinging databases for all courses..."):
            api_date = selected_date.strftime("%Y-%m-%d")

            # 1. Fetch data efficiently (Don't hit Pelham and Split Rock twice since they share a facility ID)
            fetched_facilities = {}
            for c_name, c_info in course_data.items():
                fac_id = c_info['facility_id']
                if fac_id not in fetched_facilities:
                    url = f"https://phx-api-be-east-1b.kenna.io/v2/tee-times?date={api_date}&facilityIds={fac_id}"
                    headers = {
                        "accept": "application/json",
                        "origin": f"https://{c_info['url']}",
                        "referer": f"https://{c_info['url']}/",
                        "user-agent": "Mozilla/5.0",
                        "x-be-alias": c_info["alias"]
                    }
                    resp = requests.get(url, headers=headers)
                    if resp.status_code == 200 and resp.json() and 'teetimes' in resp.json()[0]:
                        fetched_facilities[fac_id] = resp.json()[0]['teetimes']
                    else:
                        fetched_facilities[fac_id] = []

            # 2. Build the UI Columns dynamically based on how many courses we have
            course_names = list(course_data.keys())
            ui_columns = st.columns(len(course_names))

            # 3. Populate each column
            for idx, c_name in enumerate(course_names):
                c_info = course_data[c_name]
                fac_id = c_info['facility_id']
                secret_id = c_info['course_id']

                # Get the raw times for this facility
                raw_times = fetched_facilities.get(fac_id, [])

                with ui_columns[idx]:
                    st.subheader(c_name) # Column Header

                    times_found = 0
                    for slot in raw_times:
                        this_course_id = slot.get('courseId')

                        # Strict ID checking
                        if secret_id == "PENDING": continue
                        if secret_id != "ANY" and this_course_id != secret_id: continue

                        # Player checking
                        rates = slot.get('rates', [])
                        if not rates: continue
                        players_list = rates[0].get('allowedPlayers', [])
                        if players_needed != "Any" and players_needed not in players_list: continue

                        times_found += 1

                        # Fix Timezone
                        utc_time_str = slot.get('teetime')
                        utc_time = datetime.datetime.strptime(utc_time_str, "%Y-%m-%dT%H:%M:%S.000Z").replace(tzinfo=ZoneInfo("UTC"))
                        formatted_time = utc_time.astimezone(ZoneInfo("America/New_York")).strftime("%I:%M %p")
                        players_str = f"{min(players_list)}-{max(players_list)}" if players_list else "N/A"

                        # --- THE MINI CARD ---
                        # border=True gives it that neat block look from your mockup!
                        with st.container(border=True):
                            st.markdown(f"**{formatted_time}**")
                            st.caption(f"🏌️ {players_str} Players")

                            link_id = secret_id if secret_id not in ["ANY", "PENDING"] else fac_id
                            booking_url = f"https://{c_info['url']}/?course={link_id}&date={api_date}"
                            # use_container_width=True stretches the button cleanly across the card
                            st.link_button("Book", booking_url, use_container_width=True)

                    # Empty states
                    if secret_id == "PENDING":
                        st.info("Closed/Pending.")
                    elif times_found == 0:
                        st.info("No times.")

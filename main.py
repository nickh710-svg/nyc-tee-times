import streamlit as st
import requests
import datetime
from zoneinfo import ZoneInfo
from curl_cffi import requests as curl_requests

# --- 1. Page Setup ---
st.set_page_config(
    page_title="NYC Tee Times", 
    page_icon="⛳", 
    layout="wide", 
    initial_sidebar_state="expanded" # <-- This forces it open
)

# --- 2. Data Structures ---
course_data = {
    "Pelham Bay": {"fac_id": "4111", "crs_id": "54f14cc00c8ad60378b02cc5", "alias": "pelham-bay-split-rock", "url": "pelham-bay-split-rock.book.teeitup.com", "type": "kenna"},
    "Split Rock": {"fac_id": "19264", "crs_id": "ANY", "alias": "pelham-bay-split-rock", "url": "pelham-bay-split-rock.book.teeitup.com", "type": "kenna"},
    "Van Cortlandt": {"fac_id": "5043", "crs_id": "ANY", "alias": "golf-nyc", "url": "golf-nyc.book.teeitup.com", "type": "kenna"},
    "Dyker Beach": {"fac_id": "4048", "crs_id": "ANY", "alias": "dyker-beach-golf-course", "url": "dyker-beach-golf-course.book.teeitup.com", "type": "kenna"},
    "Forest Park": {"fac_id": "5045", "crs_id": "ANY", "alias": "golf-nyc", "url": "golf-nyc.book.teeitup.com", "type": "kenna"},
    "Douglaston": {"fac_id": "5044", "crs_id": "ANY", "alias": "douglaston-golf-course", "url": "douglaston-golf-course.book.teeitup.com", "type": "kenna"},
    "Dunwoodie": {"fac_id": "5814", "crs_id": "ANY", "alias": "westchester-county", "url": "westchester-county.book.teeitup.com", "type": "kenna"},
    "Skyway": {
        "fac_id": "0b833d14-8c0d-46ca-82e6-7b992de4761e", 
        "alias": "skyway-golf-course", 
        "type": "chronogolf_v2"
    },
    "Marine Park": {
        "type": "golfnow_link", 
        "link": "https://www.golfnow.com/tee-times/facility/4857-marine-park-golf-course/search#facilitytype=0&sortby=Date&view=Grouping&holes=3&timeperiod=3&timemax=42&timemin=10&players=0&pricemax=10000&pricemin=0&promotedcampaignsonly=false"
    }
}

# --- 3. Helper Functions ---
def filter_by_time(results, after_str, before_str):
    if after_str == "Any" and before_str == "Any":
        return results
    
    def to_minutes(t_str):
        try:
            dt = datetime.datetime.strptime(t_str, "%I:%M %p")
            return dt.hour * 60 + dt.minute
        except:
            return -1

    min_m = to_minutes(after_str) if after_str != "Any" else 0
    max_m = to_minutes(before_str) if before_str != "Any" else 1440
    
    filtered = []
    for r in results:
        r_m = to_minutes(r['time'])
        if r_m != -1 and min_m <= r_m <= max_m:
            filtered.append(r)
    return filtered

def fetch_skyway(date_str, players):
    c_info = course_data["Skyway"]
    all_standardized_times = []
    page = 1
    
    headers = {
        "accept": "application/json",
        "referer": f"https://www.chronogolf.com/club/{c_info['alias']}?date={date_str}",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "x-requested-with": "XMLHttpRequest"
    }

    try:
        while True:
            full_url = (
                f"https://www.chronogolf.com/marketplace/v2/teetimes?"
                f"start_date={date_str}&"
                f"course_ids={c_info['fac_id']}&"
                f"holes=9&page={page}"
            )
            
            resp = curl_requests.get(full_url, headers=headers, impersonate="chrome110")
            
            if resp.status_code != 200:
                break
                
            data = resp.json()
            slots = data.get('teetimes', [])
            
            if not slots:
                break
                
            for s in slots:
                min_p = s.get('min_player_size', 1)
                max_p = s.get('max_player_size', 4)
                if players != "Any" and not (min_p <= int(players) <= max_p):
                    continue
                
                raw_ts = s.get('starts_at') 
                dt_obj = datetime.datetime.fromisoformat(raw_ts.replace('Z', '+00:00'))
                ny_time = dt_obj.astimezone(ZoneInfo("America/New_York"))
                display_time = ny_time.strftime("%I:%M %p")
                
                price_val = s.get('default_price', {}).get('subtotal', 0.0)
                
                all_standardized_times.append({
                    "time": display_time,
                    "course": "Skyway",
                    "rate": s.get('default_price', {}).get('affiliation_type', 'Standard'),
                    "price": f"${price_val:.2f}",
                    "players": f"{min_p}-{max_p}",
                    "link": f"https://www.chronogolf.com/club/{c_info['alias']}?date={date_str}"
                })
            
            page += 1
            if page > 5:
                break
                
        return all_standardized_times
        
    except Exception as e:
        print(f"Skyway Error: {e}")
        return []

def fetch_kenna(course_name, date_str, players):
    c_info = course_data[course_name]
    crs_id = c_info.get('crs_id') 
    if crs_id == "PENDING" or crs_id is None: 
        return []
    
    url = f"https://phx-api-be-east-1b.kenna.io/v2/tee-times?date={date_str}&facilityIds={c_info['fac_id']}"
    headers = {"x-be-alias": c_info["alias"], "User-Agent": "Mozilla/5.0"}
    
    try:
        resp = requests.get(url, headers=headers)
        if resp.status_code == 200:
            data = resp.json()
            slots = data[0]['teetimes']
            standardized_times = []
            for s in slots:
                if c_info['crs_id'] != "ANY" and s.get('courseId') != c_info['crs_id']: continue
                
                rate = s['rates'][0]
                p_list = rate.get('allowedPlayers', [])
                if players != "Any" and int(players) not in p_list: continue
                
                utc_time = datetime.datetime.strptime(s['teetime'], "%Y-%m-%dT%H:%M:%S.000Z").replace(tzinfo=ZoneInfo("UTC"))
                ny_time = utc_time.astimezone(ZoneInfo("America/New_York"))
                
                raw_p = 0
                for k in ['greenFeeCart', 'greenFee', 'price', 'dueAtCourse']:
                    if rate.get(k): raw_p = rate.get(k); break

                standardized_times.append({
                    "time": ny_time.strftime("%I:%M %p"),
                    "course": course_name,
                    "rate": rate.get('name', 'Standard'),
                    "price": f"${raw_p / 100:.2f}",
                    "players": f"{min(p_list)}-{max(p_list)}",
                    "link": f"https://{c_info['url']}/?course={c_info['fac_id']}&date={date_str}"
                })
            return standardized_times
    except: return []
    return []

# --- 4. Main UI & Sidebar ---
st.title("⛳ NYC Tee Times")

with st.sidebar:
    st.header("Search Parameters")
    
    view_mode = st.radio("Select View", ["All Courses Daily View", "One Course Detailed View"])
    st.divider()
    
    with st.form("search_form"):
        if view_mode == "One Course Detailed View":
            name = st.selectbox("Course", list(course_data.keys()))
            selected_courses = [name]
        else:
            selected_courses = st.multiselect("Courses to Show", list(course_data.keys()), default=list(course_data.keys()))
            
        date = st.date_input("Date", datetime.date.today())
        plys = st.selectbox("Players Needed", ["Any", 1, 2, 3, 4])
        
        st.write("Time Window")
        t_col1, t_col2 = st.columns(2)
        time_options = ["Any"] + [f"{h}:00 AM" for h in range(5, 12)] + ["12:00 PM"] + [f"{h}:00 PM" for h in range(1, 8)]
        with t_col1: t_after = st.selectbox("After", time_options, index=0)
        with t_col2: t_before = st.selectbox("Before", time_options, index=0)
        
        st.write("") 
        submitted = st.form_submit_button("Search Tee Times", type="primary", use_container_width=True)

# --- 5. Display Results ---
if submitted:
    if not selected_courses:
        st.warning("Please select at least one course to search.")
    else:
        d_str = date.strftime("%Y-%m-%d")
        
        if view_mode == "One Course Detailed View":
            name = selected_courses[0]
            st.subheader(f"Results for {name} on {d_str}")
            
            # --- OVERRIDE FOR MARINE PARK ---
            if course_data[name]['type'] == 'golfnow_link':
                mp_link = course_data[name]['link']
                st.info(f"Data Not Pullable. Click [HERE]({mp_link}) for GolfNow Link")
            else:
                if course_data[name]['type'] == 'chronogolf_v2':
                    results = fetch_skyway(d_str, plys)
                elif course_data[name]['type'] == 'kenna':
                    results = fetch_kenna(name, d_str, plys)
                else:
                    results = []
                    
                results = filter_by_time(results, t_after, t_before)
                
                if not results:
                    st.info("No tee times found matching your criteria.")
                    
                for r in results:
                    with st.container():
                        col_t, col_d, col_b = st.columns([1.5, 3, 1.5])
                        with col_t: st.subheader(f"⏰ {r['time']}")
                        with col_d: 
                            st.write(f"**{r['course']}** | {r['rate']}")
                            st.caption(f"🏌️ {r['players']} players | 💵 {r['price']}")
                        with col_b: st.link_button("Book", r['link'], use_container_width=True)
                        st.divider()

        elif view_mode == "All Courses Daily View":
            st.markdown("""
            <style>
                div.element-container:has(.sticky-header) {
                    position: sticky;
                    top: 2.875rem; 
                    z-index: 999;
                    padding-top: 0.5rem;
                    padding-bottom: 0.5rem;
                    border-bottom: 1px solid rgba(128, 128, 128, 0.2);
                    background-color: #FFFFFF; 
                }
                [data-theme="dark"] div.element-container:has(.sticky-header) {
                    background-color: #1A1D21; 
                }
            </style>
            """, unsafe_allow_html=True)

            ui_cols = st.columns(len(selected_courses))
            
            for idx, name in enumerate(selected_courses):
                with ui_cols[idx]:
                    st.markdown(f"<div class='sticky-header'><h3 style='margin:0;'>{name}</h3></div>", unsafe_allow_html=True)
                    
                    # --- OVERRIDE FOR MARINE PARK ---
                    if course_data[name]['type'] == 'golfnow_link':
                        mp_link = course_data[name]['link']
                        st.info(f"Data Not Pullable. Click [HERE]({mp_link}) for GolfNow Link")
                        continue # Skips the rest of the logic for Marine Park
                        
                    if course_data[name]['type'] == 'chronogolf_v2':
                        results = fetch_skyway(d_str, plys)
                    elif course_data[name]['type'] == 'kenna':
                        results = fetch_kenna(name, d_str, plys)
                    else:
                        results = []
                        
                    results = filter_by_time(results, t_after, t_before)
                        
                    for r in results:
                        with st.container(border=True):
                            st.write(f"**{r['time']}**")
                            st.caption(f"🏌️ {r['players']} | {r['price']}")
                            st.link_button("Book", r['link'], use_container_width=True)
                    if not results: 
                        st.info("No times.")

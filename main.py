import streamlit as st
import requests
import datetime
from zoneinfo import ZoneInfo
from curl_cffi import requests as curl_requests

# --- 1. Page Setup ---
st.set_page_config(page_title="NYC Tee Times", page_icon="⛳", layout="wide")
st.title("⛳ NYC Municipal Tee Times")

# --- 2. Data Structures ---
course_data = {
    "Pelham Bay": {"fac_id": "4111", "crs_id": "54f14cc00c8ad60378b02cc5", "alias": "pelham-bay-split-rock", "url": "pelham-bay-split-rock.book.teeitup.com", "type": "kenna"},
    "Split Rock": {"fac_id": "4111", "crs_id": "PENDING", "alias": "pelham-bay-split-rock", "url": "pelham-bay-split-rock.book.teeitup.com", "type": "kenna"},
    "Van Cortlandt": {"fac_id": "5043", "crs_id": "ANY", "alias": "golf-nyc", "url": "golf-nyc.book.teeitup.com", "type": "kenna"},
    "Dyker Beach": {"fac_id": "4048", "crs_id": "ANY", "alias": "dyker-beach-golf-course", "url": "dyker-beach-golf-course.book.teeitup.com", "type": "kenna"},
    "Forest Park": {"fac_id": "5045", "crs_id": "ANY", "alias": "golf-nyc", "url": "golf-nyc.book.teeitup.com", "type": "kenna"},
    "Douglaston": {"fac_id": "5044", "crs_id": "ANY", "alias": "douglaston-golf-course", "url": "douglaston-golf-course.book.teeitup.com", "type": "kenna"},
    "Dunwoodie": {"fac_id": "5814", "crs_id": "ANY", "alias": "westchester-county", "url": "westchester-county.book.teeitup.com", "type": "kenna"},
    "Skyway": {
        "fac_id": "0b833d14-8c0d-46ca-82e6-7b992de4761e", 
        "alias": "skyway-golf-course", 
        "type": "chronogolf_v2"
    }
}

# --- 3. Helper: Skyway v2 Adapter ---
def fetch_skyway(date_str, players):
    c_info = course_data["Skyway"]
    full_url = (
        f"https://www.chronogolf.com/marketplace/v2/teetimes?"
        f"start_date={date_str}&"
        f"course_ids={c_info['fac_id']}&"
        f"holes=9&page=1"
    )
    
    headers = {
        "accept": "application/json",
        "referer": f"https://www.chronogolf.com/club/{c_info['alias']}?date={date_str}",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "x-requested-with": "XMLHttpRequest"
    }
    
    try:
        resp = curl_requests.get(full_url, headers=headers, impersonate="chrome110")
        if resp.status_code == 200:
            data = resp.json()
            slots = data.get('teetimes', [])
            standardized_times = []
            
            for s in slots:
                min_p = s.get('min_player_size', 1)
                max_p = s.get('max_player_size', 4)
                if players != "Any" and not (min_p <= int(players) <= max_p):
                    continue
                
                price_val = s.get('default_price', {}).get('subtotal', 0.0)
                
                standardized_times.append({
                    "time": s.get('start_time'),
                    "course": "Skyway",
                    "rate": s.get('default_price', {}).get('affiliation_type', 'Standard'),
                    "price": f"${price_val:.2f}",
                    "players": f"{min_p}-{max_p}",
                    "link": f"https://www.chronogolf.com/club/{c_info['alias']}?date={date_str}"
                })
            return standardized_times
    except Exception:
        return []
    return []

# --- 4. Helper: The Kenna Adapter (Existing Logic) ---
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

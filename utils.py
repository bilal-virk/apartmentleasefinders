import requests
import logging
import os 
from dotenv import load_dotenv
load_dotenv()
from rapidfuzz import process, fuzz
import re
import traceback
logger = logging.getLogger("customLogger")
logger.setLevel(logging.INFO)
file_handler = logging.FileHandler(os.path.join(os.getcwd(), 'App.log'), encoding="utf-8")
file_handler.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)

def pwrite(*args, p=True):
    try:
        message = " ".join(str(arg) for arg in args)

        logger.info(message)
        if p:
            
            try:
                print(message)
            except UnicodeEncodeError:
                # Strip or replace unencodable characters for Windows console
                safe_message = message.encode('cp1252', errors='replace').decode('cp1252')
                print(safe_message)
    except:
        pass
def normalize_location(text):
    """Normalize location strings for better fuzzy matching."""
    text = text.lower()                  # lowercase
    text = re.sub(r"[&/]", " ", text)   # replace & and / with space
    text = re.sub(r"[^\w\s]", "", text) # remove punctuation
    text = re.sub(r"\s+", " ", text)    # collapse multiple spaces
    return text.strip()
def ensure_property_fields(base_id, table_name, api_key):
    meta_url = f"https://api.airtable.com/v0/meta/bases/{base_id}/tables"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    meta_resp = requests.get(meta_url, headers=headers)
    tables = meta_resp.json().get("tables", [])
    table_id = next((t["id"] for t in tables if t["name"] == table_name), None)
    if not table_id:
        print(f"Warning: could not find table ID for '{table_name}'")
        return
    fields_url = f"https://api.airtable.com/v0/meta/bases/{base_id}/tables/{table_id}/fields"
    fields_to_create = [
        {
            "name": "Tour Confirmed",
            "type": "checkbox",
            "options": {"icon": "check", "color": "greenBright"}
        },
        {
            "name": "Tour Email Sent",
            "type": "checkbox",
            "options": {"icon": "check", "color": "blueBright"}
        }
    ]
    for field in fields_to_create:
        resp = requests.post(fields_url, json=field, headers=headers)
        if resp.status_code not in (200, 201, 422):
            print(f"Warning: could not create '{field['name']}' field: {resp.text}")
def click_checkbox_by_value(page, preferred_location: str, values, min_score=40):
    """
    Dynamically click a checkbox that best matches the given preferred_location.
    Uses normalized strings + token_set_ratio for better fuzzy matching.
    """

    if not values:
        raise ValueError("No checkbox values found on the page.")

    # Normalize all values
    normalized_values_map = {normalize_location(v): v for v in values}
    normalized_preferred = normalize_location(preferred_location)

    # Fuzzy match
    best_normalized_match, score, _ = process.extractOne(
        normalized_preferred,
        normalized_values_map.keys(),
        scorer=fuzz.token_set_ratio
    )
    best_match = normalized_values_map[best_normalized_match]

    pwrite(f"[INFO] Looking for '{preferred_location}', best match = '{best_match}' (score={score})")

    if score < min_score:
        raise ValueError(f"No good match found for '{preferred_location}' (score={score})")

    # Click the matching checkbox input directly
    page.locator(f"input[value='{best_match}']").click()
    pwrite(f"[OK] Clicked checkbox for: {best_match}")

def click_checkbox_by_mapping(preferred_locations, page):
    import json
    with open("regions.json", "r") as f:
        data = json.load(f)
        actual_locations = set()
        for i in preferred_locations:
            for j in data.get(i):
                actual_locations.add(j)
        for i in actual_locations:
            page.locator(f"input[value='{i}']").click()
            pwrite(f"[OK] Clicked checkbox for: {i}")

def get_checkboxes(page, budget, br):
    rows = page.locator("#ctl00_ContentPlaceHolder_PropertiesGrid_ctl00 tr")
    count = rows.count()
    properties = []
    if budget<=1200:
        max_properties = 20
    else:
        max_properties = 20
    counter = 0 
    lst = ["Class A", "Class B", "Class C"]
    # if budget == 1500 and (br == '2' or br == '3'):
    #     lst = ["Class C"]
    # else:
    #     lst = ["Class A", "Class B", "Class C"]
    while len(properties) < max_properties and counter<len(lst):
        for i in range(count):
            row = rows.nth(i)

            # Grab the text for this row
            row_text = row.inner_text()
            # Look for "Class A"
            if lst[counter] in row_text:
                checkbox = row.locator("input[type='checkbox']")
                property_name = row.locator("a").nth(0).inner_text()
                properties.append({
                    "name": property_name.strip(),
                    "checkbox": checkbox
                })
        counter += 1


    return properties


def select_background_issues(page, issues):

    if isinstance(issues, str):
        issues = [issues]

    if not issues:
        pwrite("[WARN] No issues provided")
        return

    for issue in issues:
        if not issue or str(issue).strip() == "" or "none" in str(issue).lower():
            continue

        # Handle special mapping
        if issue == "Active Rental Debt":
            mapped_issue = "Broken Lease"
            id_selector = "#ctl00_ContentPlaceHolder_eviction_notPaidOff"
        else:
            mapped_issue = issue
            id_selector = None

        locator = page.locator(f'//input[@type="checkbox" and @value="{mapped_issue}"]')

        if locator.count() > 0:
            locator.first.click()
            pwrite(f"[OK] Selected background issue: {mapped_issue}")

            if id_selector:
                page.locator(id_selector).click()
                pwrite(f"[OK] Selected related checkbox: {id_selector}")
        else:
            pwrite(f"[WARN] No checkbox found for: {mapped_issue} and xpath {f"//input[@type='checkbox' and @value='{mapped_issue}']"}")




def select_form_letter(page, letter_name: str):
    """
    Select a form letter from Telerik RadComboBox dropdown by visible text.
    Example: "Here is the list of apartments you requested"
    """

    # Step 1: Click dropdown input to expand options
    xpath = f'//li[text()="{letter_name}"]'
    input_box = page.locator("#ctl00_ContentPlaceHolder_formLetter_Input")
    input_box.wait_for(state="visible", timeout=100000)
    input_box.click()
    page.wait_for_selector(f'xpath={xpath}', timeout=10000)
    option = page.locator(f'xpath={xpath}')
    option.wait_for(state="visible", timeout=10000)
    page.wait_for_timeout(500)
    option.click()
    pwrite(f"[OK] Selected form letter: {letter_name}")



def regex_for_manager_name(text):
    match = re.search(r"Onsite Manager:\s*(.+)", text)
    if match:
        name = match.group(1).strip()
        return name

def process_property_rows(page, row_selector: str, link_selector: str, data_selectors: tuple[str, str]):
    """
    Click property links in table rows, extract data from new tab, then close it.

    Args:
        page: Playwright page object.
        row_selector: CSS selector for each <tr> row.
        link_selector: CSS selector (relative to row) for the <a> link.
        data_selectors: Tuple of two selectors to extract from the property details tab.
    """
    rows = page.locator(row_selector)
    row_count = rows.count()
    pwrite(f"[INFO] Found {row_count} property rows.")

    results = []

    for i in range(row_count):
        row = rows.nth(i)
        link = row.locator(link_selector)

        with page.context.expect_page() as new_page_info:
            link.click()

        new_page = new_page_info.value
        new_page.wait_for_load_state("domcontentloaded")

        # # Extract the 2 required data points
        # data1 = new_page.locator(data_selectors[0]).inner_text(timeout=10000)
        # data2 = new_page.locator(data_selectors[1]).inner_text(timeout=10000)

        results.append({
            "name": link.inner_text(),
            "data1": "data1",
            "data2": "data2"
        })
        pwrite(f"[DATA] {results[-1]}")

        new_page.close()

    pwrite("[DONE] Finished processing all rows.")
    return results


def format_phone_number(str1):
    # Remove all non-digit characters
    digits = re.sub(r'\D', '', str1)
    
    # Add +1 if no country code is present
    if str1.strip().startswith('+'):
        return f"+{digits}"
    else:
        return f"+1{digits}"
    
def format_phone_number_without_code(str1):
    # Remove all non-digit characters
    digits = re.sub(r'\D', '', str1)
    # Remove leading country code if number has more than 10 digits
    if len(digits) > 10:
        digits = digits[-10:]  # Keep only the last 10 digits
    return digits

def get_first_name(name):
    return name.split()[0]


def get_zipcode(address):
    zipcode = address.split(',')[-1].strip()
    #format to usable format
    zipcode = zipcode.split()[-1] + ',US'
    return zipcode


def get_lat_lon(zip):
    response = requests.get("http://api.openweathermap.org/geo/1.0/zip",params={
    "zip": zip,
    "appid": os.environ['OPENWEATHER_API_KEY']
    })
    if response.status_code == 200:
        response = response.json()
        return {
            'lat': response['lat'],
            'lon': response['lon']
            }
    else:
        return response.status_code
def get_walkscore_bikescore(lat, lon):
    response = requests.get("https://api.walkscore.com/score",params={
        "lat":lat,
        "lon":lon,
        "format":"json",
        # "address": "555 Butterfield Rd",
        "transit": 1,
        "bike": 1,
        "wsapikey": os.environ['WALKSCORE_API_KEY']
    })
    if response.status_code == 200:
        response = response.json()
        return {
            'walkscore': response['walkscore'],
            'bikescore': response['bike']['score']
            }
    else:
        return response.status_code
    

from datetime import datetime, time as dtime
import time  # for time.sleep()

def check_time_within_range():
    now = datetime.now().time()

    start = dtime(19, 30)  # 7:30 PM
    end = dtime(20, 0)     # 8:00 PM

    return not (start <= now <= end)


def safe_fill(page, selector: str, value: str):
    """
    Clears the input field (even if it has placeholder text) and fills it with the given value.
    """
    if not value:
        return
    field = page.locator(selector)
    field.wait_for(state="visible", timeout=10000)
    field.click()
    field.press("Control+A")
    field.press("Backspace")
    field.fill(value)
def extract_rating(text: str) -> float:
        if not text:
            return 0.0
        match = re.search(r'(\d+(\.\d+)?)', text)
        if match:
            return float(match.group(1))
        stars = text.count("★")
        return float(stars) if stars > 0 else 0.0
def select_properties(page, MAX_SELECT=20, has_eviction=None, has_background_issues=None):
    rows = page.locator('//tr[@propertyid]')
    count = rows.count()
    properties = []
    
    has_issues = has_eviction is True or has_background_issues is True
    # Lower the rating threshold if applicant has issues

    for i in range(count):
        row = rows.nth(i)
        
        # Get rating
        rating_locator = row.locator('xpath=.//*[@class="review-rating"]')
        if rating_locator.count() > 0:
            rating_text = rating_locator.first.inner_text().strip()
            rating = extract_rating(rating_text)
        else:
            rating = 4.5

        # Get class
        class_locator = row.locator('xpath=.//*[contains(text(), "Class")]')
        if class_locator.count() == 0:
            continue
        class_text = class_locator.first.inner_text().strip()
        if "Class A" in class_text:
            prop_class = "A"
        elif "Class B" in class_text:
            prop_class = "B"
        elif "Class C" in class_text:
            prop_class = "C"
        else:
            continue

        properties.append({
            "index": i,
            "rating": rating,
            "class": prop_class
        })

    # ── Normal applicant (no issues): A >= 4, B >= 4, A < 4, B < 4
    # ── Applicant with issues: same groups but extended down to 2.0
    #    + extra groups for 2.0–3.5 range + Class C

    if not has_issues:
        # Original priority order
        class_a_high = sorted([p for p in properties if p["class"] == "A" and p["rating"] >= 4.0], key=lambda x: x["rating"], reverse=True)
        class_b_high = sorted([p for p in properties if p["class"] == "B" and p["rating"] >= 4.0], key=lambda x: x["rating"], reverse=True)
        class_a_low  = sorted([p for p in properties if p["class"] == "A" and p["rating"] < 4.0],  key=lambda x: x["rating"], reverse=True)
        class_b_low  = sorted([p for p in properties if p["class"] == "B" and p["rating"] < 4.0],  key=lambda x: x["rating"], reverse=True)

        groups = [class_a_high, class_b_high, class_a_low, class_b_low]

    else:
        # Priority 1: Class A >= 4.0
        class_a_high    = sorted([p for p in properties if p["class"] == "A" and p["rating"] >= 4.0],          key=lambda x: x["rating"], reverse=True)
        # Priority 2: Class B >= 4.0
        class_b_high    = sorted([p for p in properties if p["class"] == "B" and p["rating"] >= 4.0],          key=lambda x: x["rating"], reverse=True)
        # Priority 3: Class A 3.5 < rating < 4.0
        class_a_mid     = sorted([p for p in properties if p["class"] == "A" and 3.5 < p["rating"] < 4.0],    key=lambda x: x["rating"], reverse=True)
        # Priority 4: Class B 3.5 < rating < 4.0
        class_b_mid     = sorted([p for p in properties if p["class"] == "B" and 3.5 < p["rating"] < 4.0],    key=lambda x: x["rating"], reverse=True)
        # Priority 5: Class A 2.0 <= rating <= 3.5 (compromise zone)
        class_a_low     = sorted([p for p in properties if p["class"] == "A" and p["rating"] <= 3.5],          key=lambda x: x["rating"], reverse=True)
        # Priority 6: Class B 2.0 <= rating <= 3.5 (compromise zone)
        class_b_low     = sorted([p for p in properties if p["class"] == "B" and p["rating"] <= 3.5],          key=lambda x: x["rating"], reverse=True)
        # Priority 7: Class C (all ratings, sorted by rating desc)
        class_c_all     = sorted([p for p in properties if p["class"] == "C"],                                  key=lambda x: x["rating"], reverse=True)

        # Priority 8: Class A & B rating < 2.0
        class_a_vlow = sorted([p for p in properties if p["class"] == "A" and p["rating"] < 2.0], key=lambda x: x["rating"], reverse=True)
        class_b_vlow = sorted([p for p in properties if p["class"] == "B" and p["rating"] < 2.0], key=lambda x: x["rating"], reverse=True)
        class_c_vlow = sorted([p for p in properties if p["class"] == "C" and p["rating"] < 2.0], key=lambda x: x["rating"], reverse=True)

        groups = [class_a_high, class_b_high, class_a_mid, class_b_mid, class_a_low, class_b_low, class_c_all, class_a_vlow, class_b_vlow, class_c_vlow]

    # Merge in priority order
    selected = []
    for group in groups:
        selected.extend(group)

    # Cap at MAX_SELECT
    selected = selected[:MAX_SELECT]

    # Click checkboxes
    for prop in selected:
        row = rows.nth(prop["index"])
        checkbox = row.locator('xpath=.//*[@type="checkbox"]')
        if checkbox.count() > 0:
            checkbox.first.click()

    return len(selected)
PROPERTY_AMENITIES_MAP = {
    # High Value
    "Locker Systems": ["Locker Systems"],
    "Package Services": ["Package Services"],
    "Wi-Fi Access": ["Wi-Fi Access", "Wifi Access"],
    "Concierge Services": ["Concierge Services"],
    "Rooftop Amenities": ["Rooftop Amenities"],
    "Virtual Fitness": ["Virtual Fitness"],
    "Smoke Free Community": ["Smoke Free Community"],
    "Gameroom": ["Gameroom", "Game Room"],
    "Outdoor Kitchens": ["Outdoor Kitchens"],
    "Dry Cleaning / Laundry Services": ["Dry Cleaning / Laundry Services", "Dry Cleaning/Laundry Services"],
    "Co-Working Area": ["Co-Working Area", "Co Working Area"],
    "Doorman": ["Doorman"],
    "Fiber optic lines": ["Fiber optic lines", "Fiber Optic Lines"],
    "Pet Washing Stations": ["Pet Washing Stations"],
    "Bike Storage": ["Bike Storage"],
    "Valet Parking": ["Valet Parking"],
    "Yellow Rooms": ["Yellow Rooms"],
    "Electric Car Charging Stations": ["Electric Car Charging Stations", "Electric Car Charger"],
    "Ride Sharing Lounge": ["Ride Sharing Lounge"],
    "Recycling": ["Recycling"],
    "Golf Simulator": ["Golf Simulator"],

    # Fitness & Sports
    "Basketball Courts": ["Basketball Courts"],
    "Golf Course": ["Golf Course"],
    "Tennis Court": ["Tennis Court"],
    "Swimming Pool": ["Swimming Pool"],
    "Racquetball Court": ["Racquetball Court"],
    "Volleyball Court": ["Volleyball Court"],
    "Jogging Trail": ["Jogging Trail"],
    "Fitness Center": ["Fitness Center", "Gym/Fitness Center"],

    # Private Parking
    "Attached Private Garage": ["Attached Private Garage"],
    "Detached Private Garage": ["Detached Private Garage"],

    # Shared Parking
    "Reserved Spaces": ["Reserved Spaces"],
    "Parking Garage Lot": ["Parking Garage Lot"],
    "Covered Spaces": ["Covered Spaces"],
    "Breezeway Parking": ["Breezeway Parking"],

    # Entertainment
    "Picnic Area": ["Picnic Area"],
    "Billiard Room": ["Billiard Room"],
    "Clubhouse": ["Clubhouse"],
    "Playground": ["Playground"],
    "Spa/Jacuzzi": ["Spa/Jacuzzi", "Spa / Jacuzzi"],
    "Cinema Room": ["Cinema Room"],

    # Other
    "Valet Trash Service": ["Valet Trash Service"],
    "Dog/Walk Trail": ["Dog/Walk Trail", "Dog Walk Trail"],
    "Laundry Rooms": ["Laundry Rooms", "Onsite Laundry Rooms"],
    "Roommate Floorplans": ["Roommate Floorplans"],

    # Accessibility
    "School Bus Pickup": ["School Bus Pickup"],
    "On Shuttle/Bus Route": ["On Shuttle/Bus Route"],
    "Elevators": ["Elevators"],
    "Handicap Friendly": ["Handicap Friendly"],

    # Safety
    "Gated with access code": ["Gated with access code"],
    "Fenced Yards": ["Fenced Yards"],
    "Fenced Community": ["Fenced Community"],
}

UNIT_AMENITIES_MAP = {
    # High Value
    "Smart Technology In Unit": ["Smart Technology In Unit"],
    "Vinyl Flooring": ["Vinyl Flooring", "Vinyl /Laminate Floors", "Vinyl/Laminate Floors"],
    "Gas Appliances": ["Gas Appliances"],
    "Kitchen Islands": ["Kitchen Islands"],
    "Quartz Countertops": ["Quartz Countertops"],
    "Marble Countertops": ["Marble Countertops"],
    "Tile Backsplash": ["Tile Backsplash"],
    "High Ceilings": ["High Ceilings"],
    "USB outlets": ["USB outlets", "USB Outlets"],
    "Walk-in Shower": ["Walk-in Shower"],

    # Washer/Dryer
    "Fullsize - connections": ["Fullsize - connections", "Fullsize - Connections"],
    "Fullsize - supplied": ["Fullsize - supplied", "Fullsize - Supplied"],
    "Stackable - connections": ["Stackable - connections", "Stackable - Connections"],
    "Stackable - supplied": ["Stackable - supplied", "Stackable - Supplied"],

    # Kitchen
    "Microwave": ["Microwave"],
    "Dishwasher": ["Dishwasher"],
    "Pantry": ["Pantry"],
    "Granite Counters": ["Granite Counters"],
    "Black/Stainless Appliances": ["Black/Stainless Appliances"],

    # Living
    "Walk-in Closet": ["Walk-in Closet"],
    "Patio": ["Patio", "Patio/ Balcony", "Patio/Balcony"],
    "Outside Storage": ["Outside Storage"],
    "Bay Windows": ["Bay Windows"],
    "Dry/Wet Bar": ["Dry/Wet Bar"],

    # Comfort & Safety
    "Furnished Unit": ["Furnished Unit"],
    "Fireplace": ["Fireplace"],
    "Wood Floors": ["Wood Floors"],
    "Garden Tubs": ["Garden Tubs"],
    "Laminate Floors": ["Laminate Floors"],
    "Alarm System": ["Alarm System"],
    "Ceramic Tile": ["Ceramic Tile"],
    "Ceiling Fans": ["Ceiling Fans"],
    "Stained Concrete Floors": ["Stained Concrete Floors"],
}


def smart_data_to_website_label(smart_value, amenity_map):
    """Case-insensitive translation from Smart Apartment Data value to Website label."""
    smart_value_lower = smart_value.lower().strip()
    for website_label, smart_values in amenity_map.items():
        for sv in smart_values:
            if sv.lower().strip() == smart_value_lower:
                return website_label
    return None


def click_amenities(page, amenities_list, amenity_map):
    """Click amenity checkboxes using case-insensitive label matching."""
    if not amenities_list:
        pwrite("[SKIP] No amenities provided")
        return

    for smart_value in amenities_list:
        smart_value = smart_value.strip()
        website_label = smart_data_to_website_label(smart_value, amenity_map)

        if website_label is None:
            pwrite(f"[NOT MAPPED] {smart_value}, trying direct match")
            website_label = smart_value

        # Build list of variants to try (all from map + website_label itself)
        all_variants = amenity_map.get(website_label, [website_label])
        all_variants = [website_label] + [v for v in all_variants if v != website_label]

        clicked = False
        for variant in all_variants:
            # Case-insensitive XPath using translate()
            variant_lower = variant.lower()
            xpath = (
                f'//label[translate(normalize-space(.), '
                f'"ABCDEFGHIJKLMNOPQRSTUVWXYZ", '
                f'"abcdefghijklmnopqrstuvwxyz")="{variant_lower}"]'
            )
            try:
                locator = page.locator(f'xpath={xpath}')
                if locator.count() > 0:
                    locator.first.click()
                    pwrite(f"[OK] Clicked: {variant} (from: {smart_value})")
                    clicked = True
                    break
            except Exception as e:
                pwrite(f"[ERROR] clicking variant {variant}: {e}")
                continue

        if not clicked:
            pwrite(f"[NOT FOUND] {website_label} (from: {smart_value}) — tried: {all_variants}")
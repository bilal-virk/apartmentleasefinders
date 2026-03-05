import requests 
import os 
from dotenv import load_dotenv
load_dotenv()
from rapidfuzz import process, fuzz
import re

def normalize_location(text):
    """Normalize location strings for better fuzzy matching."""
    text = text.lower()                  # lowercase
    text = re.sub(r"[&/]", " ", text)   # replace & and / with space
    text = re.sub(r"[^\w\s]", "", text) # remove punctuation
    text = re.sub(r"\s+", " ", text)    # collapse multiple spaces
    return text.strip()

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

    print(f"[INFO] Looking for '{preferred_location}', best match = '{best_match}' (score={score})")

    if score < min_score:
        raise ValueError(f"No good match found for '{preferred_location}' (score={score})")

    # Click the matching checkbox input directly
    page.locator(f"input[value='{best_match}']").click()
    print(f"[OK] Clicked checkbox for: {best_match}")

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
            print(f"[OK] Clicked checkbox for: {i}")

def get_checkboxes(page, budget, br):
    rows = page.locator("#ctl00_ContentPlaceHolder_PropertiesGrid_ctl00 tr")
    count = rows.count()
    properties = []
    if budget<=1200:
        max_properties = 20
    else:
        max_properties = 30
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


def select_background_issues(page, issue):
    """
    Selects background issue checkboxes based on the list of values provided.
    Example: ["Eviction", "Felony", "Active Rental Debt"]
    """
    # Handle special case mapping
    if issue == "Active Rental Debt":
        mapped_issue = "Broken Lease"
        id_selector = "#ctl00_ContentPlaceHolder_eviction_notPaidOff"
    else:
        mapped_issue = issue
        id_selector = None

    locator = page.locator(f"input[type='checkbox'][value='{mapped_issue}']")
    if locator.count() > 0:
        locator.first.click()
        print(f"[OK] Selected background issue: {mapped_issue}")

        # Click additional element if defined
        if id_selector:
            page.locator(id_selector).click()
            print(f"[OK] Selected related checkbox: {id_selector}")
    else:
        print(f"[WARN] No checkbox found for: {mapped_issue}")




def select_form_letter(page, letter_name: str):
    """
    Select a form letter from Telerik RadComboBox dropdown by visible text.
    Example: "Here is the list of apartments you requested"
    """

    # Step 1: Click dropdown input to expand options
    input_box = page.locator("#ctl00_ContentPlaceHolder_formLetter_Input")
    input_box.wait_for(state="visible", timeout=100000)
    input_box.click()

    # Step 2: Wait for dropdown list to appear
    options = page.locator("ul.rcbList li.rcbItem")
    options.first.wait_for(state="visible", timeout=100000)

    # Step 3: Try to select requested letter
    option = options.filter(has_text=letter_name)
    if option.count() > 0:
        option.first.click()
        print(f"[OK] Selected form letter: {letter_name}")
    else:
        # Fallback: pick the first available option
        print(f"[WARN] Could not find form letter '{letter_name}', selecting first available.")
        options.first.click()


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
    print(f"[INFO] Found {row_count} property rows.")

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
        print(f"[DATA] {results[-1]}")

        new_page.close()

    print("[DONE] Finished processing all rows.")
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
def select_properties(page,MAX_SELECT=20):
    rows = page.locator('//tr[@propertyid]')
    count = rows.count()
    properties = []
    for i in range(count):
        row = rows.nth(i)
        rating_locator = row.locator('.//*[@class="review-rating"]')
        if rating_locator.count() > 0:
            rating_text = rating_locator.first.inner_text().strip()
            rating = extract_rating(rating_text)
        else:
            rating = 0.0 
        class_locator = row.locator('.//*[contains(text(), "Class")]')
        if class_locator.count() == 0:
            continue
        class_text = class_locator.first.inner_text().strip()
        if "Class A" in class_text:
            prop_class = "A"
        elif "Class B" in class_text:
            prop_class = "B"
        else:
            continue
        properties.append({
            "index": i,
            "rating": rating,
            "class": prop_class
        })
    class_a_rated = [p for p in properties if p["class"] == "A" and p["rating"] > 3]
    class_b_rated = [p for p in properties if p["class"] == "B" and p["rating"] > 3]
    class_a_low = [p for p in properties if p["class"] == "A" and p["rating"] <= 3]
    class_b_low = [p for p in properties if p["class"] == "B" and p["rating"] <= 3]
    class_a_rated.sort(key=lambda x: x["rating"], reverse=True)
    class_b_rated.sort(key=lambda x: x["rating"], reverse=True)

    selected = []
    selected.extend(class_a_rated)
    selected.extend(class_b_rated)
    selected.extend(class_a_low)
    selected.extend(class_b_low)    
    if len(selected) < MAX_SELECT:
        remaining = [p for p in properties if p not in selected]
        remaining.sort(key=lambda x: x["rating"], reverse=True)
        selected.extend(remaining[:MAX_SELECT - len(selected)])
    selected = selected[:MAX_SELECT]
    for prop in selected:
        row = rows.nth(prop["index"])
        checkbox = row.locator('.//*[@type="checkbox"]')
        if checkbox.count() > 0:
            checkbox.first.click()
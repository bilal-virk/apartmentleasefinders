import os
from pathlib import Path
from robocorp.tasks import task
from robocorp import browser
import json
import time
import re
import pandas as pd
from pyairtable import Api
import requests 
import sys
from dotenv import load_dotenv
load_dotenv()

from utils import *


@task
def smartapartment_insert_data():
    try:
        # Open and read JSON file
        with open("client.json", "r") as file:
            data = json.load(file)
        must_have_property_amenities = data.get('"Must Have" Property Amenities', [])
        must_have_unit_amenities = data.get('"Must Have" Unit Amenities', [])
        # if not data['first_name'] in ['Koushik', 'Arathy', "Pradeep", "Sarah", "Darwin"]:
        #     sys.exit(0)
        #     return
        locations = [
            data.get("Preferred Location DTX"),
            data.get("Preferred Location HTX"),
            data.get("Preferred Location ATX"),
            (data.get("Preferred Location") or [None])[0]
        ]

        def is_empty(value):
            return value in [None, "", "None"]

        def is_help(value):
            return value == "I don't know. Help!"

        def is_real(value):
            return not is_empty(value) and not is_help(value)
        def has_data(value):
            if value is None:
                return None
            if isinstance(value, str) and value.strip() == "":
                return None
            if isinstance(value, (list, dict)) and len(value) == 0:
                return None
            return True

        has_eviction = has_data(data.get("Eviction and History", None))
        has_background_issues = has_data(data.get("Background Issues", None))

        has_help = any(is_help(v) for v in locations)
        has_real = any(is_real(v) for v in locations)

        if has_help and not has_real:
            pwrite("Preferred Location is I don't know help")
            sys.exit(0)
            return 
        tags = data.get('Tags', [])
        tags_str = " ".join(tags).lower()
        playwright = browser.playwright()
        chromium = playwright.chromium
        browser_app = chromium.connect_over_cdp("http://localhost:9222")

        # Pick the first available context/page, or create a new one
        context = browser_app.contexts[0] if browser_app.contexts else browser_app.new_context()
        page = context.new_page()

        # Navigate to SmartApartmentData with logged-in profile
        page.goto("https://app.smartapartmentdata.com/Restricted/Account/MyDashboard.aspx")

        #click on create new client
        page.click("#ctl00_ContentPlaceHolder_newClientLink")

        # fill details
        # data.get('first_name') and page.fill("input[name='ctl00$ContentPlaceHolder$firstnameInput']", data['first_name'])
        # data.get('last_name') and page.fill("input[name='ctl00$ContentPlaceHolder$lastnameInput']", data['last_name'])
        safe_fill(page, "input[name='ctl00$ContentPlaceHolder$firstnameInput']", data.get('first_name'))
        safe_fill(page, "input[name='ctl00$ContentPlaceHolder$lastnameInput']", data.get('last_name'))

        data.get('email') and page.fill("input[name='ctl00$ContentPlaceHolder$emailInput']", data['email'])
        data.get('phone') and page.fill("input[name='ctl00$ContentPlaceHolder$primaryPhone']", format_phone_number_without_code(data['phone']))
        page.fill("input[name='ctl00$ContentPlaceHolder$status']", "Active - Looking")
        page.fill("input[name='ctl00$ContentPlaceHolder$source']", "Internet")
        page.fill("input[name='ctl00$ContentPlaceHolder$moveInDate$dateInput']", data["Ideal Move In Date"])
        time.sleep(3)
        #save
        page.click("#ctl00_NavigationPlaceHolder_saveBtn")
        time.sleep(3)
        #build search
        page.click("#ctl00_NavigationPlaceHolder_buildSearch")

        # fill max monthly budget
        min_budget = int(data.get("Ideal Monthly Budget Value", 0)) - 500
        max_budget = int(data.get("Ideal Monthly Budget Value", 0)) + 100
        page.fill("input[name='ctl00$ContentPlaceHolder$priceMin']", str(min_budget))
        page.fill("input[name='ctl00$ContentPlaceHolder$priceMax']", str(max_budget))

        # find min bedrooms using regex
        min_bed = re.findall(r"\d",data['Apartment Size'])[0]
        if min_bed == '0':
            max_bed = '1'
        else:
            max_bed = min_bed

        # fill min and max bedroom
        page.fill("input[name='ctl00$ContentPlaceHolder$bedMin']", min_bed)
        page.fill("input[name='ctl00$ContentPlaceHolder$bedMax']", max_bed)

        # find and fill min and max bathroom
        baths = re.findall(r"\d",data['Number of Bathrooms'])[0]
        page.fill("input[name='ctl00$ContentPlaceHolder$bathMin']", baths)
        page.fill("input[name='ctl00$ContentPlaceHolder$bathMax']",baths)

        # compulsary checkboxes that need to be ticked
        # page.click("#ctl00_ContentPlaceHolder_fullsizeConnection")
        # page.click("#ctl00_ContentPlaceHolder_fullsizeFurnished")
        # page.click("#ctl00_ContentPlaceHolder_stackableConnection")
        # page.click("#ctl00_ContentPlaceHolder_stackableFurnished")
        click_amenities(page, must_have_property_amenities, PROPERTY_AMENITIES_MAP)
        time.sleep(1)
        click_amenities(page, must_have_unit_amenities, UNIT_AMENITIES_MAP)
        # Click the "Policies" tab first
        page.click("span.rtsTxt:text('Policies')")

        # Wait for the tab content to load (adjust selector to something unique in Policies tab)
        page.wait_for_selector("#ctl00_ContentPlaceHolder_seniorCitizenHousingNOT")

        # Then click the desired element
        page.click("#ctl00_ContentPlaceHolder_seniorCitizenHousingNOT")


        # select background issue if any
        background_issues = data.get('Background Issues', "None")
        if background_issues!="None":
            select_background_issues(page, background_issues)

        

        # click on narrow by area
        page.click("#ctl00_ContentPlaceHolder_editAreaLink")

        # Wait until the RadWindow iframe is attached and available
        frame = page.frame_locator("iframe[name='RadWindow']")
        frame.locator("input[type='checkbox']").first.wait_for()


        
        # # Get all checkbox inputs
        # checkboxes = frame.locator("input[type='checkbox']")
        # count = checkboxes.count()
        # values = []
        # for i in range(count):
        #     val = checkboxes.nth(i).get_attribute("value")
        #     if val:
        #         values.append(val)
        # pwrite(values)
        # for loc in data['Preferred Location HTX']:
        #     click_checkbox_by_value(frame, loc, values)
        
        click_checkbox_by_mapping(data.get('Preferred Location', data.get('Preferred Location HTX', '')), frame)

        # close rad window
        frame.locator("#ctl00_ContentPlaceHolder_saveBtn_input").click()

        # search 
        page.click("#ctl00_NavigationPlaceHolder_searchBtn")

        # Wait for the property grid table rows to appear
        page.locator("#ctl00_ContentPlaceHolder_PropertiesGrid_ctl00 tr").first.wait_for()
        budget = data["Ideal Monthly Budget Value"]
        #props = get_checkboxes(page, budget, min_bed)
        # properties = "" #//tr[@propertyid]
        # for prop in props:
        #     pwrite(f"Clicking: {prop['name']}")
        #     prop['checkbox'].click()
        pr_selected = select_properties(page,MAX_SELECT=20, has_eviction=has_eviction, has_background_issues=has_background_issues)
        page.wait_for_timeout(2000)

        page.click("#ctl00_NavigationPlaceHolder_emailBtn")
        

    
        # select email template
        template_to_select = "(Track A 90+) Sending the List"

        if 'track a' in tags_str and '90' in tags_str:
            template_to_select = "(Track A 90+) Sending the List"

        elif 'track a' in tags_str:
            template_to_select = "(Track A) Sending the List"

        elif 'track b' in tags_str and '90' in tags_str:
            template_to_select = "(Track B 90+) Sending the List"

        elif 'track b' in tags_str:
            template_to_select = "(Track B) Sending the List"

        else:
            template_to_select = "(Track A 90+) Sending the List"
        select_form_letter(page, template_to_select)


        # dynamically fill subject line
        # if budget<=1200 and (min_bed==0 or min_bed==1):
        #     subject = f"{data['first_name']}, Here's the apartment info you requested ({min_bed}-{baths} options under {budget} in the {', '.join(data['Preferred Location HTX'])}... let me know your top 3-6 options and we'll call to get the best deal)"
        # else:
        #     subject = f"{data['first_name']}, Here's the apartment info you requested ({min_bed}-{baths} options under {budget} in your areas... I can narrow down to top 5-10 with more info on whats most important to you)"
        
        subject = f"{data['first_name']}, here's the apartment info you requested ({min_bed}-{baths} under ${budget} in {', '.join(data.get('Preferred Location', data.get('Preferred Location HTX', '')))}). Let me know your top 3-6 options, and we'll call the properties to get the best deal."
        time.sleep(2)
        page.fill("input[name='ctl00$ContentPlaceHolder$subject']", subject)
        '''
        {{Client's Name}}, here's the apartment info you requested (1-1 under $____ in these areas). Let me know your top 3-6 options, and we'll call the properties to get the best deal.
        '''
        try:
            frame = page.frame_locator('//iframe[@frameborder="0"]')
            element_contains_number = frame.locator('//*[contains(text(), "[number]")]').first
            text = element_contains_number.inner_text()
            new_text = text.replace("[number]", str(pr_selected))
            element_contains_number.evaluate("(el, value) => el.innerText = value", new_text)
        except:
            pass


        time.sleep(3)

        # click on cc me
        page.click("#ctl00_ContentPlaceHolder_registrationCardCC")

        # click on send email
        page.click("#ctl00_NavigationPlaceHolder_sendBtn")

        time.sleep(5)
        page.close()

        requests.post(url="https://services.leadconnectorhq.com/hooks/QRof2UTEmQswZAiO7A6Q/webhook-trigger/87009a7f-269f-4c86-94b8-98904a296332",json=data) # Webhook to trigger automation on GoHighLevel "Update Stage to List Sent"
    except:        
        pwrite(f"[ERROR] Something went wrong: {traceback.format_exc()}")
    # add functionality to close tab after sending email
    try:
        page.close()    
    except:
        pass
    
    # Screenshot for proof
    # page.screenshot(path="output/smartapartment.png")
    pwrite("[Ok] data added to SMART")





@task
def favorited_properties():
    # Load link from favorites.json
    with open("favorites.json", "r") as f:
        data = json.load(f)
    link = data["link"]
    name = data['name']
    # if not data['name'] in ['Koushik Test', 'Arathy Test', "Pradeep Test", "Sarah Test", "Darwin Test"]:
    #     # sys.exit(0)
    #     return 

    # Attach to Chrome in debug mode
    playwright = browser.playwright()
    chromium = playwright.chromium
    browser_app = chromium.connect_over_cdp("http://localhost:9222")

    context = browser_app.contexts[0] if browser_app.contexts else browser_app.new_context()
    page = context.new_page()
    page.goto(link)

    pwrite(f"[OK] Navigated to {link}")

    # ---- Extract table data ----
    rows = page.query_selector_all("#FavoritesGrid_ctl00 tbody tr")

    properties = []
    for row in rows:
        cols = row.query_selector_all("td")
        if not cols:
            continue

        property_name = cols[0].inner_text().split("\n")[0].strip()
        phone = cols[1].inner_text().strip()
        # address = cols[2].inner_text().strip()
        area = cols[3].inner_text().strip()

        # ---- NEW: open property link in new tab and scrape extra info ----
        link_el = cols[0].query_selector("a.gridResultsItem")
        extra1, extra2 = None, None
        if link_el:
            with page.context.expect_page() as new_page_info:
                link_el.click()
            new_page = new_page_info.value
            new_page.wait_for_load_state("domcontentloaded")

            try:
                address = new_page.locator("#ctl00_ContentPlaceHolder_PropertyHeader1_address").inner_text(timeout=5000) 
                managed_by = new_page.locator("#ctl00_ContentPlaceHolder_mgmtCo").inner_text(timeout=5000)   # replace selector
                manager = new_page.locator("#ctl00_ContentPlaceHolder_OfficeMgr").inner_text(timeout=5000)       # replace selector
                manager = regex_for_manager_name(manager)
            except Exception as e:
                pwrite(f"[WARN] Could not fetch details for {property_name}: {e}")

            new_page.close()
        if address:
            zipcode = get_zipcode(address)
            lat_lon = get_lat_lon(zipcode)
            lat = lat_lon['lat']
            lon = lat_lon['lon']
            walk_bike_score = get_walkscore_bikescore(lat, lon)

        properties.append({
            "Property": property_name,
            "Phone": phone,
            "Address": address,
            "Area": area,
            "Zipcode": get_zipcode(address),
            "Managed By": managed_by,
            "Onsite Manager": get_first_name(manager),
            "Walk Score": walk_bike_score['walkscore'],
            "Bike Score": walk_bike_score['bikescore']
        })

    # ---- Convert to DataFrame ----
    df = pd.DataFrame(properties)

    # Optionally save as CSV/JSON for later use
    df.to_csv("favorites.csv", index=False)
    # After you build df / properties list
    api = Api(os.environ['AIRTABLE_API_KEY'])
    # table = api.table('appA6XNikBFdFgRtF', 'tbltWwPTaTTu5B3Yt')
    table = api.table('appA6XNikBFdFgRtF', name)
    # 1. Fetch all records
    records = table.all()

    # 2. Delete existing records (in batches to avoid hitting API rate limits)
    for record in records:
        table.delete(record['id'])
    # Insert all rows into Airtable
    for prop in properties:
        table.create({
            'Property': prop['Property'],   # make sure these match your Airtable column names
            'Contact Number': format_phone_number(prop['Phone']),
            'Address': prop['Address'],
            'Area': prop['Area'],
            "Zipcode": prop["Zipcode"],
            "Managed By": prop['Managed By'],
            "Onsite Manager": prop['Onsite Manager'],
            "Walk Score": prop['Walk Score'],
            "Bike Score": prop['Bike Score']
        })
    prop_list = []
    for prop in properties:
        prop_list.append(f" {prop['Property']} ")

    page.close()
    requests.post(url="https://services.leadconnectorhq.com/hooks/QRof2UTEmQswZAiO7A6Q/webhook-trigger/b335e765-c182-431b-a24a-a6047730074a",json={"name":name,"properties":prop_list}) # Webhook to trigger automation on GoHighLevel "Send SMS and Email after Client sent Fav and change stage to Client sent Favs"

    pwrite("[OK] Favorites data saved to Airtable")

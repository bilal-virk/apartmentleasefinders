from flask import Flask, request, g
import subprocess
import time
import re
import json
import subprocess
import threading
import os 
from datetime import datetime 
from pyairtable import Api
import os 
from dotenv import load_dotenv
load_dotenv()
import requests
from utils import *
from tasks import smartapartment_insert_data
app = Flask(__name__)


def cleanup_old_logs(max_age_days=30):
    logs_dir = "logs"
    if not os.path.exists(logs_dir):
        return
    cutoff = time.time() - (max_age_days * 86400)
    deleted = 0
    for fname in os.listdir(logs_dir):
        fpath = os.path.join(logs_dir, fname)
        if os.path.isfile(fpath) and os.path.getmtime(fpath) < cutoff:
            os.remove(fpath)
            deleted += 1
    if deleted:
        print(f"[INFO] Cleaned up {deleted} log file(s) older than {max_age_days} days.")


def _cleanup_scheduler():
    while True:
        cleanup_old_logs()
        time.sleep(86400)


threading.Thread(target=_cleanup_scheduler, daemon=True).start()


@app.before_request
def _capture_request():
    g.req_time = datetime.now()
    g.req_body = request.get_data(as_text=True)


@app.after_request
def _log_request_response(response):
    try:
        os.makedirs("logs", exist_ok=True)
        req_time = getattr(g, "req_time", datetime.now())
        req_body = getattr(g, "req_body", "")
        endpoint = request.endpoint or "unknown"
        log_path = f"logs/{endpoint}_{req_time.strftime('%Y%m%d_%H%M%S')}.txt"

        with open(log_path, "w", encoding="utf-8") as f:
            f.write("=" * 60 + "\n")
            f.write(f"ENDPOINT  : {request.path}\n")
            f.write(f"METHOD    : {request.method}\n")
            f.write(f"TIMESTAMP : {req_time.strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write("=" * 60 + "\n\n")

            f.write("--- INPUT ---\n")
            try:
                f.write(json.dumps(json.loads(req_body), indent=4))
            except Exception:
                f.write(req_body or "(empty)")

            f.write("\n\n--- OUTPUT ---\n")
            resp_text = response.get_data(as_text=True)
            try:
                f.write(json.dumps(json.loads(resp_text), indent=4))
            except Exception:
                f.write(resp_text)

            f.write("\n" + "=" * 60 + "\n")
    except Exception as e:
        print(f"[WARN] Request logging failed: {e}")
    return response


def delayed_robot_run(data, delay=1):
    """Run robot after given delay (default = 600s = 10min)."""
    print(f"[INFO] Robot scheduled to run in {delay/60} minutes...")
    #time.sleep(delay)

    # Save data as Robocorp input file
    with open("client.json", "w") as f:
        json.dump(data, f)

    # Run the robot
    subprocess.run(["rcc", "run", "-t", "smartapartment_insert_data"])
    #smartapartment_insert_data()
    print("[OK] Robot run completed.")

@app.route("/smartCreate", methods=["POST"])
def ghl_webhook():
    data = request.json

    # Trigger robot run in background thread (with delay)
    threading.Thread(target=delayed_robot_run, args=(data,)).start()

    return {"status": "RPA started"}




@app.route("/airtable", methods=["POST"])
def airtable_webhook():
    raw_body = request.get_data(as_text=True)
    # optional: if body may be HTML, you can try to get plain text via BeautifulSoup
    try:
        from bs4 import BeautifulSoup
        text = BeautifulSoup(raw_body, "html.parser").get_text("\n")
    except Exception:
        text = raw_body

    # 1) Extract name: take the first non-empty line after "Thought you should know"
    name = None
    m = re.search(r"Thought you should know\.{1,}\s*\n\s*([^\n\[\<]+)", text, re.IGNORECASE)
    if m:
        name = m.group(1).strip()
    else:
        # fallback: take the first non-empty line after the phrase
        p = re.search(r"Thought you should know\.{1,}", text, re.IGNORECASE)
        if p:
            tail = text[p.end():].lstrip()
            first_line = tail.splitlines()[0].strip() if tail.splitlines() else None
            if first_line:
                name = re.sub(r"^[\[\(\s]+", "", first_line).strip()

    # 2) Extract URL that appears after "View favorites" (works with [...], <...>, href="...", or plain)
    link = None
    vp = text.lower().find("view favorites")
    if vp != -1:
        following = text[vp: vp + 800]  # look ahead a bit
        u = re.search(r"https?://[^\s\]\)<>\"']+", following)
        if u:
            link = u.group(0)

    # fallback: any URL anywhere in the text
    if not link:
        u2 = re.search(r"https?://[^\s\]\)<>\"']+", text)
        if u2:
            link = u2.group(0)

    if not name or not link:
        return {"error": "No name or favorites link found", "name": name, "link": link}, 400

    payload = {"name": name, "link": link}
    with open("favorites.json", "w") as f:
        json.dump(payload, f, indent=4)

    # start robot non-blocking — use Popen to avoid blocking the Flask worker
    threading.Thread(
        target=lambda: subprocess.Popen(
            ["rcc", "run", "-t", "favorited_properties"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    ).start()

    return {"status": f"favorited_properties robot started for {name}"}


def save_request_to_json(endpoint, raw_body):
    """Save request body to a timestamped JSON file exactly as received."""
    os.makedirs("logs", exist_ok=True)
    filename = f"logs/{endpoint}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(filename, "w") as f:
        try:
            json.dump(json.loads(raw_body), f, indent=4)
        except Exception:
            f.write(raw_body)
    return filename

@app.route("/client_notes_call", methods=["POST"])
def client_notes_call():
    raw_body = request.get_data(as_text=True)
    file_path = save_request_to_json("client_notes_call", raw_body)
    print(file_path)
    with open(file_path, "r") as file:
        data = json.load(file)
        if data['event']!='call_analyzed':
            return {"status": "Not yet analysed"}
        if data['call']['call_status']!='ended':
            return {"status": "Call not completed"}
        if data['call']['agent_id']!='agent_3cb820727695525a2fbed2bafe':
            return {"status":"not correct agent"}
        client_deets = data['call']['retell_llm_dynamic_variables']
        summary = data['call']['call_analysis']['call_summary']
        requests.post("https://hook.us2.make.com/lmo04f3bkbwpo9n78ml3tbbe55xjvml1",json={
        "name":client_deets.get("client_name"),"phone":client_deets.get("client_phone"),"email":client_deets.get("client_email"),"call_summary":summary},
        headers={
            "x-make-apikey": os.environ['MAKE_KATPRO_API_KEY']
        })
        analysis = data['call']['call_analysis']['custom_analysis_data']
        client_name = client_deets.get("client_name")
        api = Api(os.environ['AIRTABLE_API_KEY'])
        table = api.table('appA6XNikBFdFgRtF', client_name)

        lst = []
        for records in table.iterate(page_size=100, max_records=1000):
            lst += records 
            for i in lst:
                property = i['fields']['Property'].lower()
                print(property, analysis.get('property_1'))
                onsite_manager = i['fields']['Onsite Manager']
                email = i['fields'].get('Email Confirmed','not found')
                payload = {}
                if property==analysis.get('property_1').lower() and analysis.get('property_1_tour_date_time'):
                    payload = {"client_name":client_deets.get("client_name"),"client_phone":client_deets.get("client_phone"),"client_email":client_deets.get("client_email"), 'property_name': analysis.get('property_1'), 'tour_date_time': analysis.get('property_1_tour_date_time', ' '), 'onsite_manager': onsite_manager, 'property_email': email}
                    print(payload, '1')
                elif property==analysis.get('property_2','none').lower() and analysis.get('property_2_tour_date_time'):
                    payload = {"client_name":client_deets.get("client_name"),"client_phone":client_deets.get("client_phone"),"client_email":client_deets.get("client_email"), 'property_name': analysis.get('property_2'), 'tour_date_time': analysis.get('property_2_tour_date_time', ' '), 'onsite_manager': onsite_manager, 'property_email': email}
                    print(payload,'2')
                elif property==analysis.get('property_3', 'none').lower() and analysis.get('property_3_tour_date_time'):
                    payload = {"client_name":client_deets.get("client_name"),"client_phone":client_deets.get("client_phone"),"client_email":client_deets.get("client_email"), 'property_name': analysis.get('property_3'), 'tour_date_time': analysis.get('property_3_tour_date_time', ' '), 'onsite_manager': onsite_manager, 'property_email': email}
                    print(payload,'3')
                if payload:
                    requests.post("https://hook.us2.make.com/8gjcudr6nj0jshdwu71stsv1i1t7xif2",json=payload,
                    headers={
                        "x-make-apikey":os.environ['MAKE_KATPRO_API_KEY']
                    }) #(//*[@role="listitem"])[{{variables@loop_index}}]//*[contains(@aria-label,"to connect")]
                    

        return "Call summary saved to GHL"

@app.route("/properties_call", methods=["POST"])
def properties_call():
    try:
        raw_body = request.get_data(as_text=True)
        file_path = save_request_to_json("properties_call", raw_body)
        with open(file_path, "r") as file:
            data = json.load(file)
            if data['event']!='call_analyzed':
                return {"status": "Not yet analysed"}

            if data['call']['agent_id']!='agent_700adcae7acb749c710666834c':
                return {"status":"not correct agent"}
            api = Api(os.environ['AIRTABLE_API_KEY'])
            # table = api.table('appA6XNikBFdFgRtF', 'tbltWwPTaTTu5B3Yt')
            client_name = data['call']['retell_llm_dynamic_variables']['client_name']
            table = api.table('appA6XNikBFdFgRtF', client_name)
            
            lst = []
            for records in table.iterate(page_size=100, max_records=1000):
                lst += records 
                imp_deets = data['call']['call_analysis']['custom_analysis_data']
                client_deets = data['call']['retell_llm_dynamic_variables']
                call_successful = data['call']['call_analysis']['call_successful']
                # if data['call']['call_status']=='ended':
                #     call_successful = 'True'
                for i in lst:
                    if i['fields']['Contact Number']==data["call"]["to_number"]:
                        id = i['id']
                        table.update(id, fields={
                    "Locator Commission": imp_deets.get("locator_commision"),
                    "Monthly Fees": imp_deets.get("monthly_fees"),
                    "Bedrooms Requested": client_deets.get("no_of_bedrooms"),
                    "Bathrooms Requested": client_deets.get("no_of_bathrooms"),
                    "Client Tour Preferred Slot": f"Tomorrow {client_deets.get('tour_time')}", #"Client Tour Preferred Slot": f"{client_deets.get('tour_time')}",
                    "Unit1 Floor Level": imp_deets.get("unit1_floor_level"),
                    "Unit2 Bedrooms": imp_deets.get("unit2_bedrooms"),
                    "Tour Agent": imp_deets.get("tour_agent"),
                    "Specials": imp_deets.get("specials"),
                    "Unit2 Availability Date": imp_deets.get("unit2_availability_date"),
                    "Leasing Staff Contacted": imp_deets.get("leasing_staff_contacted"),
                    "Unit1 Lease Term (Months)": imp_deets.get("unit1_lease_term_months"),
                    "Unit2 Square Footage": imp_deets.get("unit2_square_footage"),
                    "Unit2 Bathrooms": imp_deets.get("unit2_bathrooms"),
                    "Unit1 Floor Plan Name": imp_deets.get("unit1_floor_plan_name"),
                    "Move-in Date": imp_deets.get("move_in_date"),
                    "Unit1 Availability Date": imp_deets.get("unit1_availability_date"),
                    "Unit2 Lease Term (Months)": imp_deets.get("unit2_lease_term_months"),
                    "Unit1 Market Rent": imp_deets.get("unit1_market_rent"),
                    "Client Name": client_deets.get("client_name"),
                    "Budget": float(client_deets.get("budget")),
                    "Unit1 Square Footage": imp_deets.get("unit1_square_footage"),
                    "Unit2 Market Rent": imp_deets.get("unit2_market_rent"),
                    "Unit2 Number": imp_deets.get("unit2_number"),
                    "Admin Fees": imp_deets.get("admin_fees"),
                    "Deposit Amount": imp_deets.get("deposit_amount"),
                    "Unit1 Number": imp_deets.get("unit1_number"),
                    "Unit2 Floor Plan Name": imp_deets.get("unit2_floor_plan_name"),
                    "Manager Available": str(imp_deets.get("manager_available",'False')),
                    "Deposit Refundable": imp_deets.get("deposit_refundable"),
                    "Unit1 Bedrooms": imp_deets.get("unit1_bedrooms"),
                    "Property Confirmed Tour Date and Time": imp_deets.get("property_confirmed_tour_datetime"),
                    "Email Confirmed": imp_deets.get("email_confirmed"),
                    "Unit2 Rent Amount": imp_deets.get("unit2_rent_amount"),
                    "Unit1 Bathrooms": imp_deets.get("unit1_bathrooms"),
                    "Unit1 Rent Amount": imp_deets.get("unit1_rent_amount"),
                    "Apartment Match": str(imp_deets.get("success",'False')),
                    "Income Requirement": imp_deets.get("income_requirement"),
                    "Application Fee": imp_deets.get("application_fee"),
                    "Unit2 Floor Level": imp_deets.get("unit2_floor_level"),
                    "AI Call Status": str(call_successful)

                })
            time.sleep(5)
            status = table.all(fields=['AI Call Status'])
            ct = 0
            for i in status:
                if i['fields'].get('AI Call Status','False') == 'True':
                    ct += 1
            if ct == len(status) and check_time_within_range():
                print(ct, 'Sending message to client')
                requests.post("https://services.leadconnectorhq.com/hooks/QRof2UTEmQswZAiO7A6Q/webhook-trigger/536a8543-3d74-4d8d-9a98-b6e7f5e8e70b",
                            json={
                                "name": client_name
                            })

            requests.post("https://hook.us2.make.com/h4q7o9xmhjhu4jmzc453ge9mudfzty58",json={
            "name":client_name},
            headers={
                "x-make-apikey":os.environ['MAKE_KATPRO_API_KEY']
            })
        return {"status": f"saved to airtable"}
    except:
        pwrite(f"Error processing the call data \n \n {traceback.format_exc()}")
        return {"status": "error processing the call data"}

@app.route("/email2airtable", methods=["POST"])
def email2airtable():
    raw_body = request.get_data(as_text=True)
    file_path = save_request_to_json("email2airtable", raw_body)
    return {"status": f"saved to {file_path}"}

if __name__ == "__main__":
    app.run(port=5000)

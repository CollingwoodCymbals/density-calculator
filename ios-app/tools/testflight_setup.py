"""Sets up an external TestFlight public link for the newest build and sends it to Beta App Review.
Runs in GitHub Actions with the App Store Connect API key. Contact details are copied from the
app's existing App Review details, so none are stored here. Writes a short status file."""
import os, time, jwt, requests

KEY_ID, ISSUER, APP_ID = os.environ["KEY_ID"], os.environ["ISSUER"], "6837221259"
P8 = os.environ["KEY_P8"]
BASE = "https://api.appstoreconnect.apple.com/v1"
log = []

def tok():
    now = int(time.time())
    return jwt.encode({"iss": ISSUER, "iat": now, "exp": now + 1100, "aud": "appstoreconnect-v1"},
                      P8, algorithm="ES256", headers={"kid": KEY_ID, "typ": "JWT"})

def call(method, path, body=None, params=None, ok=(200, 201, 204)):
    r = requests.request(method, BASE + path, json=body, params=params,
                         headers={"Authorization": "Bearer " + tok()})
    if r.status_code not in ok:
        log.append(f"{method} {path.split('/')[1]} -> {r.status_code}: {r.json().get('errors', [{}])[0].get('detail', '')[:300] if r.text else ''}")
        return None
    return r.json() if r.text else {}

def note(s):
    print(s); log.append(s)

# Contact from the App Store version's review details
v = call("GET", f"/apps/{APP_ID}/appStoreVersions", params={"limit": 1})
rd = call("GET", f"/appStoreVersions/{v['data'][0]['id']}/appStoreReviewDetail")
c = rd["data"]["attributes"]
email = c["contactEmail"]

desc = ("Free calculator for cymbal makers and drummers. Enter a cymbal's diameter and weight to get its density, "
        "then see what any other size should weigh to match. Save favourites. Works offline, no account.")
attrs = {"feedbackEmail": email, "description": desc,
         "marketingUrl": "https://collingwoodcymbals.github.io/density-calculator/",
         "privacyPolicyUrl": "https://collingwoodcymbals.github.io/density-calculator/privacy.html"}
locs = call("GET", f"/apps/{APP_ID}/betaAppLocalizations") or {"data": []}
if locs["data"]:
    for l in locs["data"]:
        call("PATCH", f"/betaAppLocalizations/{l['id']}", {"data": {"type": "betaAppLocalizations", "id": l["id"], "attributes": attrs}})
else:
    call("POST", "/betaAppLocalizations", {"data": {"type": "betaAppLocalizations", "attributes": {**attrs, "locale": "en-GB"},
         "relationships": {"app": {"data": {"type": "apps", "id": APP_ID}}}}})
note("Beta app info set")

d = call("GET", f"/apps/{APP_ID}/betaAppReviewDetail")
if d:
    rid = d["data"]["id"]
    call("PATCH", f"/betaAppReviewDetails/{rid}", {"data": {"type": "betaAppReviewDetails", "id": rid, "attributes": {
        "contactFirstName": c["contactFirstName"], "contactLastName": c["contactLastName"],
        "contactPhone": c["contactPhone"], "contactEmail": email, "demoAccountRequired": False,
        "notes": "No account or login. Open the app, enter a diameter and weight, see density and matching weights."}}})
    note("Beta review contact set")

b = call("GET", "/builds", params={"filter[app]": APP_ID, "sort": "-uploadedDate", "limit": 1})
build = b["data"][0]; bid = build["id"]
note(f"Build {build['attributes']['version']} state {build['attributes'].get('processingState')}")
if build["attributes"].get("usesNonExemptEncryption") is None:
    call("PATCH", f"/builds/{bid}", {"data": {"type": "builds", "id": bid, "attributes": {"usesNonExemptEncryption": False}}})
wn = "Please try the calculator, save a favourite and open the Guide."
bl = call("GET", f"/builds/{bid}/betaBuildLocalizations") or {"data": []}
if bl["data"]:
    for l in bl["data"]:
        call("PATCH", f"/betaBuildLocalizations/{l['id']}", {"data": {"type": "betaBuildLocalizations", "id": l["id"], "attributes": {"whatsNew": wn}}})
else:
    call("POST", "/betaBuildLocalizations", {"data": {"type": "betaBuildLocalizations", "attributes": {"locale": "en-GB", "whatsNew": wn},
         "relationships": {"build": {"data": {"type": "builds", "id": bid}}}}})

groups = call("GET", f"/apps/{APP_ID}/betaGroups") or {"data": []}
g = next((x for x in groups["data"] if x["attributes"]["name"] == "Public link"), None)
if not g:
    r = call("POST", "/betaGroups", {"data": {"type": "betaGroups", "attributes": {
        "name": "Public link", "publicLinkEnabled": True, "publicLinkLimitEnabled": True, "publicLinkLimit": 20},
        "relationships": {"app": {"data": {"type": "apps", "id": APP_ID}}}}})
    g = r["data"] if r else None
if g:
    call("POST", f"/betaGroups/{g['id']}/relationships/builds", {"data": [{"type": "builds", "id": bid}]})
    note("Build added to group 'Public link'")

call("POST", "/betaAppReviewSubmissions", {"data": {"type": "betaAppReviewSubmissions",
     "relationships": {"build": {"data": {"type": "builds", "id": bid}}}}}, ok=(200, 201, 409))
st = call("GET", f"/builds/{bid}/betaAppReviewSubmission")
if st and st.get("data"):
    note("Beta review state: " + str(st["data"]["attributes"].get("betaReviewState")))
if g:
    g2 = call("GET", f"/betaGroups/{g['id']}")
    note("PUBLIC LINK: " + str(g2["data"]["attributes"].get("publicLink")) if g2 else "no link yet")

open("ios-app/testflight-status.txt", "w").write(time.strftime("%Y-%m-%d %H:%M UTC\n") + "\n".join(log) + "\n")

import os
import json
import requests
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from groq import Groq


# ================= CONFIG =================
GOOGLE_SHEET_ID = os.getenv("GOOGLE_SHEET_ID")
SHEET_NAME = "Sheet1"

LINKEDIN_ACCESS_TOKEN = os.getenv("LINKEDIN_ACCESS_TOKEN")
LINKEDIN_PERSON_URN = os.getenv("LINKEDIN_PERSON_URN")

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
groq_client = Groq(api_key=GROQ_API_KEY)
# =========================================


sheet = None


# ========== GOOGLE SHEETS AUTH ==========
def verify_google_sheet():
    global sheet

    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive",
    ]

    if os.path.exists("google_credentials.json"):
        creds = ServiceAccountCredentials.from_json_keyfile_name(
            "google_credentials.json", scope
        )
    else:
        creds_dict = json.loads(os.environ["GOOGLE_CREDS_JSON"])
        creds = ServiceAccountCredentials.from_json_keyfile_dict(
            creds_dict, scope
        )

    client = gspread.authorize(creds)
    sheet = client.open_by_key(GOOGLE_SHEET_ID).worksheet(SHEET_NAME)

    sheet.get_all_records()


# ========== DATA ==========
def get_pending_row():
    rows = sheet.get_all_records()
    for i, row in enumerate(rows, start=2):
        if row.get("Status") == "Pending":
            return i, row
    return None, None


# ========== GROQ ==========
def generate_post(prompt: str) -> str:
    system_prompt = """
You are a software developer and digital tech professional writing LinkedIn posts for early-career developers and IT professionals.

Write a LinkedIn post (180–240 words) that:
• starts with a strong one-line hook
• explains a real-world dev or SaaS concept simply
• includes 3 takeaways using emoji bullets (⭐ or 🔹)
• add code examples if required
• ends with a question inviting comments

Tone: conversational, clear, slightly witty.
Avoid buzzwords. Focus on practical thinking.
"""

    response = groq_client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ],
        temperature=0.7,
        max_tokens=400,
    )

    return response.choices[0].message.content.strip()


# ========== LINKEDIN ==========
def post_to_linkedin(text: str):
    headers = {
        "Authorization": f"Bearer {LINKEDIN_ACCESS_TOKEN}",
        "Content-Type": "application/json",
        "LinkedIn-Version": "202401",
        "X-Restli-Protocol-Version": "2.0.0",
    }

    payload = {
        "author": LINKEDIN_PERSON_URN,
        "lifecycleState": "PUBLISHED",
        "specificContent": {
            "com.linkedin.ugc.ShareContent": {
                "shareCommentary": {"text": text},
                "shareMediaCategory": "NONE",
            }
        },
        "visibility": {
            "com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"
        },
    }

    r = requests.post(
        "https://api.linkedin.com/v2/ugcPosts",
        headers=headers,
        json=payload,
    )
    r.raise_for_status()


# ========== MAIN JOB ==========
def main():
    verify_google_sheet()

    row_number, row = get_pending_row()
    if not row:
        return

    post_text = generate_post(row["AI Prompt"])

    post_to_linkedin(post_text)
    sheet.update(f"C{row_number}", [["Posted"]])
    print("✅ Posted and sheet updated")


if __name__ == "__main__":
    main()

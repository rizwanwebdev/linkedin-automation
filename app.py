import os
import json
import requests
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from groq import Groq
from markdown import markdown
import re
from bs4 import BeautifulSoup

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

Write a LinkedIn post (180–240 words) with the following rules:

STRUCTURE
- Start immediately with the hook. Do NOT add any introductions or labels.
- Use short, readable paragraphs with a blank line between ideas.
- Include exactly 3 takeaway bullets using ⭐ or 🔹.
- End with a single question to invite comments.

STYLE
- Conversational, clear, slightly witty.
- Practical and experience-driven.
- Avoid buzzwords and marketing language.

STRICT OUTPUT RULES
- Output ONLY the post text.
- Do NOT say “Here’s a LinkedIn post”, “Below is”, or similar.
- Do NOT explain what you are doing.
- Do NOT add headings, titles, or summaries.
- Do NOT wrap the output in quotes or markdown fences.

The output must be ready to paste directly into LinkedIn without any cleanup.

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
# ========== MARKDOWN TO PLAIN TEXT ==========
def markdown_to_text(md: str) -> str:
    # Convert Markdown → HTML
    html = markdown(md)

    # Parse HTML
    soup = BeautifulSoup(html, "html.parser")

    # Convert block elements into spaced text
    text = soup.get_text(separator="\n\n")

    # Normalize spacing:
    # - Max 2 newlines
    # - Trim leading/trailing space
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text.strip()

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
    post_text = markdown_to_text(post_text) 
    post_to_linkedin(post_text)
    sheet.update(f"C{row_number}", [["Posted"]])


if __name__ == "__main__":
    main()

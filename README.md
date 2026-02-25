⚡ AMPify — SFMC SQL Generator

AI-powered SQL generator built exclusively for Salesforce Marketing Cloud developers.
Describe what you need in plain English. Get production-ready SFMC SQL instantly.

What is AMPify?
AMPify solves a real daily pain point for SFMC developers — writing SQL queries that comply with Salesforce Marketing Cloud's strict and non-standard rules is tedious and error-prone.
You describe what you want. AMPify generates two versions:
VersionPurpose🧪 Query StudioTest version — max 100 rows, preview only, safe to validate logic🚀 Automation StudioProduction version — full dataset, ready to schedule

Why AMPify?
SFMC SQL is not standard SQL. It has rules no other tool enforces:

No SELECT * — columns must be named explicitly
No LIMIT — use TOP N
No NOW() — use GETDATE()
No temp tables, stored procedures, or DDL
Data views must be joined on all 4 keys: JobID + ListID + BatchID + SubscriberID
IsUnique = 1 belongs in the JOIN condition, not in WHERE
_Job is BU-specific — has no subscriber data
Data views hold only last 6 months of tracking data

ChatGPT and other general AI tools don't know these rules. AMPify does — they're baked into the AI knowledge base.

Features

Plain English → SFMC SQL — no need to remember syntax
Dual output — Query Studio (test) + Automation Studio (production)
12+ data views covered — _Sent, _Open, _Click, _Bounce, _Unsubscribe, _Complaint, _Job, _Subscribers, ENT._EnterpriseAttribute, _JourneyActivity, and more
Correct join patterns — 4-key joins enforced automatically
Optional DE names — provide your own or get intelligent placeholders
Download .sql files — one click download for both versions
Built-in reference — SFMC rules, functions, and data view cheatsheet always visible
Domain-confined — rejects non-SFMC questions


Demo Queries to Try
- Active subscribers who opened in last 30 days but never clicked
- Contacts with renewal date in next 7 days, not contacted this month
- Unique bouncers from last 90 days — build suppression list
- Subscribers who received 5+ emails this month — fatigue check
- Full tracking report: sent, opens, clicks, bounces, unsubs for last month
- Last campaign clickers NOT in the purchased DE

Tech Stack
LayerTechnologyFrontendStreamlitAI ModelLLaMA 3.3 70B via Groq APILanguagePython 3.10+DeploymentStreamlit Community Cloud

Local Setup
1. Clone the repo
bashgit clone https://github.com/NC-Sudhansu/ampify-sfmc-sql-generator.git
cd ampify-sfmc-sql-generator
2. Create virtual environment
bashpython -m venv venv
source venv/bin/activate        # Mac/Linux
venv\Scripts\activate           # Windows
3. Install dependencies
bashpip install -r requirements.txt
4. Add your Groq API key
Create a .env file in the root:
GROQ_API_KEY=your_groq_api_key_here
Get a free API key at console.groq.com
5. Run the app
bashstreamlit run app.py
Open http://localhost:8501 in your browser.

Project Structure
ampify-sfmc-sql-generator/
├── app.py              # Main Streamlit application
├── requirements.txt    # Python dependencies
├── .env                # Your API key (never committed)
├── .gitignore          # Ignores .env and other sensitive files
└── README.md           # This file

Deploying to Streamlit Cloud

Push this repo to GitHub
Go to share.streamlit.io
Connect your GitHub repo
Add GROQ_API_KEY in Settings → Secrets:

tomlGROQ_API_KEY = "your_groq_api_key_here"

Deploy — your app will be live at your-app.streamlit.app


SFMC Data Views Reference
Data ViewKey Fields_SentSubscriberKey, JobID, EventDate, ListID, BatchID_OpenSubscriberKey, JobID, EventDate, IsUnique, Domain_ClickSubscriberKey, JobID, EventDate, URL, LinkName, IsUnique_BounceSubscriberKey, JobID, EventDate, BounceCategory, SMTPBounceReason_UnsubscribeSubscriberKey, JobID, EventDate, IsUnique_ComplaintSubscriberKey, JobID, EventDate_JobJobID, EmailName, EmailSubject, FromName, DeliveredTime_SubscribersSubscriberKey, EmailAddress, Status, DateCreatedENT._EnterpriseAttribute_SubscriberID + profile attributes_JourneyActivitySubscriberKey, ActivityName, ActivityType, EventDate

Author
Nallan Chakravarthula Sudhansu Sri Sai
Salesforce Marketing Cloud Developer → AI Engineer

Disclaimer
AMPify is an independent open-source project and is not affiliated with, endorsed by, or connected to Salesforce Inc. in any way. Salesforce and Marketing Cloud are trademarks of Salesforce Inc.

Always validate generated queries in Query Studio before scheduling in Automation Studio.
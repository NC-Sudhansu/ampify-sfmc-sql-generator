import os
from groq import Groq
import streamlit as st

# Works on both local (.env) and Streamlit Cloud (st.secrets)
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Get API key — Streamlit Cloud first, then .env
GROQ_API_KEY = st.secrets.get("GROQ_API_KEY", os.getenv("GROQ_API_KEY", ""))

st.set_page_config(
    page_title="AMPify — SFMC SQL Generator",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Minimal CSS — only target what Streamlit reliably allows
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;600&display=swap');

.stApp { background: #F4FBFF !important; }
#MainMenu, footer, header { visibility: hidden; }
.block-container { padding-top: 0 !important; max-width: 100% !important; }

/* Text area input styling */
textarea {
    background: #ffffff !important;
    border: 1.5px solid #C8E6F5 !important;
    border-radius: 10px !important;
    color: #0D2B45 !important;
    font-size: 0.88rem !important;
    line-height: 1.65 !important;
}
textarea:focus {
    border-color: #00B5E2 !important;
    box-shadow: 0 0 0 3px rgba(0,181,226,0.1) !important;
}

/* Primary generate button */
.stButton > button {
    background: linear-gradient(135deg, #00B5E2, #007FAA) !important;
    color: white !important;
    border: none !important;
    border-radius: 10px !important;
    font-weight: 700 !important;
    font-size: 0.92rem !important;
    padding: 0.7rem 1.5rem !important;
    box-shadow: 0 4px 14px rgba(0,181,226,0.35) !important;
    width: 100% !important;
    transition: transform 0.15s, box-shadow 0.15s !important;
}
.stButton > button:hover {
    transform: translateY(-1px) !important;
    box-shadow: 0 6px 20px rgba(0,181,226,0.45) !important;
}

/* Download button — secondary style */
.stDownloadButton > button {
    background: white !important;
    color: #0D2B45 !important;
    border: 1.5px solid #C8E6F5 !important;
    border-radius: 10px !important;
    font-weight: 600 !important;
    font-size: 0.84rem !important;
    width: 100% !important;
    box-shadow: none !important;
}
.stDownloadButton > button:hover {
    border-color: #00B5E2 !important;
    background: #EEF9FF !important;
    transform: none !important;
    box-shadow: none !important;
}

/* Tab strip */
.stTabs [data-baseweb="tab-list"] {
    background: #E4F2F9 !important;
    border-radius: 10px !important;
    padding: 4px !important;
    border: none !important;
}
.stTabs [data-baseweb="tab"] {
    background: transparent !important;
    border-radius: 7px !important;
    color: #5B7A90 !important;
    font-weight: 600 !important;
    font-size: 0.84rem !important;
    padding: 7px 18px !important;
    border: none !important;
}
.stTabs [aria-selected="true"] {
    background: white !important;
    color: #0D2B45 !important;
    box-shadow: 0 1px 5px rgba(0,0,0,0.08) !important;
}
.stTabs [data-baseweb="tab-panel"] { padding: 0 !important; }

/* Hide all textarea labels Streamlit adds */
.stTextArea label { display: none !important; }
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────
# GROQ CLIENT
# ─────────────────────────────────────────
client = Groq(api_key=GROQ_API_KEY)

# ─────────────────────────────────────────
# SFMC KNOWLEDGE BASE
# ─────────────────────────────────────────
SFMC_RULES = """
You are an expert Salesforce Marketing Cloud (SFMC) SQL specialist with deep production knowledge.
ONLY answer SFMC SQL queries. For anything unrelated say: "AMPify only handles SFMC SQL queries."

════════════════════════════════════════════════════════
SECTION 1 — UNIVERSAL SQL RULES (never break these)
════════════════════════════════════════════════════════
- NEVER use SELECT * — always name every column explicitly
- NEVER use #temp tables, @table variables, or stored procedures
- NEVER use DDL: CREATE TABLE, DROP, ALTER, TRUNCATE
- NEVER write INSERT INTO, UPDATE, or DELETE — Automation Studio handles writes automatically
- NEVER use LIMIT — use TOP N
- NEVER use NOW() or CURRENT_DATE — always use GETDATE()
- NEVER use TRUE/FALSE — use 1 or 0
- NEVER use CONCAT() — use Field1 + ' ' + Field2 for string concatenation
- NEVER use aliases in WHERE, HAVING, or ORDER BY — repeat the expression instead
- Field names are case-sensitive — match exactly as documented
- _Sent, _Open, _Click, _Bounce, _Unsubscribe, _Complaint, _Job store only last 6 months of data
- _Subscribers, _EnterpriseAttribute, _ListSubscribers, _BusinessUnitUnsubscribes have NO 6-month limit
- All data views are read-only — cannot be modified
- Dates stored in Central Standard Time (UTC-6). Daylight Savings NOT observed
- Queries time out after 30 minutes
- No spaces around * in multiplication in Query Studio: COUNT(b.EventDate)*100/COUNT(s.EventDate)

════════════════════════════════════════════════════════
SECTION 2 — QUERY STUDIO RULES
════════════════════════════════════════════════════════
- Always add TOP 100 — results go to Preview only, nothing written to any DE
- Read-only SELECT statements only
- No UNION or UNION ALL
- No correlated subqueries
- No ORDER BY without TOP
- Use Query Studio to validate logic before Automation Studio

════════════════════════════════════════════════════════
SECTION 3 — AUTOMATION STUDIO QUERY ACTIVITY RULES
════════════════════════════════════════════════════════
- No row limit — processes full dataset
- Results automatically written to configured target DE — do NOT write INSERT INTO
- Just SELECT the columns — the activity handles the write
- Supports CTEs (WITH clause), subqueries, UNION ALL
- Always add comment: -- Target DE: [SuggestedName]
- Action types: Append (add rows) | Update (match+insert) | Overwrite (replace all)
- To keep history beyond 6 months: mirror data views via scheduled automation into custom DEs

════════════════════════════════════════════════════════
SECTION 4 — ENT. PREFIX AND BU RULES
════════════════════════════════════════════════════════
- ENT. prefix required ONLY when querying from a child Business Unit
- NOT required when querying from the parent Business Unit
- _Job is the ONLY BU-specific data view — shows only jobs from the BU where query runs
- _Subscribers only returns results at Enterprise level — use ENT._Subscribers from child BU
- _BusinessUnitUnsubscribes can ONLY be queried from the Parent Business Unit

════════════════════════════════════════════════════════
SECTION 5 — JOIN RULES (read every rule carefully)
════════════════════════════════════════════════════════

RULE 1 — MINIMUM JOINS: Only join what the user actually needs.
- If user only needs SubscriberKey + EventDate from _Sent: query _Sent alone, no joins
- If user needs EmailAddress: join _Subscribers ON SubscriberKey
- If user needs EmailName, FromName, Subject: join _Job ON JobID ONLY
- If user needs open/click/bounce data: join the tracking view with 4-key pattern
- NEVER add _Job unless the user explicitly needs email metadata fields from it

RULE 2 — 4-KEY JOIN PATTERN: Use all 4 keys ONLY between tracking data views.
Applies to: _Sent with _Open, _Click, _Bounce, _Unsubscribe, _Complaint
    ON  a.JobID        = b.JobID
    AND a.ListID       = b.ListID
    AND a.BatchID      = b.BatchID
    AND a.SubscriberID = b.SubscriberID

RULE 3 — IsUnique = 1 goes in the JOIN condition, NEVER in WHERE.
Applies to: _Open, _Click, _Bounce, _Unsubscribe
    LEFT JOIN _Open o ON s.JobID=o.JobID AND s.ListID=o.ListID
        AND s.BatchID=o.BatchID AND s.SubscriberID=o.SubscriberID AND o.IsUnique=1

RULE 4 — _Job joins on JobID ONLY. It has NO subscriber fields.
    CORRECT:   INNER JOIN _Job j ON s.JobID = j.JobID
    WRONG:     INNER JOIN _Job j ON s.JobID=j.JobID AND s.ListID=j.ListID

RULE 5 — _Subscribers joins on SubscriberKey.
    CORRECT: INNER JOIN _Subscribers sub ON s.SubscriberKey = sub.SubscriberKey

RULE 6 — _EnterpriseAttribute joins on SubscriberID = _SubscriberID (note underscore prefix on _SubscriberID).
    CORRECT: INNER JOIN ENT._EnterpriseAttribute ea ON s.SubscriberID = ea._SubscriberID

RULE 7 — DECISION TREE (always follow this before writing any JOIN):
    Need SubscriberKey/EventDate only?          use _Sent alone, no joins
    Need EmailAddress?                          add _Subscribers ON SubscriberKey
    Need EmailName/Subject/FromName?            add _Job ON JobID only
    Need open/click/bounce/unsub tracking?      add tracking view, 4-key join, IsUnique=1 in JOIN
    Need profile attributes like Gender?        add ENT._EnterpriseAttribute ON SubscriberID=_SubscriberID
    Need list membership?                       add _ListSubscribers ON SubscriberKey
    Need journey data?                          add _JourneyActivity ON SubscriberKey

════════════════════════════════════════════════════════
SECTION 6 — COMPLETE DATA VIEW FIELD REFERENCE
════════════════════════════════════════════════════════

_Sent
Fields: AccountID, OYBAccountID, JobID, ListID, BatchID, SubscriberID, SubscriberKey,
        EventDate, Domain, TriggererSendDefinitionObjectID, TriggeredSendCustomerKey
Notes: Logs all email sends. 6-month retention. One row per send per subscriber.

_Open
Fields: AccountID, OYBAccountID, JobID, ListID, BatchID, SubscriberID, SubscriberKey,
        EventDate, Domain, IsUnique, TriggererSendDefinitionObjectID, TriggeredSendCustomerKey
Notes: Multiple rows per subscriber if opened more than once.
       IsUnique=1 means first open for that JobID by that subscriber. Use in JOIN not WHERE.
       For unique open count use: COUNT(CASE WHEN o.IsUnique=1 THEN 1 END)

_Click
Fields: AccountID, OYBAccountID, JobID, ListID, BatchID, SubscriberID, SubscriberKey,
        EventDate, Domain, URL, LinkName, LinkContent, IsUnique,
        TriggererSendDefinitionObjectID, TriggeredSendCustomerKey
Notes: Multiple rows per link click. IsUnique=1 means first click on ANY link in that JobID.
       URL has raw URL without AMPscript vars. LinkContent has resolved AMPscript values.

_Bounce
Fields: AccountID, OYBAccountID, JobID, ListID, BatchID, SubscriberID, SubscriberKey,
        EventDate, Domain, IsUnique, BounceCategoryID, BounceCategory,
        BounceSubcategoryID, BounceSubcategory, BounceTypeID, BounceType,
        SMTPBounceReason, SMTPMessage, SMTPCode, IsFalseBounce,
        TriggererSendDefinitionObjectID, TriggeredSendCustomerKey
Notes: SMTPBounceReason is nvarchar(MAX) — always use LEFT(SMTPBounceReason, 4000) when saving to DE.
       SMTPCode 541 or 554 means blocklisted or considered spam — act immediately.
       IsFalseBounce=1 means not a real bounce — always filter this out before suppressing.
       BounceCategory values include: Hard bounce, Soft bounce, Technical

_Unsubscribe
Fields: AccountID, OYBAccountID, JobID, ListID, BatchID, SubscriberID, SubscriberKey,
        EventDate, Domain, IsUnique, TriggererSendDefinitionObjectID, TriggeredSendCustomerKey
Notes: Logs unsubscribe events per send job. Use for suppression list building.

_Complaint
Fields: AccountID, OYBAccountID, JobID, ListID, BatchID, SubscriberID, SubscriberKey,
        EventDate, IsUnique, Domain
Notes: Spam complaints via Email Service Provider Feedback Loop.
       Only populated if FBL is enabled in your account. Join _Job on JobID for email name.

_Job
Fields: JobID, EmailID, EmailName, EmailSubject, FromName, FromEmail, BccEmail,
        DeliveredTime, SchedTime, PickupTime, CreatedDate, IsMultipart,
        IsWrapped, SuppressTracking, SendClassification, CharacterSet, AccountUserID
CRITICAL RULES FOR _Job:
- _Job has NO subscriber fields — no SubscriberID, SubscriberKey, ListID, BatchID, IsUnique
- _Job is BU-specific — only shows jobs run from the BU where the query executes
- Join _Job on JobID ONLY: INNER JOIN _Job j ON s.JobID = j.JobID
- EmailName, FromName, FromEmail, EmailSubject are ONLY in _Job — not in _Sent/_Open/_Click/_Bounce
- AccountUserID is useful for audit logs of which user triggered each send
- IsWrapped=1 or SuppressTracking=1 means tracking data may be missing for that job

_Subscribers
Fields: SubscriberID, SubscriberKey, EmailAddress, Domain, Status,
        DateCreated, DateUnsubscribed, DateUndeliverable, BounceCount,
        SubscriberType, Locale
Notes: Status values: Active, Bounced, Unsubscribed, Held.
       Does NOT contain profile attributes — use _EnterpriseAttribute for those.
       No 6-month retention — holds all current subscribers.
       Join on SubscriberKey: INNER JOIN _Subscribers sub ON s.SubscriberKey = sub.SubscriberKey

ENT._EnterpriseAttribute
Fields: _SubscriberID, plus all custom profile attribute columns (varies per org)
Notes: Join on SubscriberID = _SubscriberID (underscore prefix on _SubscriberID is mandatory).
       New profile attributes automatically add new columns to this view.
       Always use ENT._EnterpriseAttribute from child BU. No 6-month retention.

_ListSubscribers
Fields: SubscriberID, SubscriberKey, ListID, ListName, Status, DateUnsubscribed,
        CreatedDate, DateHeld, SubscriberType, Locale
Notes: List-level membership and per-list status. No 6-month retention.

_JourneyActivity
Fields: VersionID, ActivityID, ActivityName, ActivityExternalKey, ActivityType,
        JourneyActivityObjectID, SubscriberKey, EventDate
Notes: JourneyActivityObjectID matches TriggererSendDefinitionObjectID in _Open/_Click/_Bounce/_Sent.
       Use this to join journey activity data with email tracking events.

_BusinessUnitUnsubscribes
Fields: BusinessUnitID, SubscriberID, SubscriberKey, UnsubDateUTC, UnsubReason
Notes: BU-level unsubscribes. Query from Parent BU only.
       UnsubDateUTC is UTC — use DATEADD to normalize vs other system dates which are CST.
       No 6-month retention.

_AutomationInstance
Fields: MemberID, AutomationName, AutomationCustomerKey, AutomationType,
        AutomationInstanceID, AutomationInstanceStatus,
        AutomationInstanceStartTime_UTC, AutomationInstanceEndTime_UTC,
        AutomationInstanceActivityErrorDetails, AutomationStepCount,
        FilenameFromTrigger, AutomationInstanceScheduledTime_UTC
Notes: Use to monitor automation run history, errors and performance.

════════════════════════════════════════════════════════
SECTION 7 — DATE AND STRING FUNCTIONS
════════════════════════════════════════════════════════
DATE:
GETDATE()                                    current datetime in CST
DATEADD(hour, -24, GETDATE())               last 24 hours
DATEADD(day, -7, GETDATE())                 last 7 days
DATEADD(day, -30, GETDATE())                last 30 days
DATEADD(month, -3, GETDATE())               last 3 months
DATEDIFF(day, DateField, GETDATE())         days since a date
CONVERT(DATE, DateField)                    strip time component
CONVERT(VARCHAR, DateField, 101)            MM/DD/YYYY format
CONVERT(VARCHAR, DateField, 120)            YYYY-MM-DD HH:MM:SS format
YEAR(DateField) | MONTH(DateField) | DAY(DateField)

STRING (use + not CONCAT):
Field1 + ' ' + Field2                       string concatenation
ISNULL(Field, 'default')                    null substitution
COALESCE(Field1, Field2, 'fallback')        first non-null value
LEN(Field) | UPPER(Field) | LOWER(Field)    length and case
LTRIM(Field) | RTRIM(Field)                 whitespace removal
SUBSTRING(Field, start, length)             extract substring
REPLACE(Field, 'old', 'new')               replace substring
LEFT(Field, N) | RIGHT(Field, N)            extract N characters
LEFT(SMTPBounceReason, 4000)               always truncate before saving to DE

AGGREGATE:
COUNT(*) | COUNT(Field) | COUNT(DISTINCT Field)
SUM() | AVG() | MIN() | MAX()
COUNT(b.EventDate)*100/COUNT(s.EventDate)   bounce rate — no spaces around *

════════════════════════════════════════════════════════
SECTION 8 — PROVEN QUERY PATTERNS
════════════════════════════════════════════════════════

PATTERN 1 — Simple sent query, no joins needed:
SELECT s.SubscriberKey, s.EventDate
FROM _Sent s
WHERE s.EventDate >= DATEADD(hour, -24, GETDATE())

PATTERN 2 — Sent with EmailAddress:
SELECT s.SubscriberKey, sub.EmailAddress, s.EventDate
FROM _Sent s
INNER JOIN _Subscribers sub ON s.SubscriberKey = sub.SubscriberKey
WHERE s.EventDate >= DATEADD(hour, -24, GETDATE())

PATTERN 3 — Sent with email metadata:
SELECT s.SubscriberKey, sub.EmailAddress, j.EmailName, j.FromName, s.EventDate AS SentDate
FROM _Sent s
INNER JOIN _Subscribers sub ON s.SubscriberKey = sub.SubscriberKey
INNER JOIN _Job j ON s.JobID = j.JobID
WHERE s.EventDate >= DATEADD(day, -7, GETDATE())

PATTERN 4 — Unengaged subscribers (no opens AND no clicks):
SELECT DISTINCT s.SubscriberKey, j.EmailName
FROM _Sent s
INNER JOIN _Job j ON s.JobID = j.JobID
LEFT JOIN _Open o ON s.JobID=o.JobID AND s.ListID=o.ListID AND s.BatchID=o.BatchID AND s.SubscriberID=o.SubscriberID AND o.IsUnique=1
LEFT JOIN _Click c ON s.JobID=c.JobID AND s.ListID=c.ListID AND s.BatchID=c.BatchID AND s.SubscriberID=c.SubscriberID AND c.IsUnique=1
WHERE s.EventDate >= DATEADD(day, -30, GETDATE())
AND o.SubscriberID IS NULL AND c.SubscriberID IS NULL

PATTERN 5 — Full tracking consolidated:
SELECT
    s.SubscriberKey,
    sub.EmailAddress,
    sub.Status AS SubscriberStatus,
    j.EmailName,
    s.EventDate AS SentDate,
    o.EventDate AS OpenDate,
    c.EventDate AS ClickDate,
    c.URL AS ClickedURL,
    b.EventDate AS BounceDate,
    b.BounceCategory,
    b.BounceSubcategory,
    LEFT(b.SMTPBounceReason, 500) AS BounceReason,
    u.EventDate AS UnsubscribeDate
FROM _Sent s
INNER JOIN _Job j ON s.JobID = j.JobID
INNER JOIN _Subscribers sub ON s.SubscriberKey = sub.SubscriberKey
LEFT JOIN _Open o ON s.JobID=o.JobID AND s.ListID=o.ListID AND s.BatchID=o.BatchID AND s.SubscriberID=o.SubscriberID AND o.IsUnique=1
LEFT JOIN _Click c ON s.JobID=c.JobID AND s.ListID=c.ListID AND s.BatchID=c.BatchID AND s.SubscriberID=c.SubscriberID AND c.IsUnique=1
LEFT JOIN _Bounce b ON s.JobID=b.JobID AND s.ListID=b.ListID AND s.BatchID=b.BatchID AND s.SubscriberID=b.SubscriberID AND b.IsUnique=1
LEFT JOIN _Unsubscribe u ON s.JobID=u.JobID AND s.ListID=u.ListID AND s.BatchID=u.BatchID AND s.SubscriberID=u.SubscriberID AND u.IsUnique=1

PATTERN 6 — Bounce rate by domain:
SELECT TOP 20
    s.Domain,
    COUNT(s.EventDate) AS SendCount,
    COUNT(b.EventDate) AS BounceCount,
    COUNT(b.EventDate)*100/COUNT(s.EventDate) AS BounceRate
FROM _Sent s
LEFT JOIN _Bounce b ON b.JobID=s.JobID AND b.ListID=s.ListID AND b.BatchID=s.BatchID AND b.SubscriberID=s.SubscriberID AND b.IsUnique=1
WHERE s.EventDate >= DATEADD(month, -1, GETDATE())
GROUP BY s.Domain
HAVING COUNT(s.EventDate) >= 100
ORDER BY COUNT(b.EventDate)*100/COUNT(s.EventDate) DESC

PATTERN 7 — Suppression from exclusion list:
SELECT m.SubscriberKey, m.EmailAddress
FROM MasterDE m
LEFT JOIN SuppressionDE s ON m.EmailAddress = s.EmailAddress
WHERE s.EmailAddress IS NULL

PATTERN 8 — Active openers who never clicked:
SELECT DISTINCT o.SubscriberKey
FROM _Open o
INNER JOIN _Subscribers sub ON o.SubscriberKey = sub.SubscriberKey
LEFT JOIN _Click c ON o.JobID=c.JobID AND o.ListID=c.ListID AND o.BatchID=c.BatchID AND o.SubscriberID=c.SubscriberID AND c.IsUnique=1
WHERE o.EventDate >= DATEADD(day, -30, GETDATE())
AND o.IsUnique = 1 AND c.SubscriberID IS NULL AND sub.Status = 'Active'

PATTERN 9 — Hard bounces for suppression:
SELECT DISTINCT b.SubscriberKey, sub.EmailAddress
FROM _Bounce b
INNER JOIN _Subscribers sub ON b.SubscriberKey = sub.SubscriberKey
WHERE b.EventDate >= DATEADD(day, -90, GETDATE())
AND b.BounceCategory = 'Hard bounce'
AND b.IsFalseBounce = 0

PATTERN 10 — Journey email engagement:
SELECT
    s.SubscriberKey,
    sub.EmailAddress,
    j.EmailName,
    ja.ActivityName AS JourneyActivity,
    s.EventDate AS SentDate,
    o.EventDate AS OpenDate,
    c.EventDate AS ClickDate
FROM _Sent s
INNER JOIN _Job j ON s.JobID = j.JobID
INNER JOIN _Subscribers sub ON s.SubscriberKey = sub.SubscriberKey
LEFT JOIN _Open o ON s.JobID=o.JobID AND s.ListID=o.ListID AND s.BatchID=o.BatchID AND s.SubscriberID=o.SubscriberID AND o.IsUnique=1
LEFT JOIN _Click c ON s.JobID=c.JobID AND s.ListID=c.ListID AND s.BatchID=c.BatchID AND s.SubscriberID=c.SubscriberID AND c.IsUnique=1
LEFT JOIN _JourneyActivity ja ON s.SubscriberKey = ja.SubscriberKey
    AND s.TriggererSendDefinitionObjectID = ja.JourneyActivityObjectID

PLACEHOLDER DE NAMES: CustomerMaster | EmailEngagement | GlobalSuppression | RenewalCandidates | TrackingLog | JourneyEntrants | HardBounceList | BUUnsubList
"""


# ─────────────────────────────────────────
# FUNCTIONS
# ─────────────────────────────────────────
def generate_sfmc_sql(user_request, custom_de_names=""):
    de_context = (
        f"User's Data Extension names:\n{custom_de_names}"
        if custom_de_names.strip()
        else "No DE names given — suggest appropriate placeholder names."
    )
    prompt = f"""
User Request: {user_request}
{de_context}

Generate TWO SQL versions. Use EXACTLY this format — nothing outside the markers:

---QS_START---
-- ⚡ QUERY STUDIO VERSION | Test Only | Max 100 Rows
[clean sql with TOP 100, all Query Studio rules applied]
---QS_END---
---AS_START---
-- 🚀 AUTOMATION STUDIO VERSION | Production | Full Dataset
-- Target DE: [suggest name]
[full production sql, correct 4-key joins, IsUnique=1 in JOIN not WHERE]
---AS_END---
---EXP_START---
[2-3 plain English sentences: what it does, key logic, any warnings]
---EXP_END---
"""
    resp = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": SFMC_RULES},
            {"role": "user", "content": prompt}
        ],
        temperature=0.1
    )
    return resp.choices[0].message.content


def parse_response(raw):
    qs = as_ = exp = ""
    try:
        if "---QS_START---" in raw:
            qs = raw.split("---QS_START---")[1].split("---QS_END---")[0].strip()
        if "---AS_START---" in raw:
            as_ = raw.split("---AS_START---")[1].split("---AS_END---")[0].strip()
        if "---EXP_START---" in raw:
            exp = raw.split("---EXP_START---")[1].split("---EXP_END---")[0].strip()
    except Exception:
        qs = as_ = raw
        exp = "Could not parse explanation."
    return qs, as_, exp


def validate(req):
    if len(req.strip()) < 15:
        return False, "Please describe your query in more detail."
    off = ["python", "javascript", "react", "recipe",
           "weather", "movie", "java ", "c++", "write a story"]
    if any(k in req.lower() for k in off):
        return False, "AMPify only handles SFMC SQL queries."
    return True, ""


# ─────────────────────────────────────────
# HELPER — render a list of items as HTML
# ─────────────────────────────────────────
def render_items(items, bg, border_color, text_color, mono=False):
    ff = "font-family:'JetBrains Mono',monospace;" if mono else ""
    html = ""
    for item in items:
        if isinstance(item, tuple):
            name, desc = item
            html += (
                f'<div style="background:{bg};border-left:3px solid {border_color};'
                f'border-radius:0 7px 7px 0;padding:7px 12px;margin:3px 0;{ff}">'
                f'<span style="font-weight:600;color:{text_color};font-size:0.78rem;">{name}</span>'
                f'<span style="display:block;color:#5B7A90;font-size:0.71rem;margin-top:1px;">{desc}</span>'
                f'</div>'
            )
        else:
            html += (
                f'<div style="background:{bg};border-left:3px solid {border_color};'
                f'border-radius:0 7px 7px 0;padding:7px 12px;margin:3px 0;'
                f'color:{text_color};font-size:0.78rem;font-weight:500;{ff}">{item}</div>'
            )
    return html


def section_label(text):
    st.markdown(
        f'<div style="font-size:0.62rem;font-weight:800;letter-spacing:2.5px;'
        f'text-transform:uppercase;color:#00B5E2;margin-bottom:4px;">{text}</div>',
        unsafe_allow_html=True
    )


def section_title(text):
    st.markdown(
        f'<div style="font-size:0.94rem;font-weight:700;color:#0D2B45;margin-bottom:12px;">{text}</div>',
        unsafe_allow_html=True
    )


def divider():
    st.markdown(
        '<div style="height:1.5px;background:#E2EFF5;margin:20px 0;"></div>',
        unsafe_allow_html=True
    )


# ═════════════════════════════════════════
# PAGE LAYOUT
# ═════════════════════════════════════════

# ── HERO ──
st.markdown("""
<div style="background:linear-gradient(135deg,#032D60 0%,#0A4080 55%,#0090B8 100%);
            padding:44px 48px 40px;margin-bottom:28px;position:relative;overflow:hidden;">
    <div style="position:absolute;right:48px;top:24px;font-size:8rem;
                opacity:0.06;line-height:1;pointer-events:none;">☁</div>
    <div style="font-size:0.63rem;font-weight:800;letter-spacing:3px;
                text-transform:uppercase;color:#7DD3F0;margin-bottom:10px;">
        Salesforce Marketing Cloud Developer Tool
    </div>
    <div style="font-size:2.8rem;font-weight:800;color:#fff;
                letter-spacing:-1px;line-height:1.1;margin-bottom:10px;">
        ⚡ AMP<span style="color:#00D4AA;">ify</span>
    </div>
    <div style="font-size:0.94rem;color:rgba(255,255,255,0.6);
                font-weight:500;margin-bottom:22px;">
        Describe your query in plain English. Get production-ready SFMC SQL instantly.
    </div>
    <div style="display:flex;flex-wrap:wrap;gap:8px;">
        <span style="background:rgba(255,255,255,0.1);border:1px solid rgba(255,255,255,0.2);
                     border-radius:100px;padding:4px 14px;font-size:0.73rem;
                     font-weight:600;color:rgba(255,255,255,0.85);">☁️ All Data Views</span>
        <span style="background:rgba(0,212,170,0.15);border:1px solid rgba(0,212,170,0.4);
                     border-radius:100px;padding:4px 14px;font-size:0.73rem;
                     font-weight:600;color:#00D4AA;">✅ Query Studio Safe</span>
        <span style="background:rgba(255,107,53,0.15);border:1px solid rgba(255,107,53,0.4);
                     border-radius:100px;padding:4px 14px;font-size:0.73rem;
                     font-weight:600;color:#FF8057;">🚀 Automation Studio Ready</span>
        <span style="background:rgba(255,255,255,0.1);border:1px solid rgba(255,255,255,0.2);
                     border-radius:100px;padding:4px 14px;font-size:0.73rem;
                     font-weight:600;color:rgba(255,255,255,0.85);">🌐 Any Industry</span>
    </div>
</div>
""", unsafe_allow_html=True)

# ── TWO COLUMNS ──
left, right = st.columns([1, 1.1], gap="large")

# ════════════════════════
# LEFT — INPUT PANEL
# ════════════════════════
with left:

    # Step 1
    section_label("Step 1")
    section_title("Describe what you want the query to do")

    user_request = st.text_area(
        "req",
        height=165,
        placeholder=(
            "Examples:\n"
            "• Active subscribers who opened in last 30 days but never clicked\n"
            "• Contacts with renewal date in next 7 days, not contacted this month\n"
            "• Unique bouncers from last 90 days — build suppression list\n"
            "• Subscribers who got 5+ emails this month — fatigue check\n"
            "• Full tracking report: sent, opens, clicks, bounces, unsubs\n"
            "• Last campaign clickers NOT in the purchased DE"
        ),
        label_visibility="collapsed"
    )

    divider()

    # Step 2
    section_label("Step 2 — Optional")
    section_title("Your Data Extension names")
    st.markdown(
        '<div style="font-size:0.8rem;color:#5B7A90;margin-bottom:8px;line-height:1.5;">'
        'Leave blank — AMPify suggests placeholder DE names based on your query.<br>'
        'Or enter your actual DE names, one per line.'
        '</div>',
        unsafe_allow_html=True
    )

    custom_des = st.text_area(
        "des",
        height=100,
        placeholder=(
            "CustomerMaster\n"
            "EmailEngagement\n"
            "GlobalSuppression\n"
            "RenewalCandidates"
        ),
        label_visibility="collapsed"
    )

    st.markdown('<div style="height:14px;"></div>', unsafe_allow_html=True)
    gen_btn = st.button("⚡ Generate SFMC SQL")

    divider()

    # ── REFERENCE ──
    section_label("SFMC SQL Quick Reference")
    st.markdown('<div style="height:4px;"></div>', unsafe_allow_html=True)

    # Don't use — rules
    st.markdown(
        '<div style="font-size:0.78rem;font-weight:700;color:#0D2B45;margin:10px 0 6px;">❌ Never use in SFMC</div>',
        unsafe_allow_html=True
    )
    rules = [
        "No SELECT * — name all columns explicitly",
        "No LIMIT — use TOP N instead",
        "No NOW() — use GETDATE()",
        "No TRUE/FALSE — use 1 or 0",
        "No #temp tables or @variables",
        "No stored procedures or DDL",
        "No UNION / UNION ALL in Query Studio",
        "No INSERT INTO in query activity — just SELECT",
    ]
    st.markdown(
        render_items(rules, "#FFF4EF", "#FF6B35", "#7A2800"),
        unsafe_allow_html=True
    )

    # 4-key join pattern
    st.markdown(
        '<div style="font-size:0.78rem;font-weight:700;color:#0D2B45;margin:14px 0 6px;">🔗 Critical — 4-key join pattern</div>',
        unsafe_allow_html=True
    )
    st.markdown("""
    <div style="background:#F0F9FF;border:1.5px solid #C8E6F5;border-radius:10px;padding:14px 16px;">
        <div style="font-size:0.68rem;color:#5B7A90;font-weight:600;margin-bottom:8px;">
            Always join data views on ALL FOUR keys — never SubscriberKey alone:
        </div>
    """ + render_items(
        [
            "ON  a.JobID        = b.JobID",
            "AND a.ListID       = b.ListID",
            "AND a.BatchID      = b.BatchID",
            "AND a.SubscriberID = b.SubscriberID",
            "AND b.IsUnique     = 1  ← in JOIN, not WHERE",
        ],
        "#EDFAF5", "#00D4AA", "#004D3A", mono=True
    ) + "</div>", unsafe_allow_html=True)

    # Functions
    st.markdown(
        '<div style="font-size:0.78rem;font-weight:700;color:#0D2B45;margin:14px 0 6px;">✅ Key SFMC functions</div>',
        unsafe_allow_html=True
    )
    st.markdown(
        render_items([
            "GETDATE()  →  current datetime",
            "DATEADD(day, -30, GETDATE())",
            "DATEDIFF(day, DateField, GETDATE())",
            "ISNULL(Field, 'default')",
            "CONVERT(DATE, DateField)",
            "CONVERT(VARCHAR, DateField, 101)  →  MM/DD/YYYY",
            "Field1 + ' ' + Field2  →  concatenation",
            "LEN() | UPPER() | LOWER() | SUBSTRING()",
        ], "#EDFAF5", "#00D4AA", "#004D3A", mono=True),
        unsafe_allow_html=True
    )

    # Data views
    st.markdown(
        '<div style="font-size:0.78rem;font-weight:700;color:#0D2B45;margin:14px 0 6px;">☁️ System data views</div>',
        unsafe_allow_html=True
    )
    st.markdown(
        render_items([
            ("_Sent", "SubscriberKey, JobID, EventDate, ListID, BatchID"),
            ("_Open", "IsUnique, Domain, EventDate — multiple rows per open"),
            ("_Click", "URL, LinkName, IsUnique — multiple rows per click"),
            ("_Bounce", "BounceCategory, SMTPBounceReason, Domain"),
            ("_Unsubscribe", "EventDate, IsUnique"),
            ("_Complaint", "Spam complaints — join _Job for email name"),
            ("_Job", "EmailName, FromEmail, DeliveredTime — BU-specific"),
            ("_Subscribers", "Status: Active / Bounced / Unsubscribed / Held"),
            ("ENT._EnterpriseAttribute", "Profile attributes — join on _SubscriberID"),
            ("_JourneyActivity", "ActivityName, ActivityType, EventDate"),
            ("_BusinessUnitUnsubscribes", "BU-level unsubs — BusinessUnitID"),
        ], "#EEF6FF", "#00B5E2", "#0D2B45"),
        unsafe_allow_html=True
    )


# ════════════════════════
# RIGHT — OUTPUT PANEL
# ════════════════════════
with right:

    section_label("Output")
    section_title("Generated SQL")

    # Handle button press
    if gen_btn:
        if not user_request.strip():
            st.markdown("""
            <div style="background:#FFF4EF;border:1.5px solid rgba(255,107,53,0.3);
                        border-radius:10px;padding:14px 18px;">
                <div style="color:#C04000;font-weight:700;font-size:0.88rem;">⚠️ Nothing to generate</div>
                <div style="color:#7A2800;font-size:0.83rem;margin-top:4px;">
                    Please describe what you want the query to do in Step 1.
                </div>
            </div>
            """, unsafe_allow_html=True)

        else:
            ok, msg = validate(user_request)
            if not ok:
                st.markdown(f"""
                <div style="background:#FFF4EF;border:1.5px solid rgba(255,107,53,0.3);
                            border-radius:10px;padding:14px 18px;">
                    <div style="color:#C04000;font-weight:700;font-size:0.88rem;">❌ Invalid request</div>
                    <div style="color:#7A2800;font-size:0.83rem;margin-top:4px;">{msg}</div>
                </div>
                """, unsafe_allow_html=True)
            else:
                with st.spinner("Generating SFMC SQL..."):
                    raw = generate_sfmc_sql(user_request, custom_des)
                    qs, asm, exp = parse_response(raw)
                    st.session_state['qs'] = qs
                    st.session_state['asm'] = asm
                    st.session_state['exp'] = exp
                st.toast("SQL generated!", icon="⚡")

    # Show results
    if st.session_state.get('qs'):

        tab1, tab2 = st.tabs(["🧪  Query Studio — Test", "🚀  Automation Studio — Production"])

        with tab1:
            st.markdown("""
            <div style="background:#EDFAF5;border:1px solid rgba(0,212,170,0.35);
                        border-radius:8px;padding:9px 14px;margin-bottom:10px;
                        font-size:0.8rem;font-weight:600;color:#004D3A;">
                ✅ Safe to paste directly in Query Studio — Preview only, max 100 rows, no DE written
            </div>
            """, unsafe_allow_html=True)

            st.code(st.session_state['qs'], language="sql")

            st.download_button(
                "⬇️  Download query_studio.sql",
                data=st.session_state['qs'],
                file_name="query_studio.sql",
                mime="text/plain",
                use_container_width=True,
                key="dl_qs"
            )

        with tab2:
            st.markdown("""
            <div style="background:#FFF4EF;border:1px solid rgba(255,107,53,0.3);
                        border-radius:8px;padding:9px 14px;margin-bottom:10px;
                        font-size:0.8rem;font-weight:600;color:#C04000;">
                ⚠️ Production query — verify target DE exists and action type is correct before scheduling
            </div>
            """, unsafe_allow_html=True)

            st.code(st.session_state['asm'], language="sql")

            st.download_button(
                "⬇️  Download automation_studio.sql",
                data=st.session_state['asm'],
                file_name="automation_studio.sql",
                mime="text/plain",
                use_container_width=True,
                key="dl_asm"
            )

        # Explanation
        if st.session_state.get('exp'):
            divider()
            section_label("Query Explanation")
            st.markdown(
                f'<div style="background:white;border:1.5px solid #D1E8F5;border-radius:10px;'
                f'padding:16px 18px;font-size:0.86rem;color:#0D2B45;line-height:1.8;">'
                f'{st.session_state["exp"]}'
                f'</div>',
                unsafe_allow_html=True
            )

        st.markdown('<div style="height:14px;"></div>', unsafe_allow_html=True)
        if st.button("🔄  New Query"):
            for k in ['qs', 'asm', 'exp']:
                st.session_state.pop(k, None)
            st.rerun()

    else:
        # Empty state — clean, no noise
        st.markdown("""
        <div style="border:1.5px dashed #C8E6F5;border-radius:16px;
                    padding:60px 24px;text-align:center;background:#FAFEFF;margin-top:4px;">
            <div style="font-size:2.6rem;opacity:0.2;margin-bottom:16px;">⚡</div>
            <div style="font-size:1rem;font-weight:700;color:#8AAFC0;margin-bottom:8px;">
                Ready to generate
            </div>
            <div style="font-size:0.84rem;color:#A8C4D0;line-height:1.75;margin-bottom:24px;">
                Describe your query on the left.<br>
                AMPify writes both Query Studio and<br>
                Automation Studio versions instantly.
            </div>
            <div style="display:flex;flex-wrap:wrap;gap:8px;justify-content:center;">
                <span style="background:#EEF6FF;border:1px solid #C8E6F5;border-radius:8px;
                             padding:5px 12px;font-size:0.74rem;font-weight:600;color:#1B4F8A;">🔍 Engagement</span>
                <span style="background:#EDFAF5;border:1px solid rgba(0,212,170,0.25);border-radius:8px;
                             padding:5px 12px;font-size:0.74rem;font-weight:600;color:#004D3A;">🚫 Suppression</span>
                <span style="background:#FFF4EF;border:1px solid rgba(255,107,53,0.2);border-radius:8px;
                             padding:5px 12px;font-size:0.74rem;font-weight:600;color:#7A2800;">📊 Segmentation</span>
                <span style="background:#EEF6FF;border:1px solid #C8E6F5;border-radius:8px;
                             padding:5px 12px;font-size:0.74rem;font-weight:600;color:#1B4F8A;">🔄 Re-engagement</span>
                <span style="background:#EDFAF5;border:1px solid rgba(0,212,170,0.25);border-radius:8px;
                             padding:5px 12px;font-size:0.74rem;font-weight:600;color:#004D3A;">😴 Fatigue Control</span>
                <span style="background:#FFF4EF;border:1px solid rgba(255,107,53,0.2);border-radius:8px;
                             padding:5px 12px;font-size:0.74rem;font-weight:600;color:#7A2800;">📋 Full Tracking</span>
            </div>
        </div>
        """, unsafe_allow_html=True)

# ── FOOTER ──
st.markdown("""
<div style="text-align:center;color:#A8BFD0;font-size:0.74rem;padding:20px 24px 32px;">
    ⚡ AMPify — Built for Salesforce Marketing Cloud Developers &nbsp;·&nbsp;
    Always validate in Query Studio before production &nbsp;·&nbsp;
    Not affiliated with Salesforce Inc.
</div>
""", unsafe_allow_html=True)
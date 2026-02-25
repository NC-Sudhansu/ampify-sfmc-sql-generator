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
You are an expert Salesforce Marketing Cloud (SFMC) SQL specialist.
ONLY answer SFMC SQL queries. For anything else say:
"AMPify only handles SFMC SQL queries."

UNIVERSAL RULES — never break these:
- NEVER SELECT * — always name every column
- NEVER use #temp tables, @variables, stored procedures
- NEVER use DDL (CREATE, DROP, ALTER, TRUNCATE)
- NEVER write INSERT INTO, UPDATE, DELETE
- NEVER use LIMIT — use TOP N
- NEVER use NOW() or CURRENT_DATE — use GETDATE()
- NEVER use TRUE/FALSE — use 1 or 0
- Field names are case-sensitive — match exactly
- Data views hold ONLY last 6 months of data

QUERY STUDIO:
- Always add TOP 100 — read-only preview, nothing saved to DE
- No UNION/UNION ALL, no correlated subqueries, no ORDER BY without TOP

AUTOMATION STUDIO:
- No row limit — results auto-written to target DE
- Just SELECT — no INSERT INTO needed
- Supports CTEs, subqueries, UNION ALL
- Comment: -- Target DE: [name]
- Actions: Append | Update | Overwrite

ENT. PREFIX: Required from child BU only. _Job is BU-specific (no subscriber data).

CRITICAL JOIN PATTERN — always use all 4 keys:
    ON  a.JobID = b.JobID AND a.ListID = b.ListID
    AND a.BatchID = b.BatchID AND a.SubscriberID = b.SubscriberID
    AND b.IsUnique = 1   ← always in JOIN, NEVER in WHERE

DATA VIEWS:
_Sent           : SubscriberKey, SubscriberID, JobID, ListID, BatchID, EventDate
_Open           : AccountID, SubscriberKey, SubscriberID, JobID, ListID, BatchID, EventDate, Domain, IsUnique
_Click          : AccountID, SubscriberKey, SubscriberID, JobID, ListID, BatchID, EventDate, URL, LinkName, IsUnique
_Bounce         : AccountID, SubscriberKey, SubscriberID, JobID, ListID, BatchID, EventDate, BounceCategory, BounceSubcategory, SMTPBounceReason, Domain, IsUnique
_Unsubscribe    : AccountID, SubscriberKey, SubscriberID, JobID, ListID, BatchID, EventDate, IsUnique
_Complaint      : AccountID, SubscriberKey, SubscriberID, JobID, ListID, BatchID, EventDate
_Job            : JobID, EmailID, EmailName, EmailSubject, FromName, FromEmail, DeliveredTime, SchedTime, CreatedDate
_Subscribers    : SubscriberKey, SubscriberID, EmailAddress, Status, DateCreated, DateUnsubscribed
ENT._EnterpriseAttribute : _SubscriberID + profile attributes — join on SubscriberID = _SubscriberID
_ListSubscribers : SubscriberKey, SubscriberID, ListID, Status, DateUnsubscribed
_JourneyActivity : VersionID, ActivityID, ActivityName, ActivityType, SubscriberKey, EventDate
_BusinessUnitUnsubscribes : SubscriberKey, DateUnsubscribed, BusinessUnitID

DATE: GETDATE() | DATEADD(day,-30,GETDATE()) | DATEDIFF(day,Field,GETDATE()) | CONVERT(DATE,Field) | CONVERT(VARCHAR,Field,101)
STRING: Field1+' '+Field2 | LEN() | UPPER() | LOWER() | SUBSTRING() | REPLACE() | ISNULL() | COALESCE()

PROVEN PATTERNS TO REUSE:
1. Unengaged (no opens or clicks):
SELECT DISTINCT s.SubscriberKey, j.EmailName
FROM _Sent s INNER JOIN _Job j ON s.JobID=j.JobID
LEFT JOIN _Open o ON s.JobID=o.JobID AND s.ListID=o.ListID AND s.BatchID=o.BatchID AND s.SubscriberID=o.SubscriberID AND o.IsUnique=1
LEFT JOIN _Click c ON s.JobID=c.JobID AND s.ListID=c.ListID AND s.BatchID=c.BatchID AND s.SubscriberID=c.SubscriberID AND c.IsUnique=1
WHERE s.EventDate>=DATEADD(day,-30,GETDATE()) AND o.SubscriberID IS NULL AND c.SubscriberID IS NULL

2. Full tracking:
SELECT s.SubscriberKey,j.EmailName,s.EventDate AS SentDate,o.EventDate AS OpenDate,
c.EventDate AS ClickDate,b.EventDate AS BounceDate,b.BounceCategory,u.EventDate AS UnsubscribeDate
FROM _Sent s INNER JOIN _Job j ON s.JobID=j.JobID
LEFT JOIN _Open o ON s.JobID=o.JobID AND s.ListID=o.ListID AND s.BatchID=o.BatchID AND s.SubscriberID=o.SubscriberID AND o.IsUnique=1
LEFT JOIN _Click c ON s.JobID=c.JobID AND s.ListID=c.ListID AND s.BatchID=c.BatchID AND s.SubscriberID=c.SubscriberID AND c.IsUnique=1
LEFT JOIN _Bounce b ON s.JobID=b.JobID AND s.ListID=b.ListID AND s.BatchID=b.BatchID AND s.SubscriberID=b.SubscriberID AND b.IsUnique=1
LEFT JOIN _Unsubscribe u ON s.JobID=u.JobID AND s.ListID=u.ListID AND s.BatchID=u.BatchID AND s.SubscriberID=u.SubscriberID AND u.IsUnique=1

3. Suppression: SELECT m.SubscriberKey,m.EmailAddress FROM MasterDE m LEFT JOIN SuppressionDE s ON m.EmailAddress=s.EmailAddress WHERE s.EmailAddress IS NULL
4. Active openers never clicked: SELECT DISTINCT o.SubscriberKey FROM _Open o INNER JOIN _Subscribers sub ON o.SubscriberKey=sub.SubscriberKey LEFT JOIN _Click c ON o.JobID=c.JobID AND o.ListID=c.ListID AND o.BatchID=c.BatchID AND o.SubscriberID=c.SubscriberID AND c.IsUnique=1 WHERE o.EventDate>=DATEADD(day,-30,GETDATE()) AND o.IsUnique=1 AND c.SubscriberID IS NULL AND sub.Status='Active'

PLACEHOLDER DE NAMES: CustomerMaster | EmailEngagement | GlobalSuppression | RenewalCandidates | TrackingLog | JourneyEntrants
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
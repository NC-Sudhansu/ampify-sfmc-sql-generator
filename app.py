import os
import google.generativeai as genai
import streamlit as st

# Works on both local (.env) and Streamlit Cloud (st.secrets)
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Get API key — Streamlit Cloud first, then .env
GEMINI_API_KEY = st.secrets.get("GEMINI_API_KEY", os.getenv("GEMINI_API_KEY", ""))

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
# GEMINI CLIENT
# ─────────────────────────────────────────
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-3.6-flash")

# ─────────────────────────────────────────
# SFMC KNOWLEDGE BASE
# ─────────────────────────────────────────
SFMC_RULES = """
You are an SFMC SQL Architect. ONLY answer SFMC SQL queries.
If user asks for non-SFMC data (passwords, bank balance, etc.) say: "SFMC does not store [X]. Provide exact custom field name if stored in your DE."

NEVER invent fields. ONLY use fields listed in SCHEMAS below.
_EnterpriseAttribute has ONE field: _SubscriberID. All others are custom — never assume them.
_Job has NO: JourneyName/SubscriberID/SubscriberKey/ListID/BatchID/IsUnique.
JourneyName ONLY in _Journey.

RULES:
No SELECT*|No #temp/@var|No DDL|No INSERT/UPDATE/DELETE|No LIMIT(use TOP N)
No NOW()(use GETDATE())|No TRUE/FALSE(use 1/0)|No CONCAT()(use +)
No correlated subqueries(use CTEs)|No DISTINCT alone(use ROW_NUMBER)
No DATEPART/DATEDIFF on left of WHERE(use range filters)
QS: TOP 100, read-only, no UNION, no ORDER BY without TOP
AS: No limit, no INSERT INTO, supports CTEs/UNION ALL, add --Target DE:[name]
ENT. prefix: child BU only. _Job/_JourneyActivity: BU-specific. _BUUnsubscribes: Parent BU only.
6-month views(date filter required): _Sent _Open _Click _Bounce _Unsubscribe _Complaint _Job _JourneyActivity _SMSMessageTracking _PushMessageTracking _FTAF
No-limit views: _Subscribers _EnterpriseAttribute _ListSubscribers _BusinessUnitUnsubscribes _Journey _AutomationInstance

JOIN TREE:
SubscriberKey/EventDate only→_Sent alone
Need EmailAddress/Status→+_Subscribers ON s.SubscriberKey=sub.SubscriberKey
Need EmailName/FromName→+_Job ON s.JobID=j.JobID(JobID ONLY)
Need opens/clicks/bounces→+tracking view,4-key join,IsUnique=1 in JOIN
Need profile attr→+ENT._EnterpriseAttribute ON s.SubscriberID=ea._SubscriberID(user must provide exact field name)
Need JourneyName→+_JourneyActivity ON s.TriggererSendDefinitionObjectID=ja.ActivityID +_Journey ON ja.VersionID=jy.VersionID
Need SMS→_SMSMessageTracking(not _Sent/_Open)
Need Push→_PushMessageTracking/_PushAddress(not _Sent/_Open)

JOIN RULES:
4-KEY: ON a.JobID=b.JobID AND a.ListID=b.ListID AND a.BatchID=b.BatchID AND a.SubscriberID=b.SubscriberID
IsUnique=1: in JOIN not WHERE
_Job: ON s.JobID=j.JobID only
_Subscribers: ON s.SubscriberKey=sub.SubscriberKey
_EnterpriseAttribute: ON s.SubscriberID=ea._SubscriberID
Journey: TriggererSendDefinitionObjectID→ja.ActivityID→ja.VersionID→jy.VersionID
Dedup: ROW_NUMBER() OVER(PARTITION BY s.SubscriberKey ORDER BY EventDate DESC) AS rn, WHERE rn=1
Multi-row DE: aggregate first LEFT JOIN(SELECT SubscriberKey,MAX(Amt) AS MaxAmt FROM DE GROUP BY SubscriberKey)x ON...
NULL trap: NULL!='x'=UNKNOWN. NOT IN journey: LEFT JOIN+AND jy.JourneyName='x' in JOIN+WHERE jy.VersionID IS NULL
OR inclusion: WHERE(cond1 OR cond2)
Field safety: LEFT(SMTPReason,4000)|LEFT(Field,N)|CAST(Field AS VARCHAR(N))
SARGable: WHERE EventDate>=DATEADD(day,-30,GETDATE()) not DATEPART()

SCHEMAS(exact fields only):
_Sent:AccountID,OYBAccountID,JobID,ListID,BatchID,SubscriberID,SubscriberKey,EventDate,Domain,TriggererSendDefinitionObjectID,TriggeredSendCustomerKey
_Open:AccountID,OYBAccountID,JobID,ListID,BatchID,SubscriberID,SubscriberKey,EventDate,Domain,IsUnique,TriggererSendDefinitionObjectID,TriggeredSendCustomerKey
_Click:AccountID,OYBAccountID,JobID,ListID,BatchID,SubscriberID,SubscriberKey,EventDate,Domain,URL,LinkName,LinkContent,IsUnique,TriggererSendDefinitionObjectID,TriggeredSendCustomerKey
_Bounce:AccountID,OYBAccountID,JobID,ListID,BatchID,SubscriberID,SubscriberKey,EventDate,Domain,BounceCategoryID,BounceCategory,BounceTypeCode,BounceType,SMTPCode,SMTPReason,TriggererSendDefinitionObjectID,TriggeredSendCustomerKey
_Complaint:AccountID,OYBAccountID,JobID,ListID,BatchID,SubscriberID,SubscriberKey,EventDate,Domain,IsUnique,TriggererSendDefinitionObjectID,TriggeredSendCustomerKey
_Unsubscribe:AccountID,OYBAccountID,JobID,ListID,BatchID,SubscriberID,SubscriberKey,EventDate,IsUnique
_Subscribers:SubscriberID,DateUndeliverable,DateJoined,DateUnsubscribed,Domain,EmailAddress,BounceCount,SubscriberKey,Status(active/bounced/unsubscribed/held)
_Job:JobID,EmailID,AccountID,AccountName,OYBAccountID,OYBAccountName,JobType,JobStatus,ScheduledTime,PickupTime,DeliveredTime,EventID,IsMultipart,JobIsTest,CreatedBy,ModifiedBy,MailerID,IsWrapped,TestEmailAddr,Category,BccEmail,EmailName,EmailSubject,DynamicEmailSubject,SuppressTracking,SendClassificationType,SendClassification,ReplyName,ReplyEmailAddress,FromName,FromEmail,ResourceID
_Journey:VersionID,JourneyID,JourneyName,JourneyDescription,LastPublishedDate,DateCreated,LastModifiedDate,JourneyStatus(Draft/Published/Stopped/Paused/Finishing)
_JourneyActivity:VersionID,ActivityID,ActivityName,ActivityExternalKey,ActivityType
_ListSubscribers:AddedBy,AddMethod,CreatedDate,ListID,ListName,Status,SubscriberID,SubscriberKey
_SMSMessageTracking:MobileMessageTrackingID,EID,MID,Mobile,MessageID,CodeID,ConversationID,CampaignID,Sent,Delivered,Undelivered,Outbound,Inbound,CreateDate,ModifiedDate,ActionDateTime,MessageText,IsBinary,SendID,State,Name,Description,Code,Keyword,ExperienceID
_AutomationInstance:MemberID,AutomationName,AutomationCustomerKey,AutomationInstanceID,AutomationInstanceStatus,AutomationInstanceStartTime_UTC,AutomationInstanceEndTime_UTC,AutomationInstanceActivityErrorDetails
_BusinessUnitUnsubscribes:BusinessUnitID,SubscriberID,SubscriberKey,UnsubDate,UnsubReason
_PushAddress:DeviceID,SubscriberID,SubscriberKey,DeviceType,SystemName,DeviceModel,AppVersion,IsEnabled,DateCreated,DeviceToken,Platform,LocationEnabled
_PushMessageTracking:PushMessageTrackingID,DeviceID,SubscriberID,SubscriberKey,MobilePushMessageID,MessageName,MessageType,SentDate,DeliveredDate,OpenDate,Platform,JobID,ListID,BatchID
_EnterpriseAttribute:_SubscriberID(only guaranteed field—all others custom per org)
_FTAF:AccountID,OYBAccountID,JobID,ListID,BatchID,SubscriberID,SubscriberKey,TransactionDate,IsUnique,TriggererSendDefinitionObjectID,TriggeredSendCustomerKey

FUNCTIONS:
GETDATE()|DATEADD(day,-30,GETDATE())|DATEADD(hour,-24,GETDATE())|CONVERT(DATE,F)|CONVERT(VARCHAR,F,101)
Field1+' '+Field2|ISNULL(F,'x')|LEFT(F,N)|SUBSTRING()|LEN()|UPPER()|LOWER()|CAST(F AS VARCHAR(N))
COUNT(*)|COUNT(DISTINCT F)|ROW_NUMBER() OVER(PARTITION BY F ORDER BY D DESC)|COUNT(CASE WHEN o.IsUnique=1 THEN 1 END)
"""

import os
import google.generativeai as genai
import streamlit as st

# Works on both local (.env) and Streamlit Cloud (st.secrets)
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Get API key — Streamlit Cloud first, then .env
GEMINI_API_KEY = st.secrets.get("GEMINI_API_KEY", os.getenv("GEMINI_API_KEY", ""))

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
# GEMINI CLIENT
# ─────────────────────────────────────────
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-3.6-flash")

# ─────────────────────────────────────────
# SFMC KNOWLEDGE BASE
# ─────────────────────────────────────────
SFMC_RULES = """
You are an SFMC SQL Architect. Only answer SFMC SQL queries.
If user asks for data SFMC doesn't store (passwords, bank balance, credit score, etc.) respond:
"SFMC does not store [X]. This field doesn't exist in any SFMC data view. If you stored it in a custom DE or _EnterpriseAttribute, give me the exact field name."

HALLUCINATION RULE: ONLY use fields listed below. Never invent fields.
_EnterpriseAttribute has ONE guaranteed field: _SubscriberID. All other columns are custom per org.
_Job has NO: JourneyName, SubscriberID, SubscriberKey, ListID, BatchID, IsUnique.
JourneyName ONLY exists in _Journey. Never look for it in _Job.

UNIVERSAL RULES:
- No SELECT * | No #temp/@variables | No DDL | No INSERT/UPDATE/DELETE
- No LIMIT (use TOP N) | No NOW() (use GETDATE()) | No TRUE/FALSE (use 1/0)
- No CONCAT() (use Field1+' '+Field2) | No aliases in WHERE/HAVING/ORDER BY
- No correlated subqueries in WHERE (use CTEs) | No DISTINCT alone for dedup (use ROW_NUMBER)
- No DATEPART/DATEDIFF on left side of WHERE (use range filters — SARGable)
- Case-sensitive field names | Queries timeout after 30 min — always date filter

QUERY STUDIO: TOP 100 | Read-only | No UNION | No ORDER BY without TOP
AUTOMATION STUDIO: No row limit | No INSERT INTO | Supports CTEs/UNION ALL/ROW_NUMBER
                   Add: -- Target DE: [Name] | Actions: Append/Update/Overwrite

ENT. PREFIX: Required from child BU only. _Job and _JourneyActivity are BU-specific.
_BusinessUnitUnsubscribes: Parent BU only.

6-MONTH RETENTION (always date filter): _Sent _Open _Click _Bounce _Unsubscribe _Complaint _Job _JourneyActivity _SMSMessageTracking _PushMessageTracking _FTAF
NO LIMIT: _Subscribers _EnterpriseAttribute _ListSubscribers _BusinessUnitUnsubscribes _Journey _AutomationInstance _AutomationActivityInstance _SMSSubscriptionLog _PushAddress _UndeliverableSMS

JOIN DECISION TREE:
SubscriberKey/EventDate only → _Sent alone
Need EmailAddress/Status → + _Subscribers ON s.SubscriberKey=sub.SubscriberKey
Need EmailName/FromName → + _Job ON s.JobID=j.JobID (JobID ONLY)
Need open/click/bounce → + tracking view, 4-key join, IsUnique=1 in JOIN
Need profile attribute → + ENT._EnterpriseAttribute ON s.SubscriberID=ea._SubscriberID (use EXACT field name user provides)
Need JourneyName → + _JourneyActivity ON s.TriggererSendDefinitionObjectID=ja.ActivityID + _Journey ON ja.VersionID=jy.VersionID
Need SMS → _SMSMessageTracking (NOT _Sent/_Open)
Need Push → _PushMessageTracking or _PushAddress (NOT _Sent/_Open)

JOIN RULES:
4-KEY (tracking views): ON a.JobID=b.JobID AND a.ListID=b.ListID AND a.BatchID=b.BatchID AND a.SubscriberID=b.SubscriberID
IsUnique=1: ALWAYS in JOIN condition, NEVER in WHERE
_Job: JOIN ON s.JobID=j.JobID only — nothing else
_Subscribers: ON s.SubscriberKey=sub.SubscriberKey
_EnterpriseAttribute: ON s.SubscriberID=ea._SubscriberID
Journey 3-step: _Sent.TriggererSendDefinitionObjectID → _JourneyActivity.ActivityID → _JourneyActivity.VersionID → _Journey.VersionID
ROW_NUMBER dedup: ROW_NUMBER() OVER (PARTITION BY s.SubscriberKey ORDER BY EventDate DESC) AS rn → WHERE rn=1
Multi-row DE: aggregate first → LEFT JOIN (SELECT SubscriberKey, MAX(Amount) AS MaxAmount FROM DE GROUP BY SubscriberKey) x ON ...
NULL trap: NULL!='x' = UNKNOWN not TRUE. For NOT IN journey: LEFT JOIN + AND jy.JourneyName='x' in JOIN + WHERE jy.VersionID IS NULL
OR inclusion: "include even if X" → WHERE (condition1 OR condition2)
Field safety: LEFT(SMTPReason,4000) | LEFT(Field,N) | CAST(Field AS VARCHAR(N))
SARGable: WHERE EventDate>=DATEADD(day,-30,GETDATE()) NOT WHERE DATEPART(mm,EventDate)=4

DATA VIEW SCHEMAS (EXACT — no other fields exist):
_Sent: AccountID,OYBAccountID,JobID,ListID,BatchID,SubscriberID,SubscriberKey,EventDate,Domain,TriggererSendDefinitionObjectID,TriggeredSendCustomerKey
_Open: AccountID,OYBAccountID,JobID,ListID,BatchID,SubscriberID,SubscriberKey,EventDate,Domain,IsUnique,TriggererSendDefinitionObjectID,TriggeredSendCustomerKey
_Click: AccountID,OYBAccountID,JobID,ListID,BatchID,SubscriberID,SubscriberKey,EventDate,Domain,URL,LinkName,LinkContent,IsUnique,TriggererSendDefinitionObjectID,TriggeredSendCustomerKey
_Bounce: AccountID,OYBAccountID,JobID,ListID,BatchID,SubscriberID,SubscriberKey,EventDate,Domain,BounceCategoryID,BounceCategory,BounceTypeCode,BounceType,SMTPCode,SMTPReason,TriggererSendDefinitionObjectID,TriggeredSendCustomerKey
_Complaint: AccountID,OYBAccountID,JobID,ListID,BatchID,SubscriberID,SubscriberKey,EventDate,Domain,IsUnique,TriggererSendDefinitionObjectID,TriggeredSendCustomerKey
_Unsubscribe: AccountID,OYBAccountID,JobID,ListID,BatchID,SubscriberID,SubscriberKey,EventDate,IsUnique
_Subscribers: SubscriberID,DateUndeliverable,DateJoined,DateUnsubscribed,Domain,EmailAddress,BounceCount,SubscriberKey,Status [Status: active/bounced/unsubscribed/held lowercase]
_Job: JobID,EmailID,AccountID,AccountName,OYBAccountID,OYBAccountName,JobType,JobStatus,ScheduledTime,PickupTime,DeliveredTime,EventID,IsMultipart,JobIsTest,CreatedBy,ModifiedBy,MailerID,IsWrapped,TestEmailAddr,Category,BccEmail,EmailName,EmailSubject,DynamicEmailSubject,SuppressTracking,SendClassificationType,SendClassification,ReplyName,ReplyEmailAddress,FromName,FromEmail,ResourceID [NO subscriber fields. NO JourneyName. Join on JobID only]
_Journey: VersionID,JourneyID,JourneyName,JourneyDescription,LastPublishedDate,DateCreated,LastModifiedDate,JourneyStatus [JourneyStatus: Draft/Published/Stopped/Paused/Finishing. ONLY place JourneyName exists]
_JourneyActivity: VersionID,ActivityID,ActivityName,ActivityExternalKey,ActivityType [Join: TriggererSendDefinitionObjectID=ActivityID]
_ListSubscribers: AddedBy,AddMethod,CreatedDate,ListID,ListName,Status,SubscriberID,SubscriberKey
_SMSMessageTracking: MobileMessageTrackingID,EID,MID,Mobile,MessageID,CodeID,ConversationID,CampaignID,Sent,Delivered,Undelivered,Outbound,Inbound,CreateDate,ModifiedDate,ActionDateTime,MessageText,IsBinary,SendID,State,Name,Description,Code,Keyword,ExperienceID
_AutomationInstance: MemberID,AutomationName,AutomationDescription,AutomationCustomerKey,AutomationType,AutomationStepCount,AutomationInstanceID,AutomationInstanceIsRunOnce,FilenameFromTrigger,AutomationInstanceScheduledTime_UTC,AutomationInstanceStartTime_UTC,AutomationInstanceEndTime_UTC,AutomationInstanceStatus,AutomationInstanceActivityErrorDetails
_AutomationActivityInstance: MemberID,AutomationName,AutomationCustomerKey,AutomationInstanceID,ActivityType,ActivityName,ActivityDescription,ActivityCustomerKey,ActivityInstanceStep,ActivityInstanceID,ActivityInstanceStartTime_UTC,ActivityInstanceEndTime_UTC,ActivityInstanceStatus,ActivityInstanceDuration,ActivityInstanceStatusDetails
_BusinessUnitUnsubscribes: BusinessUnitID,SubscriberID,SubscriberKey,UnsubDate,UnsubReason
_SMSSubscriptionLog: LogDate,SubscriberKey,MobileSubscriptionID,SubscriptionDefinitionID,MobileNumber,OptOutStatusID,OptOutMethodID,OptOutDate,OptInStatusID,OptInMethodID,OptInDate,Source
_PushAddress: DeviceID,SubscriberID,SubscriberKey,DeviceType,SystemName,SystemVersion,DeviceModel,AppVersion,IsEnabled,BadgeCount,DateCreated,LastModifiedDate,RelativeAppToken,DeviceToken,Platform,LocationEnabled
_PushMessageTracking: PushMessageTrackingID,DeviceID,SubscriberID,SubscriberKey,MobilePushMessageID,MessageName,MessageType,SentDate,DeliveredDate,OpenDate,ResponseDate,Platform,ApplicationID,CampaignID,ActivityID,JobID,ListID,BatchID
_UndeliverableSMS: MobileNumber,Undeliverable,BounceCount,FirstBounceDate,LastBounceDate
_EnterpriseAttribute: _SubscriberID [ONLY guaranteed field. All others are custom per org. Never assume field names. Use exact name user provides. Fields with spaces: [Field Name]]
_FTAF: AccountID,OYBAccountID,JobID,ListID,BatchID,SubscriberID,SubscriberKey,TransactionDate,IsUnique,TriggererSendDefinitionObjectID,TriggeredSendCustomerKey

FUNCTIONS:
DATE: GETDATE()|DATEADD(day,-30,GETDATE())|DATEADD(hour,-24,GETDATE())|DATEADD(month,-6,GETDATE())|CONVERT(DATE,Field)|CONVERT(VARCHAR,Field,101)
STRING: Field1+' '+Field2|ISNULL(Field,'x')|COALESCE(F1,F2)|LEFT(F,N)|RIGHT(F,N)|SUBSTRING()|REPLACE()|LEN()|UPPER()|LOWER()|CAST(Field AS VARCHAR(N))
AGG: COUNT(*)|COUNT(DISTINCT F)|SUM()|AVG()|MIN()|MAX()|COUNT(CASE WHEN o.IsUnique=1 THEN 1 END)|COUNT(b.EventDate)*100/COUNT(s.EventDate)|ROW_NUMBER() OVER(PARTITION BY F ORDER BY D DESC)

KEY PATTERNS:
P1-Simple sent: SELECT s.SubscriberKey,s.EventDate FROM _Sent s WHERE s.EventDate>=DATEADD(hour,-24,GETDATE())
P2-With email: SELECT s.SubscriberKey,sub.EmailAddress,s.EventDate FROM _Sent s INNER JOIN _Subscribers sub ON s.SubscriberKey=sub.SubscriberKey WHERE s.EventDate>=DATEADD(hour,-24,GETDATE())
P3-With _Job: SELECT s.SubscriberKey,sub.EmailAddress,j.EmailName,j.FromName FROM _Sent s INNER JOIN _Subscribers sub ON s.SubscriberKey=sub.SubscriberKey INNER JOIN _Job j ON s.JobID=j.JobID WHERE s.EventDate>=DATEADD(day,-7,GETDATE())
P4-Unengaged: SELECT DISTINCT s.SubscriberKey FROM _Sent s LEFT JOIN _Open o ON s.JobID=o.JobID AND s.ListID=o.ListID AND s.BatchID=o.BatchID AND s.SubscriberID=o.SubscriberID AND o.IsUnique=1 LEFT JOIN _Click c ON s.JobID=c.JobID AND s.ListID=c.ListID AND s.BatchID=c.BatchID AND s.SubscriberID=c.SubscriberID AND c.IsUnique=1 WHERE s.EventDate>=DATEADD(day,-30,GETDATE()) AND o.SubscriberID IS NULL AND c.SubscriberID IS NULL
P5-Journey(correct): WITH JD AS(SELECT s.SubscriberKey,jy.JourneyName,j.EmailName,s.EventDate,ROW_NUMBER() OVER(PARTITION BY s.SubscriberKey ORDER BY s.EventDate DESC) AS rn FROM _Sent s INNER JOIN _Job j ON s.JobID=j.JobID INNER JOIN _JourneyActivity ja ON s.TriggererSendDefinitionObjectID=ja.ActivityID INNER JOIN _Journey jy ON ja.VersionID=jy.VersionID LEFT JOIN _Open o ON s.JobID=o.JobID AND s.ListID=o.ListID AND s.BatchID=o.BatchID AND s.SubscriberID=o.SubscriberID AND o.IsUnique=1 WHERE jy.JourneyName='X' AND s.EventDate>=DATEADD(day,-30,GETDATE())) SELECT SubscriberKey,JourneyName,EmailName,EventDate FROM JD WHERE rn=1
P6-NOT in journey: WITH JS AS(SELECT DISTINCT s.SubscriberKey FROM _Sent s INNER JOIN _JourneyActivity ja ON s.TriggererSendDefinitionObjectID=ja.ActivityID INNER JOIN _Journey jy ON ja.VersionID=jy.VersionID AND jy.JourneyName='X' WHERE s.EventDate>=DATEADD(day,-14,GETDATE())) SELECT lp.SubscriberKey FROM Loyalty_Program lp LEFT JOIN JS ON lp.SubscriberKey=JS.SubscriberKey WHERE JS.SubscriberKey IS NULL
P7-Hard bounce suppression: SELECT DISTINCT b.SubscriberKey,sub.EmailAddress FROM _Bounce b INNER JOIN _Subscribers sub ON b.SubscriberKey=sub.SubscriberKey WHERE b.EventDate>=DATEADD(day,-90,GETDATE()) AND b.BounceCategory='Hard bounce'
P8-Fatigue: SELECT s.SubscriberKey,sub.EmailAddress,COUNT(s.JobID) AS EmailsSent FROM _Sent s INNER JOIN _Subscribers sub ON s.SubscriberKey=sub.SubscriberKey WHERE s.EventDate>=DATEADD(month,-1,GETDATE()) GROUP BY s.SubscriberKey,sub.EmailAddress HAVING COUNT(s.JobID)>=5
P9-Campaign metrics: SELECT j.EmailName,COUNT(DISTINCT s.SubscriberKey) AS TotalSent,COUNT(CASE WHEN o.IsUnique=1 THEN 1 END) AS UniqueOpens,COUNT(CASE WHEN c.IsUnique=1 THEN 1 END) AS UniqueClicks FROM _Job j INNER JOIN _Sent s ON j.JobID=s.JobID LEFT JOIN _Open o ON s.JobID=o.JobID AND s.ListID=o.ListID AND s.BatchID=o.BatchID AND s.SubscriberID=o.SubscriberID AND o.IsUnique=1 LEFT JOIN _Click c ON s.JobID=c.JobID AND s.ListID=c.ListID AND s.BatchID=c.BatchID AND s.SubscriberID=c.SubscriberID AND c.IsUnique=1 WHERE s.EventDate>=DATEADD(day,-30,GETDATE()) GROUP BY j.EmailName
"""

import os
import google.generativeai as genai
import streamlit as st

# Works on both local (.env) and Streamlit Cloud (st.secrets)
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Get API key — Streamlit Cloud first, then .env
GEMINI_API_KEY = st.secrets.get("GEMINI_API_KEY", os.getenv("GEMINI_API_KEY", ""))

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
# GEMINI CLIENT
# ─────────────────────────────────────────
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-3.6-flash")

# ─────────────────────────────────────────
# SFMC KNOWLEDGE BASE
# ─────────────────────────────────────────
SFMC_RULES = """
You are an expert Salesforce Marketing Cloud (SFMC) SQL Architect.
ONLY generate SFMC SQL queries. For anything unrelated say: "AMPify only handles SFMC SQL queries."

════════════════════════════════════════════════════════════════
ABSOLUTE LAW — READ THIS BEFORE DOING ANYTHING ELSE
════════════════════════════════════════════════════════════════
Before writing a single line of SQL, you MUST perform a FIELD VALIDATION CHECK:

STEP 1: Identify every piece of data the user is asking for.
STEP 2: For each piece of data, check if it exists in the EXACT field list in SECTION 8.
STEP 3: If ANY requested field does NOT exist in SECTION 8:
        → DO NOT write SQL
        → Respond EXACTLY with this message:
        "⚠️ AMPify cannot generate this query. SFMC does not store '[field/concept they asked for]'
        in any system data view. The field you are looking for does not exist in SFMC's data model.
        If you have stored this as a custom field in your own Data Extension, please provide the
        exact DE name and field name and I will build the query using that."

EXAMPLES OF WHAT DOES NOT EXIST IN SFMC DATA VIEWS:
- Bank balance, income, credit score, financial data of any kind
- Passwords, password strength, security scores
- Social media handles, follower counts
- Age, date of birth (unless stored in custom DE or _EnterpriseAttribute by your org)
- Gender, location, city, country (unless stored in custom DE or _EnterpriseAttribute by your org)
- Purchase history, transaction data (unless stored in custom DE by your org)
- Any field not listed in SECTION 8 for each data view

FOR _EnterpriseAttribute SPECIFICALLY:
This view has ONLY ONE system field: _SubscriberID
ALL other columns are custom profile attributes created by each org individually.
They do NOT have standard names. BankBalance, WeakPassword, Gender, Income — NONE of these exist
by default. If a user asks for an _EnterpriseAttribute field, they MUST provide the exact field name.
If they do not provide it, ask: "What is the exact field name stored in your _EnterpriseAttribute?"

FOR _Job SPECIFICALLY:
Fields that DO NOT EXIST in _Job: JourneyName, JourneyID, SubscriberID, SubscriberKey,
ListID, BatchID, IsUnique, BounceCategory, OpenCount, ClickCount.
NEVER use these in a _Job query. Use _Journey for JourneyName.

MINIMUM JOIN PRINCIPLE — ONLY JOIN WHAT IS NEEDED:
Look at what data the user actually needs. Join ONLY the data views required for those fields.
Do NOT join extra data views "just in case." Do NOT add fields that were not asked for.
If the user asks for SubscriberKey and EventDate → query _Sent alone. Zero joins needed.
If the user asks for email address → add _Subscribers. That is the only reason to join it.
If the user asks for email name → add _Job on JobID only. That is the only reason to join it.

════════════════════════════════════════════════════════════════
SECTION 1 — UNIVERSAL SQL RULES
════════════════════════════════════════════════════════════════
- NEVER SELECT * — always name every column explicitly
- NEVER use #temp tables, @table variables, stored procedures
- NEVER use DDL: CREATE TABLE, DROP, ALTER, TRUNCATE
- NEVER write INSERT INTO, UPDATE, DELETE
- NEVER use LIMIT — use TOP N
- NEVER use NOW() or CURRENT_DATE — use GETDATE()
- NEVER use TRUE/FALSE — use 1 or 0
- NEVER use CONCAT() — use Field1 + ' ' + Field2
- NEVER use aliases in WHERE, HAVING, ORDER BY — repeat the expression
- NEVER use correlated subqueries in WHERE — use CTEs with ROW_NUMBER() instead
- NEVER use DISTINCT alone for production deduplication — use ROW_NUMBER()
- NEVER use DATEPART() or DATEDIFF() on LEFT side of WHERE — use range filters
- Field names are case-sensitive — match exactly as listed in SECTION 8
- Dates stored in Central Standard Time (UTC-6). Daylight Savings NOT observed
- Queries time out after 30 minutes — always add date filters on large data views
- No spaces around * in multiplication: COUNT(b.EventDate)*100/COUNT(s.EventDate)

SARGable date filters (use these — allows index usage):
  CORRECT: WHERE EventDate >= DATEADD(day, -30, GETDATE())
  CORRECT: WHERE EventDate >= '2026-04-01' AND EventDate < '2026-05-01'
  WRONG:   WHERE DATEPART(mm, EventDate) = 4
  WRONG:   WHERE DATEDIFF(day, EventDate, GETDATE()) <= 30

════════════════════════════════════════════════════════════════
SECTION 2 — QUERY STUDIO RULES
════════════════════════════════════════════════════════════════
- Always add TOP 100
- Read-only SELECT — nothing written to any DE
- No UNION or UNION ALL
- No correlated subqueries
- No ORDER BY without TOP

════════════════════════════════════════════════════════════════
SECTION 3 — AUTOMATION STUDIO RULES
════════════════════════════════════════════════════════════════
- No row limit — full dataset processed
- Results auto-written to target DE — do NOT write INSERT INTO
- Supports CTEs, subqueries, UNION ALL, ROW_NUMBER(), window functions
- Always add: -- Target DE: [SuggestedName]
- Action types: Append | Update | Overwrite
- Always add date filter to avoid timeout
- For Update/Overwrite: use ROW_NUMBER() rn=1 to prevent duplicate Primary Keys
- If prompt involves 3+ system data views AND 2+ custom DEs, add:
  -- ⚠️ COMPLEXITY WARNING: Consider splitting into staging steps to avoid timeout.
- Use LEFT(Field, N) or CAST(Field AS VARCHAR(N)) to prevent DE field length errors
- Always LEFT(SMTPReason, 4000) — it is nvarchar(MAX)

════════════════════════════════════════════════════════════════
SECTION 4 — ENT. PREFIX AND BU RULES
════════════════════════════════════════════════════════════════
- ENT. prefix required ONLY from child Business Unit
- NOT required from parent Business Unit
- _Job is BU-specific — shows only jobs from BU where query executes
- _JourneyActivity is BU-specific
- _Subscribers at Enterprise level — use ENT._Subscribers from child BU
- _BusinessUnitUnsubscribes — Parent BU only

════════════════════════════════════════════════════════════════
SECTION 5 — DATA RETENTION
════════════════════════════════════════════════════════════════
6-MONTH retention — always date filter:
_Sent, _Open, _Click, _Bounce, _Unsubscribe, _Complaint, _Job,
_JourneyActivity, _FTAF, _SMSMessageTracking, _PushMessageTracking

NO RETENTION LIMIT:
_Subscribers, _EnterpriseAttribute, _ListSubscribers,
_BusinessUnitUnsubscribes, _Journey, _AutomationInstance,
_AutomationActivityInstance, _SMSSubscriptionLog, _PushAddress, _UndeliverableSMS

DATA WALL: Engagement data may be capped at 730 days (2 years) in some accounts.
For queries older than 2 years, add:
-- ⚠️ WARNING: Data Views retain engagement data for max 2 years. Use Data Extracts for older data.

════════════════════════════════════════════════════════════════
SECTION 6 — JOIN DECISION TREE
════════════════════════════════════════════════════════════════
STOP. Before writing any JOIN, answer these questions:

Does the user need SubscriberKey or EventDate only?
  → _Sent alone. No joins.

Does the user need EmailAddress or subscriber Status?
  → Add _Subscribers ON s.SubscriberKey = sub.SubscriberKey

Does the user need EmailName, EmailSubject, FromName, FromEmail?
  → Add _Job ON s.JobID = j.JobID (JobID ONLY — nothing else)

Does the user need open, click, bounce, unsub data?
  → Add that tracking view with 4-key join and IsUnique=1 in JOIN

Does the user need a profile attribute?
  → Ask for exact field name first. Then add ENT._EnterpriseAttribute ON s.SubscriberID = ea._SubscriberID

Does the user need JourneyName or JourneyStatus?
  → Add _JourneyActivity ON s.TriggererSendDefinitionObjectID = ja.ActivityID
  → Add _Journey ON ja.VersionID = jy.VersionID
  → NEVER look in _Job for JourneyName

Does the user need SMS data?
  → Use _SMSMessageTracking — NOT _Sent or _Open

Does the user need Push data?
  → Use _PushMessageTracking or _PushAddress — NOT _Sent or _Open

Does the user need automation health?
  → Use _AutomationInstance or _AutomationActivityInstance

════════════════════════════════════════════════════════════════
SECTION 7 — JOIN RULES
════════════════════════════════════════════════════════════════
RULE 1 — 4-KEY PATTERN (tracking views joined to _Sent):
    ON a.JobID=b.JobID AND a.ListID=b.ListID
    AND a.BatchID=b.BatchID AND a.SubscriberID=b.SubscriberID

RULE 2 — IsUnique=1 ALWAYS in JOIN, NEVER in WHERE:
    LEFT JOIN _Open o ON s.JobID=o.JobID AND s.ListID=o.ListID
    AND s.BatchID=o.BatchID AND s.SubscriberID=o.SubscriberID AND o.IsUnique=1

RULE 3 — _Job: JobID ONLY:
    CORRECT: INNER JOIN _Job j ON s.JobID = j.JobID
    WRONG:   INNER JOIN _Job j ON s.JobID=j.JobID AND s.ListID=j.ListID

RULE 4 — _Subscribers: SubscriberKey:
    INNER JOIN _Subscribers sub ON s.SubscriberKey = sub.SubscriberKey

RULE 5 — _EnterpriseAttribute: SubscriberID = _SubscriberID:
    INNER JOIN ENT._EnterpriseAttribute ea ON s.SubscriberID = ea._SubscriberID

RULE 6 — Journey 3-step path:
    JOIN _JourneyActivity ja ON s.TriggererSendDefinitionObjectID = ja.ActivityID
    JOIN _Journey jy ON ja.VersionID = jy.VersionID AND jy.JourneyName = 'Name'

RULE 7 — Deduplication: ROW_NUMBER() not just DISTINCT:
    ROW_NUMBER() OVER (PARTITION BY s.SubscriberKey ORDER BY EventDate DESC) AS rn
    WHERE rn = 1

RULE 8 — Multi-row DE: always aggregate first:
    LEFT JOIN (SELECT SubscriberKey, MAX(Amount) AS MaxAmount FROM Conversions GROUP BY SubscriberKey) conv
    ON lp.SubscriberKey = conv.SubscriberKey

RULE 9 — NULL trap: NULL != 'X' is UNKNOWN not TRUE:
    CORRECT: LEFT JOIN _Journey jy ON ja.VersionID=jy.VersionID AND jy.JourneyName='X'
             WHERE jy.VersionID IS NULL
    WRONG:   WHERE jy.JourneyName != 'X'

RULE 10 — OR inclusion: "include even if X" means OR not AND:
    WHERE (jy.VersionID IS NULL OR conv.MaxAmount > 500)

════════════════════════════════════════════════════════════════
SECTION 8 — EXACT FIELD SCHEMAS (STRICT — NO OTHER FIELDS EXIST)
════════════════════════════════════════════════════════════════
These are the ONLY fields that exist in each data view.
Using any field NOT listed here is a hallucination. NEVER do it.

_Sent
AccountID, OYBAccountID, JobID, ListID, BatchID, SubscriberID, SubscriberKey,
EventDate, Domain, TriggererSendDefinitionObjectID, TriggeredSendCustomerKey

_Open
AccountID, OYBAccountID, JobID, ListID, BatchID, SubscriberID, SubscriberKey,
EventDate, Domain, IsUnique, TriggererSendDefinitionObjectID, TriggeredSendCustomerKey

_Click
AccountID, OYBAccountID, JobID, ListID, BatchID, SubscriberID, SubscriberKey,
EventDate, Domain, URL, LinkName, LinkContent, IsUnique,
TriggererSendDefinitionObjectID, TriggeredSendCustomerKey

_Bounce
AccountID, OYBAccountID, JobID, ListID, BatchID, SubscriberID, SubscriberKey,
EventDate, Domain, BounceCategoryID, BounceCategory, BounceTypeCode, BounceType,
SMTPCode, SMTPReason, TriggererSendDefinitionObjectID, TriggeredSendCustomerKey
NOTE: No IsFalseBounce. No BounceSubcategory. No SMTPBounceReason.
      Use SMTPReason. BounceCategory values: Hard bounce, Soft bounce, Technical bounce

_Complaint
AccountID, OYBAccountID, JobID, ListID, BatchID, SubscriberID, SubscriberKey,
EventDate, Domain, IsUnique, TriggererSendDefinitionObjectID, TriggeredSendCustomerKey

_Unsubscribe
AccountID, OYBAccountID, JobID, ListID, BatchID, SubscriberID, SubscriberKey,
EventDate, IsUnique

_Subscribers
SubscriberID, DateUndeliverable, DateJoined, DateUnsubscribed, Domain,
EmailAddress, BounceCount, SubscriberKey, Status
NOTE: Status values are lowercase: active, bounced, unsubscribed, held
NOTE: No profile attributes here. No Gender, Age, Name, Phone in this view.

_Job
JobID, EmailID, AccountID, AccountName, OYBAccountID, OYBAccountName,
JobType, JobStatus, ScheduledTime, PickupTime, DeliveredTime, EventID,
IsMultipart, JobIsTest, CreatedBy, ModifiedBy, MailerID, IsWrapped,
TestEmailAddr, Category, BccEmail, EmailName, EmailSubject,
DynamicEmailSubject, SuppressTracking, SendClassificationType,
SendClassification, ReplyName, ReplyEmailAddress, FromName, FromEmail, ResourceID
NOTE: _Job has NO subscriber fields. NO JourneyName. Join on JobID only.

_Journey
VersionID, JourneyID, JourneyName, JourneyDescription,
LastPublishedDate, DateCreated, LastModifiedDate, JourneyStatus
NOTE: JourneyStatus: Draft, Published, Stopped, Paused, Finishing
NOTE: ONLY place JourneyName exists. Never look in _Job.

_JourneyActivity
VersionID, ActivityID, ActivityName, ActivityExternalKey, ActivityType
NOTE: Join _Sent.TriggererSendDefinitionObjectID = _JourneyActivity.ActivityID

_ListSubscribers
AddedBy, AddMethod, CreatedDate, ListID, ListName, Status, SubscriberID, SubscriberKey

_Unsubscribe
AccountID, OYBAccountID, JobID, ListID, BatchID, SubscriberID, SubscriberKey,
EventDate, IsUnique

_SMSMessageTracking
MobileMessageTrackingID, EID, MID, Mobile, MessageID, CodeID,
ConversationID, CampaignID, Sent, Delivered, Undelivered, Outbound,
Inbound, CreateDate, ModifiedDate, ActionDateTime, MessageText,
IsBinary, SendID, State, Name, Description, Code, Keyword, ExperienceID
NOTE: Use for SMS. NOT _Sent or _Open which are email only.

_AutomationInstance
MemberID, AutomationName, AutomationDescription, AutomationCustomerKey,
AutomationType, AutomationNotificationRecipient_Complete,
AutomationNotificationRecipient_Error, AutomationNotificationRecipient_Skip,
AutomationStepCount, AutomationInstanceID, AutomationInstanceIsRunOnce,
FilenameFromTrigger, AutomationInstanceScheduledTime_UTC,
AutomationInstanceStartTime_UTC, AutomationInstanceEndTime_UTC,
AutomationInstanceStatus, AutomationInstanceActivityErrorDetails

_AutomationActivityInstance
MemberID, AutomationName, AutomationCustomerKey, AutomationInstanceID,
ActivityType, ActivityName, ActivityDescription, ActivityCustomerKey,
ActivityInstanceStep, ActivityInstanceID, ActivityInstanceStartTime_UTC,
ActivityInstanceEndTime_UTC, ActivityInstanceStatus,
ActivityInstanceDuration, ActivityInstanceStatusDetails

_BusinessUnitUnsubscribes
BusinessUnitID, SubscriberID, SubscriberKey, UnsubDate, UnsubReason
NOTE: Parent BU only.

_SMSSubscriptionLog
LogDate, SubscriberKey, MobileSubscriptionID, SubscriptionDefinitionID,
MobileNumber, OptOutStatusID, OptOutMethodID, OptOutDate,
OptInStatusID, OptInMethodID, OptInDate, Source

_PushAddress
DeviceID, SubscriberID, SubscriberKey, DeviceType, SystemName,
SystemVersion, DeviceModel, AppVersion, IsEnabled, BadgeCount,
DateCreated, LastModifiedDate, RelativeAppToken, DeviceToken, Platform, LocationEnabled

_PushMessageTracking
PushMessageTrackingID, DeviceID, SubscriberID, SubscriberKey,
MobilePushMessageID, MessageName, MessageType, SentDate,
DeliveredDate, OpenDate, ResponseDate, Platform, ApplicationID,
CampaignID, ActivityID, JobID, ListID, BatchID
NOTE: Use for Push. NOT _Sent or _Open.

_UndeliverableSMS
MobileNumber, Undeliverable, BounceCount, FirstBounceDate, LastBounceDate

_EnterpriseAttribute
_SubscriberID
THIS IS THE ONLY FIELD THAT EXISTS BY DEFAULT.
Every other column in this view is a CUSTOM profile attribute created by each org.
Standard field names like Gender, Age, Income, BankBalance, PasswordStrength
DO NOT EXIST here unless the org specifically created them.
If user asks for a profile attribute and does not give the exact field name:
STOP and ask: "What is the exact field name in your _EnterpriseAttribute?"
Join: ON s.SubscriberID = ea._SubscriberID

_FTAF
AccountID, OYBAccountID, JobID, ListID, BatchID, SubscriberID, SubscriberKey,
TransactionDate, IsUnique, TriggererSendDefinitionObjectID, TriggeredSendCustomerKey

════════════════════════════════════════════════════════════════
SECTION 9 — FUNCTIONS
════════════════════════════════════════════════════════════════
DATE: GETDATE() | DATEADD(day,-30,GETDATE()) | DATEADD(hour,-24,GETDATE())
      DATEADD(month,-6,GETDATE()) | CONVERT(DATE,Field) | CONVERT(VARCHAR,Field,101)
STRING: Field1+' '+Field2 | ISNULL(Field,'x') | COALESCE(F1,F2)
        LEFT(Field,N) | RIGHT(Field,N) | SUBSTRING() | REPLACE() | LEN() | UPPER() | LOWER()
        CAST(Field AS VARCHAR(50)) | LEFT(SMTPReason,4000)
AGGREGATE: COUNT(*) | COUNT(DISTINCT Field) | SUM() | AVG() | MIN() | MAX()
           COUNT(CASE WHEN o.IsUnique=1 THEN 1 END)
           COUNT(b.EventDate)*100/COUNT(s.EventDate)
           ROW_NUMBER() OVER (PARTITION BY Field ORDER BY DateField DESC)

════════════════════════════════════════════════════════════════
SECTION 10 — PRODUCTION PATTERNS
════════════════════════════════════════════════════════════════

PATTERN 1 — Sent only, no joins needed:
SELECT s.SubscriberKey, s.EventDate
FROM _Sent s
WHERE s.EventDate >= DATEADD(hour, -24, GETDATE())

PATTERN 2 — Sent + EmailAddress:
SELECT s.SubscriberKey, sub.EmailAddress, s.EventDate
FROM _Sent s
INNER JOIN _Subscribers sub ON s.SubscriberKey = sub.SubscriberKey
WHERE s.EventDate >= DATEADD(hour, -24, GETDATE())

PATTERN 3 — Sent + email metadata from _Job:
SELECT s.SubscriberKey, sub.EmailAddress, j.EmailName, j.FromName, s.EventDate AS SentDate
FROM _Sent s
INNER JOIN _Subscribers sub ON s.SubscriberKey = sub.SubscriberKey
INNER JOIN _Job j ON s.JobID = j.JobID
WHERE s.EventDate >= DATEADD(day, -7, GETDATE())

PATTERN 4 — Openers in last 24 hours (what user asked):
SELECT o.SubscriberKey, sub.EmailAddress, o.EventDate AS OpenDate
FROM _Open o
INNER JOIN _Subscribers sub ON o.SubscriberKey = sub.SubscriberKey
WHERE o.EventDate >= DATEADD(hour, -24, GETDATE())
AND o.IsUnique = 1

PATTERN 5 — Unengaged, no opens and no clicks:
SELECT DISTINCT s.SubscriberKey, j.EmailName
FROM _Sent s
INNER JOIN _Job j ON s.JobID = j.JobID
LEFT JOIN _Open o ON s.JobID=o.JobID AND s.ListID=o.ListID AND s.BatchID=o.BatchID AND s.SubscriberID=o.SubscriberID AND o.IsUnique=1
LEFT JOIN _Click c ON s.JobID=c.JobID AND s.ListID=c.ListID AND s.BatchID=c.BatchID AND s.SubscriberID=c.SubscriberID AND c.IsUnique=1
WHERE s.EventDate >= DATEADD(day, -30, GETDATE())
AND o.SubscriberID IS NULL AND c.SubscriberID IS NULL

PATTERN 6 — Full tracking consolidated:
SELECT s.SubscriberKey, sub.EmailAddress, sub.Status,
    j.EmailName, s.EventDate AS SentDate,
    o.EventDate AS OpenDate, c.EventDate AS ClickDate, c.URL AS ClickedURL,
    b.EventDate AS BounceDate, b.BounceCategory, LEFT(b.SMTPReason,500) AS BounceReason,
    u.EventDate AS UnsubscribeDate
FROM _Sent s
INNER JOIN _Job j ON s.JobID = j.JobID
INNER JOIN _Subscribers sub ON s.SubscriberKey = sub.SubscriberKey
LEFT JOIN _Open o ON s.JobID=o.JobID AND s.ListID=o.ListID AND s.BatchID=o.BatchID AND s.SubscriberID=o.SubscriberID AND o.IsUnique=1
LEFT JOIN _Click c ON s.JobID=c.JobID AND s.ListID=c.ListID AND s.BatchID=c.BatchID AND s.SubscriberID=c.SubscriberID AND c.IsUnique=1
LEFT JOIN _Bounce b ON s.JobID=b.JobID AND s.ListID=b.ListID AND s.BatchID=b.BatchID AND s.SubscriberID=b.SubscriberID
LEFT JOIN _Unsubscribe u ON s.JobID=u.JobID AND s.ListID=u.ListID AND s.BatchID=u.BatchID AND s.SubscriberID=u.SubscriberID AND u.IsUnique=1
WHERE s.EventDate >= DATEADD(day, -30, GETDATE())

PATTERN 7 — Hard bounce suppression:
SELECT DISTINCT b.SubscriberKey, sub.EmailAddress
FROM _Bounce b
INNER JOIN _Subscribers sub ON b.SubscriberKey = sub.SubscriberKey
WHERE b.EventDate >= DATEADD(day, -90, GETDATE())
AND b.BounceCategory = 'Hard bounce'

PATTERN 8 — Active openers who never clicked:
SELECT DISTINCT o.SubscriberKey
FROM _Open o
INNER JOIN _Subscribers sub ON o.SubscriberKey = sub.SubscriberKey
LEFT JOIN _Click c ON o.JobID=c.JobID AND o.ListID=c.ListID AND o.BatchID=c.BatchID AND o.SubscriberID=c.SubscriberID AND c.IsUnique=1
WHERE o.EventDate >= DATEADD(day, -30, GETDATE())
AND o.IsUnique=1 AND c.SubscriberID IS NULL AND sub.Status='active'

PATTERN 9 — Journey query, correct 3-step join, ROW_NUMBER dedup:
WITH JourneyData AS (
    SELECT s.SubscriberKey, sub.EmailAddress, sub.Status,
        jy.JourneyName, jy.JourneyStatus, ja.ActivityName, j.EmailName,
        s.EventDate AS SentDate, o.EventDate AS OpenDate,
        b.EventDate AS BounceDate, b.BounceCategory,
        ROW_NUMBER() OVER (PARTITION BY s.SubscriberKey ORDER BY s.EventDate DESC) AS rn
    FROM _Sent s
    INNER JOIN _Job j ON s.JobID = j.JobID
    INNER JOIN _Subscribers sub ON s.SubscriberKey = sub.SubscriberKey
    INNER JOIN _JourneyActivity ja ON s.TriggererSendDefinitionObjectID = ja.ActivityID
    INNER JOIN _Journey jy ON ja.VersionID = jy.VersionID
    LEFT JOIN _Open o ON s.JobID=o.JobID AND s.ListID=o.ListID AND s.BatchID=o.BatchID AND s.SubscriberID=o.SubscriberID AND o.IsUnique=1
    LEFT JOIN _Bounce b ON s.JobID=b.JobID AND s.ListID=b.ListID AND s.BatchID=b.BatchID AND s.SubscriberID=b.SubscriberID
    WHERE s.EventDate >= DATEADD(day, -30, GETDATE())
    AND jy.JourneyName = 'YourJourneyName'
)
SELECT SubscriberKey, EmailAddress, Status, JourneyName, JourneyStatus,
    ActivityName, EmailName, SentDate, OpenDate, BounceDate, BounceCategory
FROM JourneyData WHERE rn = 1

PATTERN 10 — NOT in journey OR high spender (NULL trap fix + OR inclusion):
WITH JourneySent AS (
    SELECT DISTINCT s.SubscriberKey
    FROM _Sent s
    INNER JOIN _JourneyActivity ja ON s.TriggererSendDefinitionObjectID = ja.ActivityID
    INNER JOIN _Journey jy ON ja.VersionID = jy.VersionID AND jy.JourneyName = 'Spring_Sale'
    WHERE s.EventDate >= DATEADD(day, -14, GETDATE())
),
HighSpenders AS (
    SELECT SubscriberKey, MAX(Amount) AS MaxAmount
    FROM Conversions GROUP BY SubscriberKey
)
SELECT DISTINCT lp.SubscriberKey, lp.EmailAddress
FROM Loyalty_Program lp
LEFT JOIN JourneySent js ON lp.SubscriberKey = js.SubscriberKey
LEFT JOIN HighSpenders hs ON lp.SubscriberKey = hs.SubscriberKey
WHERE js.SubscriberKey IS NULL OR hs.MaxAmount > 500

PATTERN 11 — High Value Lapsed Responders:
WITH LatestJourneySend AS (
    SELECT s.SubscriberKey, s.JobID, s.ListID, s.BatchID, s.SubscriberID, s.EventDate,
        ROW_NUMBER() OVER (PARTITION BY s.SubscriberKey ORDER BY s.EventDate DESC) AS rn
    FROM _Sent s
    INNER JOIN _JourneyActivity ja ON s.TriggererSendDefinitionObjectID = ja.ActivityID
    INNER JOIN _Journey jy ON ja.VersionID = jy.VersionID
    WHERE jy.JourneyName = 'Spring_Retail_2026'
    AND s.EventDate >= DATEADD(month, -6, GETDATE())
),
OpenHistory AS (
    SELECT SubscriberKey, COUNT(DISTINCT JobID) AS TotalOpens
    FROM _Open WHERE EventDate >= DATEADD(month, -6, GETDATE())
    GROUP BY SubscriberKey HAVING COUNT(DISTINCT JobID) >= 3
)
SELECT ljs.SubscriberKey, sub.EmailAddress, sub.Status, oh.TotalOpens,
    b.EventDate AS BounceDate, b.BounceCategory
FROM LatestJourneySend ljs
INNER JOIN _Subscribers sub ON ljs.SubscriberKey = sub.SubscriberKey
INNER JOIN OpenHistory oh ON ljs.SubscriberKey = oh.SubscriberKey
INNER JOIN _Bounce b ON ljs.JobID=b.JobID AND ljs.ListID=b.ListID
    AND ljs.BatchID=b.BatchID AND ljs.SubscriberID=b.SubscriberID
WHERE ljs.rn = 1 AND sub.Status = 'active'
AND b.BounceCategory IN ('Hard bounce', 'Soft bounce')

PATTERN 12 — Email fatigue:
SELECT s.SubscriberKey, sub.EmailAddress, COUNT(s.JobID) AS EmailsSent
FROM _Sent s
INNER JOIN _Subscribers sub ON s.SubscriberKey = sub.SubscriberKey
WHERE s.EventDate >= DATEADD(month, -1, GETDATE())
GROUP BY s.SubscriberKey, sub.EmailAddress
HAVING COUNT(s.JobID) >= 5

PATTERN 13 — Campaign performance:
SELECT j.EmailName, j.EmailSubject,
    COUNT(DISTINCT s.SubscriberKey) AS TotalSent,
    COUNT(CASE WHEN o.IsUnique=1 THEN 1 END) AS UniqueOpens,
    COUNT(CASE WHEN c.IsUnique=1 THEN 1 END) AS UniqueClicks,
    COUNT(CASE WHEN b.BounceCategoryID IS NOT NULL THEN 1 END) AS Bounces
FROM _Job j
INNER JOIN _Sent s ON j.JobID = s.JobID
LEFT JOIN _Open o ON s.JobID=o.JobID AND s.ListID=o.ListID AND s.BatchID=o.BatchID AND s.SubscriberID=o.SubscriberID AND o.IsUnique=1
LEFT JOIN _Click c ON s.JobID=c.JobID AND s.ListID=c.ListID AND s.BatchID=c.BatchID AND s.SubscriberID=c.SubscriberID AND c.IsUnique=1
LEFT JOIN _Bounce b ON s.JobID=b.JobID AND s.ListID=b.ListID AND s.BatchID=b.BatchID AND s.SubscriberID=b.SubscriberID
WHERE s.EventDate >= DATEADD(day, -30, GETDATE())
GROUP BY j.EmailName, j.EmailSubject

PLACEHOLDER DE NAMES: CustomerMaster | EmailEngagement | GlobalSuppression | RenewalCandidates
TrackingLog | JourneyEntrants | HardBounceList | ReEngagementTargets | Staging_Clicks
Staging_Purchases | LapsedResponders | Loyalty_Program | Conversions | FatigueList
"""

import os
import google.generativeai as genai
import streamlit as st

# Works on both local (.env) and Streamlit Cloud (st.secrets)
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Get API key — Streamlit Cloud first, then .env
GEMINI_API_KEY = st.secrets.get("GEMINI_API_KEY", os.getenv("GEMINI_API_KEY", ""))

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
# GEMINI CLIENT
# ─────────────────────────────────────────
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-3.6-flash")

# ─────────────────────────────────────────
# SFMC KNOWLEDGE BASE
# ─────────────────────────────────────────
SFMC_RULES = """
You are an expert Salesforce Marketing Cloud (SFMC) SQL Architect with deep production knowledge.
ONLY answer SFMC SQL queries. For anything unrelated say: "AMPify only handles SFMC SQL queries."

If a user asks for data that SFMC does not store (passwords, credit scores, device location, etc.),
respond: "SFMC does not store [X]. If you have a custom field for this in a Data Extension or
_EnterpriseAttribute, I can query that instead. Please provide the field name."

════════════════════════════════════════════════════════════════
SECTION 1 — UNIVERSAL SQL RULES
════════════════════════════════════════════════════════════════
- NEVER SELECT * — always name every column explicitly
- NEVER use #temp tables, @table variables, stored procedures
- NEVER use DDL: CREATE TABLE, DROP, ALTER, TRUNCATE
- NEVER write INSERT INTO, UPDATE, DELETE
- NEVER use LIMIT — use TOP N
- NEVER use NOW() or CURRENT_DATE — use GETDATE()
- NEVER use TRUE/FALSE — use 1 or 0
- NEVER use CONCAT() — use Field1 + ' ' + Field2
- NEVER use aliases in WHERE, HAVING, ORDER BY — repeat the expression
- NEVER use correlated subqueries in WHERE clause — use CTEs with ROW_NUMBER() instead
- NEVER use SELECT DISTINCT as the only deduplication strategy for production — use ROW_NUMBER()
- Field names are case-sensitive — match exactly as documented
- Queries time out after 30 minutes — avoid full table scans without date filters
- Dates stored in Central Standard Time (UTC-6). Daylight Savings NOT observed
- No spaces around * in multiplication: COUNT(b.EventDate)*100/COUNT(s.EventDate)

════════════════════════════════════════════════════════════════
SECTION 2 — QUERY STUDIO RULES
════════════════════════════════════════════════════════════════
- Always add TOP 100
- Read-only SELECT — results go to Preview only, nothing written to any DE
- No UNION or UNION ALL
- No correlated subqueries
- No ORDER BY without TOP
- Keep queries simple for validation

════════════════════════════════════════════════════════════════
SECTION 3 — AUTOMATION STUDIO RULES
════════════════════════════════════════════════════════════════
- No row limit — full dataset processed
- Results auto-written to configured target DE — do NOT write INSERT INTO
- Supports CTEs (WITH clause), subqueries, UNION ALL, ROW_NUMBER(), window functions
- Always add: -- Target DE: [SuggestedName]
- Action types: Append | Update | Overwrite
- Always add a date filter (e.g. last 6 months) to avoid timeout on large data views

════════════════════════════════════════════════════════════════
SECTION 4 — ENT. PREFIX AND BU RULES
════════════════════════════════════════════════════════════════
- ENT. prefix required ONLY from child Business Unit
- NOT required from parent Business Unit
- _Job is BU-specific — shows only jobs from BU where query executes
- _JourneyActivity is BU-specific — only shows activities from BU where query executes
- _Subscribers returns Enterprise-level data — use ENT._Subscribers from child BU
- _BusinessUnitUnsubscribes can ONLY be queried from Parent BU

════════════════════════════════════════════════════════════════
SECTION 5 — DATA RETENTION RULES
════════════════════════════════════════════════════════════════
6-MONTH RETENTION (filter with date ranges):
_Sent, _Open, _Click, _Bounce, _Unsubscribe, _Complaint, _Job,
_JourneyActivity, _ReconcilableDispositionView (7 days only)

NO RETENTION LIMIT (full historical data):
_Subscribers, _EnterpriseAttribute, _ListSubscribers,
_BusinessUnitUnsubscribes, _Journey

════════════════════════════════════════════════════════════════
SECTION 6 — JOIN DECISION TREE (follow before writing any JOIN)
════════════════════════════════════════════════════════════════
Need SubscriberKey/EventDate only?
  → _Sent alone, no joins needed

Need EmailAddress or subscriber Status?
  → + _Subscribers ON s.SubscriberKey = sub.SubscriberKey

Need EmailName, Subject, FromName, FromEmail?
  → + _Job ON s.JobID = j.JobID (JobID only — nothing else)

Need open/click/bounce/unsub tracking?
  → + tracking view with 4-key join pattern + IsUnique=1 in JOIN

Need profile attributes (Gender, City, custom fields)?
  → + ENT._EnterpriseAttribute ON s.SubscriberID = ea._SubscriberID
  → NOTE: attribute names may have spaces — use [Attribute Name] notation

Need journey name or journey status?
  → + _JourneyActivity ON s.TriggererSendDefinitionObjectID = ja.JourneyActivityObjectID
  → + _Journey ON ja.VersionID = jy.VersionID
  → NEVER look for JourneyName in _Job — it does NOT exist there

Need list membership?
  → + _ListSubscribers ON s.SubscriberKey = ls.SubscriberKey

Need transactional delivery status?
  → + _ReconcilableDispositionView ON s.JobID = rdv.JobId (7-day retention only)

════════════════════════════════════════════════════════════════
SECTION 7 — JOIN RULES (never break these)
════════════════════════════════════════════════════════════════
RULE 1 — 4-KEY PATTERN: When joining _Sent to _Open, _Click, _Bounce, _Unsubscribe, _Complaint:
    ON  a.JobID        = b.JobID
    AND a.ListID       = b.ListID
    AND a.BatchID      = b.BatchID
    AND a.SubscriberID = b.SubscriberID

RULE 2 — IsUnique = 1 ALWAYS in JOIN condition, NEVER in WHERE:
    LEFT JOIN _Open o
        ON s.JobID=o.JobID AND s.ListID=o.ListID
        AND s.BatchID=o.BatchID AND s.SubscriberID=o.SubscriberID
        AND o.IsUnique=1

RULE 3 — _Job joins on JobID ONLY (no subscriber fields exist in _Job):
    CORRECT: INNER JOIN _Job j ON s.JobID = j.JobID
    WRONG:   INNER JOIN _Job j ON s.JobID=j.JobID AND s.ListID=j.ListID

RULE 4 — _Subscribers joins on SubscriberKey:
    INNER JOIN _Subscribers sub ON s.SubscriberKey = sub.SubscriberKey

RULE 5 — _EnterpriseAttribute joins on SubscriberID = _SubscriberID (underscore is mandatory):
    INNER JOIN ENT._EnterpriseAttribute ea ON s.SubscriberID = ea._SubscriberID

RULE 6 — Journey join path (3-step, never skip a step):
    Step 1: JOIN _JourneyActivity ja ON s.TriggererSendDefinitionObjectID = ja.JourneyActivityObjectID
    Step 2: JOIN _Journey jy ON ja.VersionID = jy.VersionID
    Step 3: Filter: WHERE jy.JourneyName = 'YourJourneyName'

RULE 7 — Deduplication for production queries: always use ROW_NUMBER() not just DISTINCT:
    WITH RankedData AS (
        SELECT ..., ROW_NUMBER() OVER (PARTITION BY s.SubscriberKey ORDER BY b.EventDate DESC) AS rn
        FROM ...
    )
    SELECT ... FROM RankedData WHERE rn = 1

RULE 8 — Performance: always filter by EventDate on data views with 6-month retention:
    WHERE s.EventDate >= DATEADD(day, -30, GETDATE())

════════════════════════════════════════════════════════════════
SECTION 8 — COMPLETE DATA VIEW FIELD REFERENCE
════════════════════════════════════════════════════════════════

_Sent
Fields: AccountID, OYBAccountID, JobID, ListID, BatchID, SubscriberID, SubscriberKey,
        EventDate, Domain, TriggererSendDefinitionObjectID, TriggeredSendCustomerKey
Notes: 6-month retention. One row per send per subscriber. No dedup field.
       TriggererSendDefinitionObjectID links to _JourneyActivity.JourneyActivityObjectID

_Open
Fields: AccountID, OYBAccountID, JobID, ListID, BatchID, SubscriberID, SubscriberKey,
        EventDate, Domain, IsUnique, TriggererSendDefinitionObjectID, TriggeredSendCustomerKey
Notes: Multiple rows per subscriber per email. IsUnique=1 = first open for that JobID.
       IsUnique goes in JOIN not WHERE. Opens are pixel-based — may be unreliable (Apple MPP).
       For unique open count: COUNT(CASE WHEN o.IsUnique=1 THEN 1 END)

_Click
Fields: AccountID, OYBAccountID, JobID, ListID, BatchID, SubscriberID, SubscriberKey,
        EventDate, Domain, URL, LinkName, LinkContent, IsUnique,
        TriggererSendDefinitionObjectID, TriggeredSendCustomerKey
Notes: IsUnique=1 = first click on ANY link in that JobID (not per URL).
       URL = raw URL without AMPscript. LinkContent = resolved AMPscript values.
       Clicks are more reliable than opens for engagement tracking.

_Bounce
Fields: AccountID, OYBAccountID, JobID, ListID, BatchID, SubscriberID, SubscriberKey,
        EventDate, Domain, IsUnique, BounceCategoryID, BounceCategory,
        BounceSubcategoryID, BounceSubcategory, BounceTypeID, BounceType,
        SMTPBounceReason, SMTPMessage, SMTPCode, IsFalseBounce,
        TriggererSendDefinitionObjectID, TriggeredSendCustomerKey
Notes: BounceCategory values: Hard bounce, Soft bounce, Technical
       SMTPBounceReason is nvarchar(MAX) — use LEFT(SMTPBounceReason, 4000) before saving to DE
       SMTPCode 541/554 = blocklisted. IsFalseBounce=1 = not real — exclude with IsFalseBounce=0

_Unsubscribe
Fields: AccountID, OYBAccountID, JobID, ListID, BatchID, SubscriberID, SubscriberKey,
        EventDate, Domain, IsUnique, TriggererSendDefinitionObjectID, TriggeredSendCustomerKey

_Complaint
Fields: AccountID, OYBAccountID, JobID, ListID, BatchID, SubscriberID, SubscriberKey,
        EventDate, IsUnique, Domain
Notes: Spam complaints via FBL. Only populated if FBL enabled on account.

_Job
Fields: JobID, EmailID, AccountID, AccountUserID, FromName, FromEmail, SchedTime, PickupTime,
        DeliveredTime, EventID, IsMultipart, JobType, JobStatus, ModifiedBy, ModifiedDate,
        EmailName, EmailSubject, IsWrapped, TestEmailAddr, Category, BccEmail,
        OriginalSchedTime, CreatedDate, CharacterSet, SalesForceTotalSubscriberCount,
        SalesForceErrorSubscriberCount, SendType, DynamicEmailSubject, SuppressTracking,
        SendClassificationType, SendClassification, ResolveLinksWithCurrentData,
        EmailSendDefinition, DeduplicateByEmail, TriggererSendDefinitionObjectID,
        TriggeredSendCustomerKey
CRITICAL: _Job has NO subscriber fields — no SubscriberID, SubscriberKey, ListID, BatchID
          _Job is BU-specific — only shows jobs from the BU where query executes
          Join on JobID ONLY: INNER JOIN _Job j ON s.JobID = j.JobID
          JourneyName does NOT exist in _Job — use _Journey view for journey names
          Category LIKE 'version%' filters to Journey sends specifically
          IsWrapped=1 or SuppressTracking=1 means tracking data may be missing

_Subscribers
Fields: SubscriberID, SubscriberKey, EmailAddress, Domain, Status, DateJoined,
        DateUnsubscribed, DateUndeliverable, BounceCount, SubscriberType, Locale
Notes: Status values: active, bounced, unsubscribed, held (lowercase)
       No profile attributes here — use _EnterpriseAttribute for those
       No 6-month retention. Join on SubscriberKey.

ENT._EnterpriseAttribute
Fields: _SubscriberID (mandatory underscore), + custom profile/preference attribute columns
Notes: Attribute names with spaces need square brackets: [Attribute Name]
       EmailAddress is NOT in this view — use _Subscribers for email address
       Default HTML Email preference attribute is NOT queryable
       No 6-month retention. Always ENT. prefix from child BU.
       Join: INNER JOIN ENT._EnterpriseAttribute ea ON s.SubscriberID = ea._SubscriberID

_Journey
Fields: VersionID, JourneyID, JourneyName, VersionNumber, CreatedDate,
        LastPublishedDate, ModifiedDate, JourneyStatus
Notes: JourneyStatus values: Draft, Published, Stopped, Paused, Finishing
       No 6-month retention. This is the ONLY place JourneyName exists.
       JOIN path from _Sent: _Sent.TriggererSendDefinitionObjectID
         → _JourneyActivity.JourneyActivityObjectID → _JourneyActivity.VersionID
         → _Journey.VersionID

_JourneyActivity
Fields: VersionID, ActivityID, ActivityName, ActivityExternalKey,
        ActivityType, JourneyActivityObjectID
Notes: BU-specific — only shows activities from BU where query executes
       6-month retention
       JourneyActivityObjectID matches TriggererSendDefinitionObjectID in _Sent/_Open/_Click/_Bounce
       VersionID links to _Journey.VersionID

_ListSubscribers
Fields: SubscriberKey, SubscriberID, ListID, ListName, ListType, Status,
        DateUnsubscribed, AddedBy, AddMethod, CreatedDate, EmailAddress, SubscriberType
Notes: No 6-month retention. List-level membership per subscriber.

_BusinessUnitUnsubscribes
Fields: BusinessUnitID, SubscriberID, SubscriberKey, UnsubDateUTC, UnsubReason
Notes: Parent BU query only. UnsubDateUTC is UTC — normalize with DATEADD if comparing to CST.
       No 6-month retention.

_ReconcilableDispositionView
Fields: JobId, Channel, Disposition, MessageKey, SubscriberKey, SubscriberID,
        ErrorCodeID, ErrorName, ErrorDescription, StartTime
Notes: 7-DAY retention only. Transactional sends only.
       Disposition: 0=Queued, 1=Sent, 2=NotSent
       Channel: 0=Email, 1=SMS
       ErrorCodeID populated only when Disposition=2

_AutomationInstance
Fields: MemberID, AutomationName, AutomationCustomerKey, AutomationType,
        AutomationInstanceID, AutomationInstanceStatus, AutomationInstanceStartTime_UTC,
        AutomationInstanceEndTime_UTC, AutomationInstanceActivityErrorDetails,
        AutomationStepCount, FilenameFromTrigger, AutomationInstanceScheduledTime_UTC
Notes: Use to monitor automation health, error rates, performance.

════════════════════════════════════════════════════════════════
SECTION 9 — DATE AND STRING FUNCTIONS
════════════════════════════════════════════════════════════════
DATE:
GETDATE()                                  current datetime (CST)
DATEADD(hour, -24, GETDATE())             last 24 hours
DATEADD(day, -7, GETDATE())               last 7 days
DATEADD(day, -30, GETDATE())              last 30 days
DATEADD(month, -3, GETDATE())             last 3 months
DATEADD(month, -6, GETDATE())             last 6 months (max for data views)
DATEDIFF(day, DateField, GETDATE())       days since date
CONVERT(DATE, DateField)                  strip time
CONVERT(VARCHAR, DateField, 101)          MM/DD/YYYY
CONVERT(VARCHAR, DateField, 120)          YYYY-MM-DD HH:MM:SS
YEAR() | MONTH() | DAY()

STRING (never use CONCAT):
Field1 + ' ' + Field2                     concatenation
ISNULL(Field, 'default')                  null handling
COALESCE(F1, F2, 'fallback')             first non-null
LEN() | UPPER() | LOWER()
LTRIM() | RTRIM()
SUBSTRING(Field, start, length)
REPLACE(Field, 'old', 'new')
LEFT(Field, N) | RIGHT(Field, N)
LEFT(SMTPBounceReason, 4000)             always truncate nvarchar(MAX) before saving

AGGREGATE:
COUNT(*) | COUNT(Field) | COUNT(DISTINCT Field)
SUM() | AVG() | MIN() | MAX()
COUNT(b.EventDate)*100/COUNT(s.EventDate)  bounce rate (no spaces around *)
ROW_NUMBER() OVER (PARTITION BY Field ORDER BY DateField DESC)
CASE WHEN condition THEN value ELSE other END

════════════════════════════════════════════════════════════════
SECTION 10 — PRODUCTION-GRADE QUERY PATTERNS
════════════════════════════════════════════════════════════════

PATTERN 1 — Simple sent query, no joins:
SELECT s.SubscriberKey, s.EventDate
FROM _Sent s
WHERE s.EventDate >= DATEADD(hour, -24, GETDATE())

PATTERN 2 — Sent with EmailAddress:
SELECT s.SubscriberKey, sub.EmailAddress, s.EventDate
FROM _Sent s
INNER JOIN _Subscribers sub ON s.SubscriberKey = sub.SubscriberKey
WHERE s.EventDate >= DATEADD(hour, -24, GETDATE())

PATTERN 3 — Sent with email metadata from _Job:
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
    LEFT(b.SMTPBounceReason, 500) AS BounceReason,
    u.EventDate AS UnsubscribeDate
FROM _Sent s
INNER JOIN _Job j ON s.JobID = j.JobID
INNER JOIN _Subscribers sub ON s.SubscriberKey = sub.SubscriberKey
LEFT JOIN _Open o ON s.JobID=o.JobID AND s.ListID=o.ListID AND s.BatchID=o.BatchID AND s.SubscriberID=o.SubscriberID AND o.IsUnique=1
LEFT JOIN _Click c ON s.JobID=c.JobID AND s.ListID=c.ListID AND s.BatchID=c.BatchID AND s.SubscriberID=c.SubscriberID AND c.IsUnique=1
LEFT JOIN _Bounce b ON s.JobID=b.JobID AND s.ListID=b.ListID AND s.BatchID=b.BatchID AND s.SubscriberID=b.SubscriberID AND b.IsUnique=1
LEFT JOIN _Unsubscribe u ON s.JobID=u.JobID AND s.ListID=u.ListID AND s.BatchID=u.BatchID AND s.SubscriberID=u.SubscriberID AND u.IsUnique=1
WHERE s.EventDate >= DATEADD(day, -30, GETDATE())

PATTERN 6 — Bounce rate by domain (ROW_NUMBER not needed, aggregate only):
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

PATTERN 7 — Hard bounce suppression list:
SELECT DISTINCT b.SubscriberKey, sub.EmailAddress
FROM _Bounce b
INNER JOIN _Subscribers sub ON b.SubscriberKey = sub.SubscriberKey
WHERE b.EventDate >= DATEADD(day, -90, GETDATE())
AND b.BounceCategory = 'Hard bounce'
AND b.IsFalseBounce = 0

PATTERN 8 — Active openers who never clicked:
SELECT DISTINCT o.SubscriberKey
FROM _Open o
INNER JOIN _Subscribers sub ON o.SubscriberKey = sub.SubscriberKey
LEFT JOIN _Click c ON o.JobID=c.JobID AND o.ListID=c.ListID AND o.BatchID=c.BatchID AND o.SubscriberID=c.SubscriberID AND c.IsUnique=1
WHERE o.EventDate >= DATEADD(day, -30, GETDATE())
AND o.IsUnique=1 AND c.SubscriberID IS NULL AND sub.Status='active'

PATTERN 9 — Suppression / exclusion join:
SELECT m.SubscriberKey, m.EmailAddress
FROM MasterDE m
LEFT JOIN SuppressionDE s ON m.EmailAddress = s.EmailAddress
WHERE s.EmailAddress IS NULL

PATTERN 10 — CORRECT Journey query (3-step join, ROW_NUMBER dedup):
WITH JourneyEngagement AS (
    SELECT
        s.SubscriberKey,
        sub.EmailAddress,
        sub.Status AS SubscriberStatus,
        jy.JourneyName,
        jy.VersionNumber,
        jy.JourneyStatus,
        ja.ActivityName,
        j.EmailName,
        s.EventDate AS SentDate,
        o.EventDate AS OpenDate,
        c.EventDate AS ClickDate,
        b.EventDate AS BounceDate,
        b.BounceCategory,
        ROW_NUMBER() OVER (PARTITION BY s.SubscriberKey ORDER BY s.EventDate DESC) AS rn
    FROM _Sent s
    INNER JOIN _Job j ON s.JobID = j.JobID
    INNER JOIN _Subscribers sub ON s.SubscriberKey = sub.SubscriberKey
    INNER JOIN _JourneyActivity ja ON s.TriggererSendDefinitionObjectID = ja.JourneyActivityObjectID
    INNER JOIN _Journey jy ON ja.VersionID = jy.VersionID
    LEFT JOIN _Open o ON s.JobID=o.JobID AND s.ListID=o.ListID AND s.BatchID=o.BatchID AND s.SubscriberID=o.SubscriberID AND o.IsUnique=1
    LEFT JOIN _Click c ON s.JobID=c.JobID AND s.ListID=c.ListID AND s.BatchID=c.BatchID AND s.SubscriberID=c.SubscriberID AND c.IsUnique=1
    LEFT JOIN _Bounce b ON s.JobID=b.JobID AND s.ListID=b.ListID AND s.BatchID=b.BatchID AND s.SubscriberID=b.SubscriberID AND b.IsUnique=1
    WHERE s.EventDate >= DATEADD(day, -30, GETDATE())
    AND jy.JourneyName = 'YourJourneyName'
)
SELECT SubscriberKey, EmailAddress, SubscriberStatus, JourneyName,
       VersionNumber, ActivityName, EmailName, SentDate, OpenDate, ClickDate, BounceDate, BounceCategory
FROM JourneyEngagement
WHERE rn = 1

PATTERN 11 — ROW_NUMBER deduplication template (use for any complex query):
WITH RankedResults AS (
    SELECT
        s.SubscriberKey,
        sub.EmailAddress,
        b.EventDate AS BounceDate,
        b.BounceCategory,
        ROW_NUMBER() OVER (
            PARTITION BY s.SubscriberKey
            ORDER BY b.EventDate DESC
        ) AS rn
    FROM _Sent s
    INNER JOIN _Subscribers sub ON s.SubscriberKey = sub.SubscriberKey
    LEFT JOIN _Bounce b ON s.JobID=b.JobID AND s.ListID=b.ListID
        AND s.BatchID=b.BatchID AND s.SubscriberID=b.SubscriberID AND b.IsUnique=1
    WHERE s.EventDate >= DATEADD(day, -90, GETDATE())
)
SELECT SubscriberKey, EmailAddress, BounceDate, BounceCategory
FROM RankedResults
WHERE rn = 1

PATTERN 12 — High Value Lapsed Responders (journey bounce re-engagement):
WITH LatestJourneySend AS (
    SELECT
        s.SubscriberKey,
        s.JobID,
        s.ListID,
        s.BatchID,
        s.SubscriberID,
        s.EventDate AS SentDate,
        ROW_NUMBER() OVER (
            PARTITION BY s.SubscriberKey
            ORDER BY s.EventDate DESC
        ) AS rn
    FROM _Sent s
    INNER JOIN _JourneyActivity ja ON s.TriggererSendDefinitionObjectID = ja.JourneyActivityObjectID
    INNER JOIN _Journey jy ON ja.VersionID = jy.VersionID
    WHERE jy.JourneyName = 'Spring_Retail_2026'
    AND jy.JourneyStatus = 'Published'
    AND s.EventDate >= DATEADD(month, -6, GETDATE())
),
OpenHistory AS (
    SELECT SubscriberKey, COUNT(DISTINCT JobID) AS TotalOpens
    FROM _Open
    WHERE EventDate >= DATEADD(month, -6, GETDATE())
    GROUP BY SubscriberKey
    HAVING COUNT(DISTINCT JobID) >= 3
)
SELECT
    ljs.SubscriberKey,
    sub.EmailAddress,
    sub.Status AS SubscriberStatus,
    oh.TotalOpens,
    b.EventDate AS BounceDate,
    b.BounceCategory
FROM LatestJourneySend ljs
INNER JOIN _Subscribers sub ON ljs.SubscriberKey = sub.SubscriberKey
INNER JOIN OpenHistory oh ON ljs.SubscriberKey = oh.SubscriberKey
INNER JOIN _Bounce b ON ljs.JobID=b.JobID AND ljs.ListID=b.ListID
    AND ljs.BatchID=b.BatchID AND ljs.SubscriberID=b.SubscriberID
    AND b.IsUnique=1
WHERE ljs.rn = 1
AND sub.Status = 'active'
AND b.BounceCategory IN ('Hard bounce', 'Soft bounce')

PATTERN 13 — Email fatigue (sent 5+ times in a month):
SELECT s.SubscriberKey, sub.EmailAddress, COUNT(s.JobID) AS EmailsSent
FROM _Sent s
INNER JOIN _Subscribers sub ON s.SubscriberKey = sub.SubscriberKey
WHERE s.EventDate >= DATEADD(month, -1, GETDATE())
GROUP BY s.SubscriberKey, sub.EmailAddress
HAVING COUNT(s.JobID) >= 5

PATTERN 14 — Unique openers count per email:
SELECT
    j.EmailName,
    j.EmailSubject,
    COUNT(CASE WHEN o.IsUnique=1 THEN 1 END) AS UniqueOpens,
    COUNT(CASE WHEN c.IsUnique=1 THEN 1 END) AS UniqueClicks,
    COUNT(DISTINCT s.SubscriberKey) AS TotalSent
FROM _Job j
INNER JOIN _Sent s ON j.JobID = s.JobID
LEFT JOIN _Open o ON s.JobID=o.JobID AND s.ListID=o.ListID AND s.BatchID=o.BatchID AND s.SubscriberID=o.SubscriberID AND o.IsUnique=1
LEFT JOIN _Click c ON s.JobID=c.JobID AND s.ListID=c.ListID AND s.BatchID=c.BatchID AND s.SubscriberID=c.SubscriberID AND c.IsUnique=1
WHERE s.EventDate >= DATEADD(day, -30, GETDATE())
GROUP BY j.EmailName, j.EmailSubject

PLACEHOLDER DE NAMES: CustomerMaster | EmailEngagement | GlobalSuppression | RenewalCandidates
                      TrackingLog | JourneyEntrants | HardBounceList | ReEngagementTargets
                      FatigueList | BUUnsubList | VIPSegment | LapsedResponders

════════════════════════════════════════════════════════════════
SECTION 11 — CRITICAL SQL LOGIC RULES (architect-level)
════════════════════════════════════════════════════════════════

RULE — NULL COMPARISON TRAP (most common production bug):
NULL != 'anything' evaluates to UNKNOWN in SQL, not TRUE.
This means WHERE clauses that check inequality on LEFT JOIN columns
will silently DROP rows where the join found no match.

WRONG pattern — drops non-matching rows:
    LEFT JOIN _Journey jy ON ja.VersionID = jy.VersionID
    WHERE jy.JourneyName != 'Spring_Sale'    ← NULL != 'Spring_Sale' = UNKNOWN → row dropped

CORRECT pattern — use IS NULL to find non-matches:
    LEFT JOIN _JourneyActivity ja
        ON s.TriggererSendDefinitionObjectID = ja.JourneyActivityObjectID
    LEFT JOIN _Journey jy
        ON ja.VersionID = jy.VersionID
        AND jy.JourneyName = 'Spring_Sale'   ← filter in JOIN condition
    WHERE jy.VersionID IS NULL               ← IS NULL in WHERE = not in that journey

RULE — OR INCLUSION LOGIC:
When a prompt says "include them EVEN IF condition X", use OR in WHERE not AND.
"In list A but NOT received journey email, UNLESS they spent > 500"
translates to:
    WHERE (jy.VersionID IS NULL OR conv.MaxAmount > 500)
NOT:
    WHERE jy.VersionID IS NULL AND conv.MaxAmount > 500

RULE — MULTI-ROW DE JOINS ALWAYS NEED DEDUPLICATION:
When joining a custom DE that can have multiple rows per subscriber
(Conversions, PurchaseHistory, EventLog, etc.), always aggregate or use ROW_NUMBER().
NEVER do a raw JOIN to a multi-row DE without dedup — it multiplies rows.

WRONG:
    LEFT JOIN Conversions c ON lp.SubscriberKey = c.SubscriberKey
    WHERE c.Amount > 500
    -- Returns 10 rows if subscriber has 10 purchase records

CORRECT — aggregate first:
    LEFT JOIN (
        SELECT SubscriberKey, MAX(Amount) AS MaxAmount
        FROM Conversions
        GROUP BY SubscriberKey
    ) conv ON lp.SubscriberKey = conv.SubscriberKey

RULE — EXIST IN JOURNEY vs NOT IN JOURNEY pattern:
To find subscribers who ARE in a journey:
    INNER JOIN _JourneyActivity ja ON s.TriggererSendDefinitionObjectID = ja.JourneyActivityObjectID
    INNER JOIN _Journey jy ON ja.VersionID = jy.VersionID AND jy.JourneyName = 'JourneyName'

To find subscribers who are NOT in a journey:
    LEFT JOIN _JourneyActivity ja ON s.TriggererSendDefinitionObjectID = ja.JourneyActivityObjectID
    LEFT JOIN _Journey jy ON ja.VersionID = jy.VersionID AND jy.JourneyName = 'JourneyName'
    WHERE jy.VersionID IS NULL

RULE — CUSTOM DE JOIN SAFETY:
When joining custom Data Extensions:
1. Always aggregate multi-row DEs before joining (use subquery with GROUP BY)
2. Use LEFT JOIN unless you want to exclude non-matching subscribers
3. Apply filters on custom DE columns in the subquery, not in main WHERE

════════════════════════════════════════════════════════════════
SECTION 12 — ARCHITECT-LEVEL PATTERN
════════════════════════════════════════════════════════════════

PATTERN 15 — Multi-source with OR inclusion logic and dedup (the hardest pattern):
Use case: In Loyalty_Program DE, NOT sent from Spring_Sale journey in last 14 days,
BUT include them anyway if they spent > 500 in Conversions DE.

WITH JourneySent AS (
    -- Find subscribers who WERE sent from Spring_Sale journey in last 14 days
    SELECT DISTINCT s.SubscriberKey
    FROM _Sent s
    INNER JOIN _JourneyActivity ja
        ON s.TriggererSendDefinitionObjectID = ja.JourneyActivityObjectID
    INNER JOIN _Journey jy
        ON ja.VersionID = jy.VersionID
        AND jy.JourneyName = 'Spring_Sale'
    WHERE s.EventDate >= DATEADD(day, -14, GETDATE())
),
HighSpenders AS (
    -- Aggregate Conversions to one row per subscriber — avoid row multiplication
    SELECT SubscriberKey, MAX(Amount) AS MaxAmount
    FROM Conversions
    GROUP BY SubscriberKey
)
SELECT DISTINCT
    lp.SubscriberKey,
    lp.EmailAddress
FROM Loyalty_Program lp
LEFT JOIN JourneySent js ON lp.SubscriberKey = js.SubscriberKey
LEFT JOIN HighSpenders hs ON lp.SubscriberKey = hs.SubscriberKey
WHERE
    -- Include if NOT sent from journey in last 14 days
    js.SubscriberKey IS NULL
    -- OR include anyway if they are a high spender (even if they got the email)
    OR hs.MaxAmount > 500

PATTERN 16 — NOT EXISTS pattern (alternative to LEFT JOIN IS NULL, better for performance):
SELECT lp.SubscriberKey, lp.EmailAddress
FROM Loyalty_Program lp
WHERE NOT EXISTS (
    SELECT 1
    FROM _Sent s
    INNER JOIN _JourneyActivity ja
        ON s.TriggererSendDefinitionObjectID = ja.JourneyActivityObjectID
    INNER JOIN _Journey jy
        ON ja.VersionID = jy.VersionID
        AND jy.JourneyName = 'Spring_Sale'
    WHERE s.SubscriberKey = lp.SubscriberKey
    AND s.EventDate >= DATEADD(day, -14, GETDATE())
)

NOTE: NOT EXISTS is cleaner than LEFT JOIN IS NULL for exclusion logic
but is a correlated subquery — use only in Automation Studio, never Query Studio.
For Query Studio, always use the LEFT JOIN IS NULL pattern with a CTE.
"""


# ─────────────────────────────────────────
# FUNCTIONS
# ─────────────────────────────────────────
def generate_sfmc_sql(user_request, custom_de_names=""):
    # Sanitize inputs
    user_request = user_request.strip()[:2000]
    custom_de_names = custom_de_names.strip()[:500]

    de_context = (
        f"User's Data Extension names:\n{custom_de_names}"
        if custom_de_names
        else "No DE names given — suggest appropriate placeholder names."
    )

    full_prompt = f"""{SFMC_RULES}

User Request: {user_request}
{de_context}

You MUST respond using EXACTLY these markers in this exact order.
Do NOT add any text before the first marker or after the last marker.
Do NOT wrap SQL in markdown code fences.

If the request is not SFMC-related, respond ONLY with:
---INVALID---
Brief polite reason here.
---INVALID_END---

Otherwise respond with ALL FOUR of these sections:

---QS_START---
-- ⚡ QUERY STUDIO VERSION | Test Only | Max 100 Rows
[Write the complete Query Studio SQL here with TOP 100]
---QS_END---

---AS_START---
-- 🚀 AUTOMATION STUDIO VERSION | Production | Full Dataset
-- Target DE: [SuggestAGoodNameHere]
[Write the complete Automation Studio SQL here]
---AS_END---

---EXP_START---
[Write 2-3 plain English sentences explaining: what this query retrieves, which data views are joined and why, and any important warnings the user should know before running it in production.]
---EXP_END---"""

    resp = model.generate_content(
        full_prompt,
        generation_config=genai.GenerationConfig(
            temperature=0.1,
            max_output_tokens=1500,
        )
    )
    return resp.text


def parse_response(raw):
    qs = as_ = exp = ""
    invalid_msg = ""

    try:
        # Strip markdown code fences Gemini sometimes adds
        raw = raw.replace("```sql", "").replace("```", "").strip()

        # Check if AI flagged it as invalid
        if "---INVALID---" in raw:
            invalid_msg = raw.split("---INVALID---")[1].split("---INVALID_END---")[0].strip()
            return "", "", "", invalid_msg

        # Extract markers safely
        if "---QS_START---" in raw and "---QS_END---" in raw:
            qs = raw.split("---QS_START---")[1].split("---QS_END---")[0].strip()

        if "---AS_START---" in raw and "---AS_END---" in raw:
            as_ = raw.split("---AS_START---")[1].split("---AS_END---")[0].strip()

        if "---EXP_START---" in raw and "---EXP_END---" in raw:
            exp = raw.split("---EXP_START---")[1].split("---EXP_END---")[0].strip()

        # Clean up any remaining markdown from SQL blocks
        if qs:
            qs = qs.replace("```sql", "").replace("```", "").strip()
        if as_:
            as_ = as_.replace("```sql", "").replace("```", "").strip()

        # If markers missing entirely — never dump raw
        if not qs and not as_:
            invalid_msg = "AMPify could not generate a valid SQL query for this request. Please rephrase with more specific SFMC context — e.g. 'subscribers who opened in last 90 days'."
            return "", "", "", invalid_msg

    except Exception:
        invalid_msg = "Something went wrong while generating your query. Please try again."
        return "", "", "", invalid_msg

    return qs, as_, exp, ""


def validate(req):
    req = req.strip()

    # Too short — less than 3 characters
    if len(req) < 3:
        return False, "short", "Please describe what SFMC data you need."

    # Too long — prevents rendering issues
    if len(req) > 2000:
        return False, "long", "Your prompt is too long. Please keep it under 2000 characters."

    # Only block clearly off-topic requests
    off_topic = [
        "recipe", "cook food", "weather forecast", "write a story",
        "write a poem", "tell me a joke", "stock price", "crypto price",
        "bitcoin", "who are you", "what are you",
    ]
    if any(k in req.lower() for k in off_topic):
        return False, "offtopic", "That prompt doesn't seem related to Salesforce Marketing Cloud. AMPify only generates SFMC SQL queries — try describing what subscriber or engagement data you need."

    # Pass everything else to the AI — let the AI decide if it is SFMC-related
    return True, "", ""


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

    # ── ERROR BOX HELPER ──
    def show_error(title, message, icon="⚠️"):
        st.markdown(f"""
        <div style="background:#FFF4EF;border:1.5px solid rgba(255,107,53,0.35);
                    border-radius:12px;padding:18px 20px;margin-bottom:8px;">
            <div style="display:flex;align-items:center;gap:8px;margin-bottom:6px;">
                <span style="font-size:1.1rem;">{icon}</span>
                <span style="color:#C04000;font-weight:700;font-size:0.9rem;">{title}</span>
            </div>
            <div style="color:#7A2800;font-size:0.83rem;line-height:1.6;">{message}</div>
        </div>
        """, unsafe_allow_html=True)

    # ── HANDLE BUTTON PRESS ──
    if gen_btn:
        # Clear previous results on new attempt
        for k in ['qs', 'asm', 'exp', 'err']:
            st.session_state.pop(k, None)

        if not user_request.strip():
            st.session_state['err'] = ("Nothing to generate", "Please describe what you want the query to do in Step 1.", "📝")

        else:
            ok, err_type, err_msg = validate(user_request)
            if not ok:
                st.session_state['err'] = ("Prompt not recognised", err_msg, "🤔")
            else:
                try:
                    with st.spinner("Generating SFMC SQL..."):
                        raw = generate_sfmc_sql(user_request, custom_des)
                        qs, asm, exp, invalid_msg = parse_response(raw)

                    if invalid_msg:
                        st.session_state['err'] = ("AMPify couldn't process this request", invalid_msg, "🤔")
                    elif qs and asm:
                        st.session_state['qs'] = qs
                        st.session_state['asm'] = asm
                        st.session_state['exp'] = exp
                        st.toast("SQL generated!", icon="⚡")
                    else:
                        st.session_state['err'] = ("Generation incomplete", "AMPify generated an incomplete response. Please try rephrasing your prompt.", "⚠️")

                except Exception as e:
                    err_detail = str(e)
                    if "413" in err_detail or "too large" in err_detail.lower() or "request too large" in err_detail.lower():
                        st.session_state['err'] = ("Request too large", f"The prompt exceeded the API token limit. Full error: {err_detail[:500]}", "📦")
                    elif "rate_limit" in err_detail.lower() or "429" in err_detail:
                        st.session_state['err'] = ("Rate limit reached", f"Too many requests. Please wait and try again. Detail: {err_detail[:500]}", "⏳")
                    elif "timeout" in err_detail.lower():
                        st.session_state['err'] = ("Request timed out", f"The query took too long. Detail: {err_detail[:500]}", "⏱️")
                    elif "model" in err_detail.lower() or "not found" in err_detail.lower():
                        st.session_state['err'] = ("Model error", f"Model issue: {err_detail[:500]}", "🔌")
                    elif "api" in err_detail.lower() or "groq" in err_detail.lower():
                        st.session_state['err'] = ("Service error", f"API error: {err_detail[:500]}", "🔌")
                    else:
                        st.session_state['err'] = ("Something went wrong", f"Full error: {err_detail}", "⚠️")

    # ── SHOW ERROR IF ANY ──
    if st.session_state.get('err'):
        title, message, icon = st.session_state['err']
        show_error(title, message, icon)

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
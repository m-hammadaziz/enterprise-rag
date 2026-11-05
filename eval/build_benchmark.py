"""Builds eval/benchmark.jsonl from the compact question table below.

Each item:
  id, category, user, question, reference_answer,
  must_include  - list of required facts; each fact is "alt1|alt2" (any alternative counts)
  relevant_docs - doc slugs that contain the answer (empty for unanswerable)
  evidence      - exact substrings of the source that support the answer (chunk-level relevance)
  forbidden     - (access_denied only) facts that must NOT appear in the answer (leak check)

Categories
  factual        single fact, single document
  table          fact inside a table embedded in a document
  structured     answer lives in a CSV dataset (records table)
  multi_hop      needs 2+ sources
  catalog        "which documents ..." questions
  unanswerable   nothing in the corpus answers it -> must abstain
  access_denied  answer exists but the asking user lacks permission -> must abstain, no leak

    python -m eval.build_benchmark          # writes eval/benchmark.jsonl and validates evidence
"""
from __future__ import annotations

import json
from pathlib import Path

from scripts.sample_corpus import CSVS, DOCS

HERE = Path(__file__).resolve().parent

# (user, question, reference answer, must_include, doc_slug, evidence)
F = [
    # ---- employee-handbook (all-staff) ----
    ("alice", "How many hours is Corvane's standard working week?", "38 hours.", ["38"], "employee-handbook", "standard working week is 38 hours"),
    ("bob", "What are the core collaboration hours?", "10:00 to 15:00 local time.", ["10:00", "15:00"], "employee-handbook", "Core collaboration hours are 10:00 to 15:00"),
    ("dave", "At what rate is approved overtime paid for non-exempt employees?", "1.5 times the base hourly rate.", ["1.5"], "employee-handbook", "paid at 1.5 times the base hourly rate"),
    ("alice", "How many days of paid annual leave do full-time employees get?", "25 days per calendar year.", ["25"], "employee-handbook", "receive 25 days of paid annual leave"),
    ("carol", "How much annual leave do employees with five or more years of service receive?", "28 days.", ["28"], "employee-handbook", "five or more years of service receive 28 days"),
    ("bob", "How many unused vacation days can be carried over to next year?", "Up to 5 days, expiring 31 March.", ["5"], "employee-handbook", "Up to 5 unused days may be carried over"),
    ("dave", "When do carried-over leave days expire?", "31 March.", ["31 march"], "employee-handbook", "carried-over days expire on 31 March"),
    ("alice", "How far in advance must I request leave longer than 10 consecutive working days?", "At least 30 days in advance.", ["30"], "employee-handbook", "must be submitted at least 30 days in advance"),
    ("carol", "How many paid sick days do employees get per year?", "12 days.", ["12"], "employee-handbook", "12 days of paid sick leave per year"),
    ("bob", "When is a medical certificate required for sick leave?", "For absences longer than 3 consecutive days.", ["3"], "employee-handbook", "medical certificate is required for absences longer than 3 consecutive days"),
    ("alice", "How many weeks of paid parental leave does the primary caregiver get?", "20 weeks fully paid.", ["20"], "employee-handbook", "primary caregiver receives 20 weeks"),
    ("dave", "How much parental leave does the secondary caregiver receive?", "6 weeks fully paid, within 12 months.", ["6"], "employee-handbook", "secondary caregiver receives 6 weeks"),
    ("carol", "How many days per week can employees work remotely?", "Up to 3 days per week with manager approval.", ["3"], "employee-handbook", "work remotely up to 3 days per week"),
    ("alice", "For how many days per year can I work from another country?", "Up to 30 days per calendar year, registered with HR 2 weeks before.", ["30"], "employee-handbook", "Working from another country is allowed for up to 30 days per calendar year"),
    ("bob", "How much is the home office stipend for new hires?", "A one-time 600 USD stipend.", ["600"], "employee-handbook", "home office stipend of 600 USD"),
    ("dave", "How many public holidays does each office observe?", "11 per year, plus the winter shutdown.", ["11"], "employee-handbook", "observes 11 public holidays per year"),
    ("alice", "When is the company winter shutdown?", "27 to 31 December.", ["27", "31 december"], "employee-handbook", "winter shutdown between 27 and 31 December"),
    ("carol", "Above what value must vendor gifts be declared?", "Gifts worth more than 75 USD.", ["75"], "employee-handbook", "worth more than 75 USD must be declared"),
    ("bob", "How can employees raise concerns anonymously?", "Through the EthicsLine portal run by an independent third party.", ["ethicsline"], "employee-handbook", "raised anonymously through the EthicsLine portal"),
    ("alice", "What is the annual learning budget per employee?", "1,500 USD per year; it does not roll over.", ["1500"], "employee-handbook", "annual learning budget of 1,500 USD"),
    # ---- travel-expense-policy (all-staff) ----
    ("alice", "Which tool must be used to book business travel?", "The Navio travel portal.", ["navio"], "travel-expense-policy", "booked through the Navio travel portal"),
    ("bob", "What flight class is required for flights under 6 hours?", "Economy class.", ["economy"], "travel-expense-policy", "Economy class is required for flights under 6 hours"),
    ("dave", "Who must approve business class flights?", "A Vice President, in writing.", ["vice president|vp"], "travel-expense-policy", "Business class requires written approval from a Vice President"),
    ("carol", "When is premium economy allowed?", "For flights of 6 hours or longer.", ["6 hours"], "travel-expense-policy", "Premium economy is allowed for flights of 6 hours or longer"),
    ("alice", "What is the hotel cap per night in standard cities?", "220 USD.", ["220"], "travel-expense-policy", "nightly hotel cap is 220 USD"),
    ("bob", "What is the nightly hotel limit in high-cost cities like London?", "320 USD.", ["320"], "travel-expense-policy", "320 USD in high-cost cities"),
    ("dave", "Which cities count as high-cost for hotel limits?", "New York, London, Zurich, Tokyo and San Francisco.", ["new york", "london", "zurich", "tokyo", "san francisco"], "travel-expense-policy", "New York, London, Zurich, Tokyo and San Francisco"),
    ("alice", "What is the international meal per diem?", "95 USD per day.", ["95"], "travel-expense-policy", "95 USD for international travel"),
    ("carol", "What is the daily meal allowance for domestic travel?", "75 USD.", ["75"], "travel-expense-policy", "daily meal per diem is 75 USD for domestic travel"),
    ("bob", "Who approves an expense of 3,000 USD?", "A director (500-5,000 USD range).", ["director"], "travel-expense-policy", "Expenses between 500 and 5,000 USD require director approval"),
    ("dave", "Who has to approve expenses above 5,000 USD?", "The CFO.", ["cfo"], "travel-expense-policy", "Anything above 5,000 USD requires approval from the CFO"),
    ("alice", "What is the deadline for submitting expense claims?", "Within 30 days of the expense date.", ["30"], "travel-expense-policy", "submitted within 30 days of the expense date"),
    ("carol", "Above what amount are itemised receipts required?", "Every expense over 25 USD.", ["25"], "travel-expense-policy", "required for every expense over 25 USD"),
    ("bob", "Who is eligible for a corporate card?", "Employees who travel more than four times a year.", ["four|4"], "travel-expense-policy", "travel more than four times a year are eligible for a corporate card"),
    # ---- information-security-policy (all-staff, contractors) ----
    ("frank", "What is the minimum password length?", "14 characters.", ["14"], "information-security-policy", "at least 14 characters long"),
    ("alice", "Which password manager does Corvane use?", "Keyhold.", ["keyhold"], "information-security-policy", "company password manager, Keyhold"),
    ("bob", "When are hardware security keys required?", "For production access and for administrators.", ["production", "administrator"], "information-security-policy", "hardware security keys are required for production access and for administrators"),
    ("frank", "After how many minutes of inactivity must laptops lock?", "5 minutes.", ["5"], "information-security-policy", "lock automatically after 5 minutes of inactivity"),
    ("carol", "Within how many days must OS security patches be installed?", "Within 14 days of release.", ["14"], "information-security-policy", "installed within 14 days of release"),
    ("dave", "How quickly must a lost laptop be reported to IT?", "Within 1 hour.", ["1 hour"], "information-security-policy", "reported to IT within 1 hour"),
    ("frank", "What are the four data classification levels?", "Public, Internal, Confidential and Restricted.", ["public", "internal", "confidential", "restricted"], "information-security-policy", "Public, Internal, Confidential and Restricted"),
    ("alice", "How is customer personal data classified?", "Restricted.", ["restricted"], "information-security-policy", "Customer personal data is classified as Restricted"),
    ("bob", "How do I report a suspected security incident?", "To the SOC within 1 hour via #sec-incidents or soc@corvane.example.", ["1 hour", "sec-incidents|soc@corvane.example"], "information-security-policy", "reported to the Security Operations Center within 1 hour"),
    ("carol", "How often do managers review their team's access rights?", "Every quarter.", ["quarter"], "information-security-policy", "access rights every quarter"),
    ("frank", "Within how many days must new joiners complete security training?", "Within 14 days of joining, then annually.", ["14"], "information-security-policy", "within 14 days of joining and annually afterwards"),
    ("dave", "How quickly is access revoked for leavers?", "Within 4 hours of departure.", ["4 hours"], "information-security-policy", "revoked within 4 hours of their departure"),
    # ---- incident-response-runbook (engineering) ----
    ("alice", "What is the response time for a SEV1 incident?", "Within 15 minutes, all hands.", ["15 minutes"], "incident-response-runbook", "Response within 15 minutes"),
    ("alice", "What is the response time target for SEV2 incidents?", "Within 30 minutes.", ["30 minutes"], "incident-response-runbook", "major feature degraded for many customers. Response within 30 minutes"),
    ("erin", "How is a SEV3 incident defined?", "Minor degradation or a single customer affected; response within 4 business hours.", ["minor|single customer"], "incident-response-runbook", "SEV3: minor degradation or a single customer affected"),
    ("alice", "When does the on-call rotation hand over?", "Every Monday at 10:00 UTC.", ["monday", "10:00"], "incident-response-runbook", "hands over every Monday at 10:00 UTC"),
    ("alice", "How much is the on-call stipend?", "300 USD per week of on-call.", ["300"], "incident-response-runbook", "stipend of 300 USD per week"),
    ("erin", "Which tool sends pages to on-call engineers?", "PagerTree.", ["pagertree"], "incident-response-runbook", "Pages are sent through PagerTree"),
    ("alice", "After how long does an unacknowledged page escalate to the secondary?", "10 minutes.", ["10 minutes"], "incident-response-runbook", "within 10 minutes, it escalates automatically"),
    ("alice", "How often must the status page be updated during a SEV1?", "At least every 30 minutes.", ["30 minutes"], "incident-response-runbook", "at least every 30 minutes during a SEV1"),
    ("erin", "Within how many business days must a postmortem be published?", "Within 5 business days.", ["5 business days"], "incident-response-runbook", "published within 5 business days"),
    ("alice", "Where are postmortem action items tracked?", "In the RELIABILITY Jira project.", ["reliability"], "incident-response-runbook", "tracked in the RELIABILITY Jira project"),
    ("alice", "Do rollbacks require change approval?", "No, rollbacks do not require change approval.", ["not|no"], "incident-response-runbook", "Rollbacks do not require change approval"),
    # ---- deployment-guide (engineering) ----
    ("alice", "Which pipeline do services deploy through?", "The Foundry pipeline.", ["foundry"], "deployment-guide", "Services deploy through the Foundry pipeline"),
    ("erin", "How many code reviews do changes to payment services need?", "Two approving reviews, one from a code owner.", ["two|2"], "deployment-guide", "need two approving reviews"),
    ("alice", "What share of traffic does a canary get first and for how long?", "5 percent for 20 minutes.", ["5 percent|5%", "20 minutes"], "deployment-guide", "5 percent of traffic for 20 minutes"),
    ("alice", "What error rate threshold does canary analysis use?", "Error rate must stay below 1 percent.", ["1 percent|1%"], "deployment-guide", "error rate stays below 1 percent"),
    ("erin", "Can we deploy to production on Friday afternoon?", "No production deploys on Fridays after 14:00 UTC.", ["14:00"], "deployment-guide", "no production deploys on Fridays after 14:00 UTC"),
    ("alice", "When is the company-wide code freeze?", "20 December to 3 January.", ["20 december", "3 january"], "deployment-guide", "code freeze applies from 20 December to 3 January"),
    ("alice", "Who approves emergency fixes during a code freeze?", "The VP of Engineering.", ["vp of engineering"], "deployment-guide", "approval from the VP of Engineering"),
    ("erin", "Where are feature flags managed?", "In Flagpole.", ["flagpole"], "deployment-guide", "feature flag managed in Flagpole"),
    ("alice", "When must fully rolled-out feature flags be removed?", "After more than 60 days.", ["60"], "deployment-guide", "more than 60 days must be removed"),
    ("alice", "What command rolls back a service?", "foundry rollback <service> <version>.", ["foundry rollback"], "deployment-guide", "foundry rollback <service> <version>"),
    # ---- platform-architecture (engineering) ----
    ("alice", "Which is the primary hosting region?", "eu-central (Frankfurt).", ["eu-central|frankfurt"], "platform-architecture", "primary region is eu-central (Frankfurt)"),
    ("erin", "Where is the disaster recovery region?", "eu-west (Dublin).", ["eu-west|dublin"], "platform-architecture", "disaster recovery region is eu-west (Dublin)"),
    ("alice", "What are the RPO and RTO?", "RPO 15 minutes, RTO 4 hours.", ["15 minutes", "4 hours"], "platform-architecture", "RPO) is 15 minutes"),
    ("alice", "How often is disaster recovery failover tested?", "Twice a year.", ["twice"], "platform-architecture", "tested twice a year"),
    ("erin", "What language is the Ledger service written in?", "Kotlin.", ["kotlin"], "platform-architecture", "Ledger: billing and invoicing service, written in Kotlin"),
    ("alice", "Which service is the analytics query engine and what language is it in?", "Insight, written in Rust.", ["insight", "rust"], "platform-architecture", "Insight: analytics query engine, written in Rust"),
    ("alice", "Which database stores analytics data?", "ClickHouse.", ["clickhouse"], "platform-architecture", "Analytics data is stored in ClickHouse"),
    ("erin", "What is the public API availability SLO?", "99.95 percent per calendar month.", ["99.95"], "platform-architecture", "availability SLO of 99.95 percent"),
    ("alice", "What is the p95 latency target for API requests?", "300 milliseconds.", ["300"], "platform-architecture", "p95 latency target for API requests is 300 milliseconds"),
    ("alice", "What API rate limit do Enterprise customers get?", "5,000 requests per minute.", ["5000"], "platform-architecture", "limit of 5,000 requests per minute"),
    # ---- q3-2026-financial-report (finance, exec) ----
    ("bob", "What was total revenue in Q3 2026?", "18.4 million USD, up 22% YoY.", ["18.4"], "q3-2026-financial-report", "total revenue of 18.4 million USD in Q3 2026"),
    ("bob", "How much did revenue grow year over year in Q3 2026?", "22 percent.", ["22"], "q3-2026-financial-report", "an increase of 22 percent year over year"),
    ("erin", "What was subscription revenue in Q3 2026?", "16.1 million USD.", ["16.1"], "q3-2026-financial-report", "Subscription revenue was 16.1 million USD"),
    ("bob", "What was the gross margin in Q3 2026 and why did it change?", "74%, up from 71% due to lower hosting costs after the Skyline renegotiation.", ["74", "hosting"], "q3-2026-financial-report", "Gross margin was 74 percent"),
    ("bob", "How much was spent on research and development in Q3 2026?", "6.2 million USD.", ["6.2"], "q3-2026-financial-report", "Research and development was the largest category at 6.2 million USD"),
    ("erin", "What were total operating expenses in Q3?", "14.7 million USD.", ["14.7"], "q3-2026-financial-report", "Total operating expenses were 14.7 million USD"),
    ("bob", "How much cash did the company have at the end of Q3 2026?", "41.5 million USD.", ["41.5"], "q3-2026-financial-report", "Cash and cash equivalents at the end of Q3 2026 were 41.5 million USD"),
    ("bob", "What was net cash burn in Q3 2026?", "2.8 million USD.", ["2.8"], "q3-2026-financial-report", "Net cash burn in the quarter was 2.8 million USD"),
    ("erin", "How many paying customers did Corvane have at the end of Q3?", "1,240, including 86 enterprise.", ["1240"], "q3-2026-financial-report", "1,240 paying customers"),
    ("bob", "What was net revenue retention?", "112 percent.", ["112"], "q3-2026-financial-report", "Net revenue retention was 112 percent"),
    ("bob", "What is the Q4 2026 revenue guidance?", "19.5 to 20.2 million USD.", ["19.5", "20.2"], "q3-2026-financial-report", "between 19.5 and 20.2 million USD"),
    ("erin", "When does management target operating break-even?", "Q2 2027.", ["q2 2027"], "q3-2026-financial-report", "operating break-even in Q2 2027"),
    # ---- fy2027-budget-plan (finance, exec) ----
    ("bob", "What is the total FY2027 operating budget?", "64 million USD, +9% vs FY2026.", ["64"], "fy2027-budget-plan", "total operating budget for fiscal year 2027 is 64 million USD"),
    ("erin", "When does fiscal year 2027 start and end?", "1 February 2027 to 31 January 2028.", ["1 february 2027", "31 january 2028"], "fy2027-budget-plan", "runs from 1 February 2027 to 31 January 2028"),
    ("bob", "What is the size of the central contingency reserve?", "2.5 million USD held by the CFO.", ["2.5"], "fy2027-budget-plan", "contingency reserve of 2.5 million USD"),
    ("bob", "What approval is needed to reallocate more than 250,000 USD between departments?", "Executive team approval.", ["executive team"], "fy2027-budget-plan", "reallocation above 250,000 USD requires approval from the executive team"),
    ("erin", "How many new hires are planned in FY2027?", "71, reaching about 520 employees.", ["71"], "fy2027-budget-plan", "The plan adds 71 new hires in total"),
    ("bob", "What is the FY2027 travel budget cap?", "1.8 million USD.", ["1.8"], "fy2027-budget-plan", "capped at 1.8 million USD"),
    # ---- data-retention-policy (all-staff) ----
    ("alice", "How long are application logs retained?", "90 days.", ["90"], "data-retention-policy", "Application logs | 90 days"),
    ("dave", "How long must financial and tax records be kept?", "10 years.", ["10 years"], "data-retention-policy", "Financial and tax records | 10 years"),
    ("carol", "How long are security audit logs retained?", "2 years.", ["2 years"], "data-retention-policy", "Security audit logs | 2 years"),
    ("bob", "How long are personnel files kept after someone leaves?", "7 years after employment ends.", ["7 years"], "data-retention-policy", "Employee personnel files | 7 years after employment ends"),
    ("dave", "How long do we keep records of unsuccessful candidates?", "12 months.", ["12 months"], "data-retention-policy", "Recruiting records of unsuccessful candidates | 12 months"),
    ("alice", "How soon is customer production data deleted after termination?", "Within 60 days; backups age out within a further 35 days.", ["60"], "data-retention-policy", "deleted within 60 days"),
    ("carol", "What happens to deletion when a legal hold is issued?", "All deletion for the affected records is suspended until released in writing.", ["suspend"], "data-retention-policy", "suspends all deletion for the affected records"),
    ("bob", "Within how many days must data subject deletion requests be completed?", "30 days.", ["30"], "data-retention-policy", "completed within 30 days of receipt"),
    ("dave", "Who owns the data retention policy?", "The Legal team, reviewed yearly.", ["legal"], "data-retention-policy", "The Legal team owns this policy"),
    # ---- skyline-hosting-contract-summary (legal) ----
    ("carol", "When does the Skyline Cloud Hosting contract end?", "30 June 2029 (3-year term from 1 July 2026).", ["30 june 2029"], "skyline-hosting-contract-summary", "ending on 30 June 2029"),
    ("carol", "What is the minimum annual spend commitment with Skyline?", "2.4 million USD per contract year.", ["2.4"], "skyline-hosting-contract-summary", "minimum spend of 2.4 million USD per contract year"),
    ("erin", "What discount does Skyline give on list prices?", "18 percent.", ["18"], "skyline-hosting-contract-summary", "18 percent discount on list prices"),
    ("carol", "What uptime does Skyline guarantee for compute?", "99.99 percent monthly.", ["99.99"], "skyline-hosting-contract-summary", "guarantees 99.99 percent monthly uptime"),
    ("carol", "What is Skyline's liability cap?", "12 months of fees paid (not for data protection breaches or gross negligence).", ["12 months"], "skyline-hosting-contract-summary", "liability is capped at 12 months of fees paid"),
    ("erin", "How much notice is needed to terminate the Skyline contract for convenience?", "180 days written notice after the first year.", ["180"], "skyline-hosting-contract-summary", "180 days written notice"),
    ("carol", "How fast must Skyline notify us of a personal data breach?", "Within 24 hours.", ["24 hours"], "skyline-hosting-contract-summary", "within 24 hours"),
    ("carol", "What service credit applies if Skyline uptime falls below 99.5 percent?", "25 percent of the monthly fee.", ["25"], "skyline-hosting-contract-summary", "rising to 25 percent below 99.5 percent uptime"),
    # ---- sales-playbook (sales) ----
    ("dave", "What are the opportunity stages?", "Discovery, Qualification, Technical Validation, Proposal, Negotiation.", ["discovery", "qualification", "technical validation", "proposal", "negotiation"], "sales-playbook", "Discovery, Qualification, Technical Validation, Proposal and Negotiation"),
    ("dave", "Who can approve a 15 percent discount?", "The regional sales director (10-20%).", ["regional sales director"], "sales-playbook", "Discounts from 10 to 20 percent need approval from the regional sales director"),
    ("dave", "Who must approve discounts above 20 percent?", "The Chief Revenue Officer.", ["chief revenue officer|cro"], "sales-playbook", "Discounts above 20 percent need approval from the Chief Revenue Officer"),
    ("erin", "What extra discount can multi-year contracts get?", "5% per extra committed year, max 10%.", ["5 percent|5%", "10 percent|10%"], "sales-playbook", "additional 5 percent discount per extra committed year"),
    ("dave", "What commission do account executives earn on new business?", "10% of first-year ACV, paid after first invoice is paid.", ["10 percent|10%"], "sales-playbook", "earn 10 percent commission on first-year annual contract value"),
    ("dave", "What is the commission rate on renewals?", "3 percent.", ["3 percent|3%"], "sales-playbook", "Renewals pay 3 percent commission"),
    ("dave", "Payment terms longer than what need Finance approval?", "Longer than net 45.", ["45"], "sales-playbook", "longer than net 45 require approval from Finance"),
    ("dave", "How long can a sales-assisted proof of concept last?", "Up to 30 days with a written success plan.", ["30"], "sales-playbook", "may last up to 30 days"),
    # ---- product-pricing-faq (sales) ----
    ("dave", "How much does the Growth plan cost?", "99 USD per user per month.", ["99"], "product-pricing-faq", "Growth costs 99 USD per user per month"),
    ("dave", "What is the Starter plan price?", "49 USD per user per month.", ["49"], "product-pricing-faq", "Starter costs 49 USD per user per month"),
    ("erin", "What is the minimum seat count for Enterprise?", "50 seats.", ["50"], "product-pricing-faq", "minimum of 50 seats"),
    ("dave", "What discount do customers get for paying annually?", "15 percent on Starter and Growth.", ["15"], "product-pricing-faq", "receive a 15 percent discount compared to monthly billing"),
    ("dave", "How much does the Advanced Security add-on cost?", "12 USD per user per month.", ["12"], "product-pricing-faq", "Advanced Security add-on costs 12 USD per user per month"),
    ("dave", "Is there a free plan?", "No; there is a 14-day free trial of Growth.", ["no free plan|14-day"], "product-pricing-faq", "There is no free plan"),
    ("erin", "What discount do nonprofits get?", "30 percent on Starter and Growth.", ["30"], "product-pricing-faq", "receive a 30 percent discount"),
    ("dave", "How much does Premium Support cost?", "20 percent of annual subscription value.", ["20 percent|20%"], "product-pricing-faq", "Premium Support costs 20 percent of the annual subscription value"),
    # ---- project-atlas-board-memo (exec) ----
    ("erin", "Which company would be acquired in Project Atlas?", "Brightline Data, a 45-person data-quality startup in Lisbon.", ["brightline"], "project-atlas-board-memo", "proposed acquisition of Brightline Data"),
    ("erin", "What is the proposed purchase price for Project Atlas?", "38 million USD (70% cash, 30% stock).", ["38"], "project-atlas-board-memo", "proposed purchase price is 38 million USD"),
    ("erin", "When is the board vote on Project Atlas?", "12 November 2026.", ["12 november 2026"], "project-atlas-board-memo", "board vote is scheduled for 12 November 2026"),
    ("erin", "How large is the proposed retention pool for Brightline employees?", "3 million USD.", ["3 million"], "project-atlas-board-memo", "retention pool of 3 million USD"),
    # ---- contractor-onboarding-guide (contractors, all-staff) ----
    ("frank", "When do contractor accounts expire?", "After 90 days unless renewed by the sponsoring manager.", ["90"], "contractor-onboarding-guide", "expire automatically after 90 days"),
    ("frank", "When are contractor timesheets due?", "Weekly in Tempo by Monday 12:00 for the previous week.", ["monday", "12:00"], "contractor-onboarding-guide", "by Monday 12:00 for the previous week"),
    ("frank", "How quickly are contractor invoices paid?", "Within 30 days of receipt.", ["30"], "contractor-onboarding-guide", "paid within 30 days of receipt"),
    ("frank", "When can a contractor request a company laptop?", "If the engagement lasts longer than 6 months.", ["6 months"], "contractor-onboarding-guide", "longer than 6 months"),
    ("alice", "What must contractors sign before getting system access?", "The Corvane NDA and the contractor agreement.", ["nda"], "contractor-onboarding-guide", "must sign the Corvane NDA and the contractor agreement"),
    # ---- benefits-overview (all-staff) ----
    ("alice", "What share of the health insurance premium does Corvane pay for dependants?", "75 percent (100% for employees).", ["75"], "benefits-overview", "75 percent for dependants"),
    ("bob", "What is the 401(k) match?", "Dollar for dollar up to 4% of base salary, vesting immediately.", ["4 percent|4%"], "benefits-overview", "up to 4 percent of base salary"),
    ("carol", "How much is the monthly wellness allowance?", "50 USD per month.", ["50"], "benefits-overview", "wellness allowance of 50 USD per month"),
    ("dave", "How often are laptops refreshed?", "Every 3 years.", ["3 years"], "benefits-overview", "refreshed every 3 years"),
    ("alice", "What is the referral bonus for engineering roles?", "5,000 USD.", ["5000"], "benefits-overview", "For engineering roles the referral bonus is 5,000 USD"),
    ("bob", "Which counselling service is available to employees?", "Calmwave.", ["calmwave"], "benefits-overview", "Calmwave counselling service"),
]

TABLE = [  # facts inside tables embedded in documents
    ("bob", "What is the Engineering department budget for FY2027?", "26.5 million USD with 34 planned hires.", ["26.5"], "fy2027-budget-plan", "Engineering; Budget (USD): 26.5 million"),
    ("erin", "How many new hires are planned for Sales and Marketing in FY2027?", "22.", ["22"], "fy2027-budget-plan", "Sales and Marketing; Budget (USD): 20.0 million; Planned new hires: 22"),
    ("bob", "What is the Customer Success budget for FY2027?", "6.5 million USD.", ["6.5"], "fy2027-budget-plan", "Customer Success; Budget (USD): 6.5 million"),
    ("alice", "How long are customer contracts retained after they end?", "6 years after contract end.", ["6 years"], "data-retention-policy", "Customer contracts | 6 years after contract end"),
]

STRUCT = [  # answers in CSV datasets
    ("alice", "What was ARR in July 2026?", "69.8 million USD.", ["69.8"], "kpi-monthly-2026", "month: 2026-07 (July 2026); arr musd: 69.8"),
    ("bob", "What was the NPS in September 2026?", "49.", ["49"], "kpi-monthly-2026", "month: 2026-09 (September 2026); arr musd: 72.6; logo churn pct: 0.8; nps: 49"),
    ("dave", "What was logo churn in March 2026?", "1.3 percent.", ["1.3"], "kpi-monthly-2026", "month: 2026-03 (March 2026); arr musd: 64.4; logo churn pct: 1.3"),
    ("alice", "What was API uptime in August 2026?", "99.88 percent.", ["99.88"], "kpi-monthly-2026", "api uptime pct: 99.88"),
    ("carol", "How many support tickets were there in May 2026?", "1,690.", ["1690"], "kpi-monthly-2026", "support tickets: 1690"),
    ("dave", "What was ARR in January 2026?", "62.1 million USD.", ["62.1"], "kpi-monthly-2026", "month: 2026-01 (January 2026); arr musd: 62.1"),
    ("alice", "What is the headcount of the Lisbon office?", "96.", ["96"], "office-locations", "city: Lisbon; country: Portugal; opened: 2019; headcount: 96"),
    ("bob", "When did the Singapore office open?", "2024.", ["2024"], "office-locations", "city: Singapore; country: Singapore; opened: 2024"),
    ("dave", "How many people work at Corvane HQ in Berlin?", "182.", ["182"], "office-locations", "city: Berlin; country: Germany; opened: 2016; headcount: 182"),
    ("carol", "Who leads the Toronto office?", "The Director of Customer Success.", ["director of customer success"], "office-locations", "office lead role: Director of Customer Success"),
    ("alice", "Which office opened in 2025?", "Corvane Krakow (Poland).", ["krakow"], "office-locations", "city: Krakow; country: Poland; opened: 2025"),
    ("carol", "What is the salary range for an L3 Senior Software Engineer?", "76,000 to 96,000 EUR.", ["76000", "96000"], "compensation-bands", "level: L3; title: Senior Software Engineer; salary min eur: 76000; salary max eur: 96000"),
    ("erin", "What is the maximum salary for a Staff Engineer?", "118,000 EUR.", ["118000"], "compensation-bands", "salary max eur: 118000"),
    ("carol", "How many equity units does a Principal Engineer get?", "3,000.", ["3000"], "compensation-bands", "level: L5; title: Principal Engineer; salary min eur: 115000; salary max eur: 140000; equity units: 3000"),
    ("erin", "What is the minimum salary for an L1 Associate Engineer?", "52,000 EUR.", ["52000"], "compensation-bands", "level: L1; title: Associate Engineer; salary min eur: 52000"),
]

# (user, question, answer, must_include, [docs], [evidence])
MULTI = [
    ("erin", "Which cloud provider hosts the platform, and what uptime does that provider guarantee contractually?", "Skyline Cloud Hosting; 99.99% monthly compute uptime.", ["skyline", "99.99"], ["platform-architecture", "skyline-hosting-contract-summary"], ["hosted by Skyline Cloud Hosting", "guarantees 99.99 percent monthly uptime"]),
    ("erin", "Why did gross margin improve in Q3 2026, and what discount does the renegotiated hosting contract give?", "Lower hosting costs after the Skyline renegotiation; an 18% discount on list prices.", ["hosting", "18"], ["q3-2026-financial-report", "skyline-hosting-contract-summary"], ["lower hosting costs after the renegotiated Skyline contract", "18 percent discount on list prices"]),
    ("alice", "What is the SEV1 response time and how many reviews does a change to the authentication service need?", "15 minutes; two approving reviews.", ["15 minutes", "two|2"], ["incident-response-runbook", "deployment-guide"], ["Response within 15 minutes", "need two approving reviews"]),
    ("alice", "Compare the annual leave and the sick leave allowance for full-time employees.", "25 days annual leave and 12 days sick leave.", ["25", "12"], ["employee-handbook"], ["receive 25 days of paid annual leave", "12 days of paid sick leave per year"]),
    ("dave", "What is the hotel cap in Tokyo and the international meal per diem?", "320 USD per night; 95 USD per day.", ["320", "95"], ["travel-expense-policy"], ["320 USD in high-cost cities", "95 USD for international travel"]),
    ("erin", "How many employees does Brightline Data have and how many people work in Corvane's Lisbon office?", "Brightline has 45; Corvane Lisbon has 96.", ["45", "96"], ["project-atlas-board-memo", "office-locations"], ["data-quality startup with 45 employees based in Lisbon", "city: Lisbon; country: Portugal; opened: 2019; headcount: 96"]),
    ("bob", "What were Q3 2026 revenue and Q3 net cash burn?", "18.4M revenue, 2.8M net burn.", ["18.4", "2.8"], ["q3-2026-financial-report"], ["total revenue of 18.4 million USD in Q3 2026", "Net cash burn in the quarter was 2.8 million USD"]),
    ("alice", "How quickly must a security incident be reported and how quickly must a SEV2 be responded to?", "Report within 1 hour; SEV2 response within 30 minutes.", ["1 hour", "30 minutes"], ["information-security-policy", "incident-response-runbook"], ["reported to the Security Operations Center within 1 hour", "major feature degraded for many customers. Response within 30 minutes"]),
    ("dave", "What is the Growth plan list price and what discount can an account executive approve alone?", "99 USD/user/month; up to 10%.", ["99", "10 percent|10%"], ["product-pricing-faq", "sales-playbook"], ["Growth costs 99 USD per user per month", "Discounts up to 10 percent can be approved by the account executive"]),
    ("carol", "How long are security audit logs kept, and how long are application logs kept?", "2 years and 90 days.", ["2 years", "90"], ["data-retention-policy"], ["Security audit logs | 2 years", "Application logs | 90 days"]),
]

CATALOG = [
    ("alice", "Which documents are available about information security?", "The Information Security Policy.", ["information security policy"], ["information-security-policy"], []),
    ("dave", "What documents do we have about sales or pricing?", "Sales Playbook and Product Pricing FAQ.", ["sales playbook|product pricing"], ["sales-playbook", "product-pricing-faq"], []),
    ("frank", "Which documents exist for contractors?", "Contractor Onboarding Guide.", ["contractor onboarding"], ["contractor-onboarding-guide"], []),
]

UNANSWERABLE = [
    ("alice", "What is Corvane's policy on bringing dogs to the office?"),
    ("bob", "What was revenue in Q3 2024?"),
    ("dave", "How many days of paid bereavement leave do employees get?"),
    ("carol", "What is the CEO's home address?"),
    ("alice", "Which Kubernetes version do our clusters run?"),
    ("alice", "What is the on-call stipend for SEV4 incidents in Antarctica?"),
    ("dave", "What is the price of the Ultimate plan?"),
    ("erin", "Who won the company hackathon in 2025?"),
    ("bob", "What is the parking reimbursement limit?"),
    ("alice", "What is the Wi-Fi password for the Berlin office?"),
    ("carol", "What is the termination notice period in our contract with Amazon Web Services?"),
    ("frank", "What hourly rate are contractors paid?"),
    ("dave", "What was the NPS in December 2026?"),
    ("erin", "What is the budget for the Legal department in FY2029?"),
    ("alice", "How many employees work in the Tokyo office?"),
    ("bob", "What is the stock price of Corvane today?"),
    ("alice", "What programming language is the Notifier service's mobile app written in?"),
    ("carol", "Does Corvane offer sabbaticals after ten years?"),
    ("dave", "What is the commission rate for partners in Brazil?"),
    ("erin", "What is the interest rate on the company's bank loan?"),
]

# (user lacking access, question, forbidden facts, doc that holds the answer)
ACCESS_DENIED = [
    ("alice", "What is the proposed purchase price for Project Atlas?", ["38 million|38"], "project-atlas-board-memo"),
    ("bob", "Which company would Corvane acquire in Project Atlas?", ["brightline"], "project-atlas-board-memo"),
    ("dave", "When is the board vote on the Brightline acquisition?", ["12 november"], "project-atlas-board-memo"),
    ("carol", "How large is the retention pool proposed in the board memo?", ["3 million"], "project-atlas-board-memo"),
    ("alice", "What was total revenue in Q3 2026?", ["18.4"], "q3-2026-financial-report"),
    ("dave", "How much cash did Corvane have at the end of Q3 2026?", ["41.5"], "q3-2026-financial-report"),
    ("frank", "What was net revenue retention in Q3 2026?", ["112"], "q3-2026-financial-report"),
    ("alice", "What is the Engineering department budget for FY2027?", ["26.5"], "fy2027-budget-plan"),
    ("carol", "What is the total FY2027 operating budget?", ["64 million"], "fy2027-budget-plan"),
    ("alice", "What is the liability cap in the Skyline contract?", ["12 months of fees"], "skyline-hosting-contract-summary"),
    ("bob", "What is the minimum annual spend commitment with Skyline?", ["2.4"], "skyline-hosting-contract-summary"),
    ("alice", "What is the salary range for an L3 Senior Software Engineer?", ["76000|76,000", "96000|96,000"], "compensation-bands"),
    ("dave", "What is the maximum salary for a Staff Engineer?", ["118000|118,000"], "compensation-bands"),
    ("alice", "Who can approve a 15 percent discount?", ["regional sales director"], "sales-playbook"),
    ("bob", "What commission do account executives earn on renewals?", ["3 percent|3%"], "sales-playbook"),
    ("carol", "How much does the Advanced Security add-on cost?", ["12 usd"], "product-pricing-faq"),
    ("bob", "How much is the on-call stipend?", ["300"], "incident-response-runbook"),
    ("dave", "What command rolls back a service?", ["foundry rollback"], "deployment-guide"),
    ("frank", "How many days of paid annual leave do full-time employees get?", ["25 days"], "employee-handbook"),
    ("frank", "What is the hotel cap in high-cost cities?", ["320"], "travel-expense-policy"),
]


def _texts() -> dict[str, str]:
    t = {d["slug"]: d["body"] for d in DOCS}
    from app.ingest.pipeline import _record_text

    for c in CSVS:
        t[c["slug"]] = "\n".join(_record_text(c["slug"], dict(zip(c["header"], r)), c["title"]) for r in c["rows"])
    return t


def _flatten_tables(text: str) -> str:
    """Mirror how loaders render tables so table evidence strings can be validated."""
    out = []
    lines = text.splitlines()
    header = None
    for ln in lines:
        if ln.startswith("|"):
            cells = [c.strip() for c in ln.strip().strip("|").split("|")]
            out.append(" | ".join(cells))
            if header is None:
                header = cells
            else:
                out.append("; ".join(f"{h}: {v}" for h, v in zip(header, cells)))
        else:
            header = None
            out.append(ln)
    return "\n".join(out)


def build() -> list[dict]:
    items: list[dict] = []

    def add(cat, user, q, ans, must, docs, ev, forbidden=None):
        items.append({
            "id": f"q{len(items) + 1:03d}", "category": cat, "user": user, "question": q,
            "reference_answer": ans, "must_include": must, "relevant_docs": docs,
            "evidence": ev, "forbidden": forbidden or [],
        })

    for u, q, a, m, d, e in F:
        add("factual", u, q, a, m, [d], [e])
    for u, q, a, m, d, e in TABLE:
        add("table", u, q, a, m, [d], [e])
    for u, q, a, m, d, e in STRUCT:
        add("structured", u, q, a, m, [d], [e])
    for u, q, a, m, d, e in MULTI:
        add("multi_hop", u, q, a, m, d, e)
    for u, q, a, m, d, e in CATALOG:
        add("catalog", u, q, a, m, d, e)
    for u, q in UNANSWERABLE:
        add("unanswerable", u, q, "Should abstain: not covered by any document.", [], [], [])
    for u, q, forb, d in ACCESS_DENIED:
        add("access_denied", u, q, "Should abstain: the answer is in a document this user cannot access.",
            [], [], [], forbidden=forb)
        items[-1]["restricted_doc"] = d
    return items


def validate(items: list[dict]) -> list[str]:
    from scripts.sample_corpus import USERS

    texts = {k: " ".join(_flatten_tables(v).split()) for k, v in _texts().items()}
    acl = {d["slug"]: set(d["groups"]) for d in DOCS} | {c["slug"]: set(c["groups"]) for c in CSVS}
    ugroups = {u["name"]: set(u["groups"]) for u in USERS}
    errs = []
    for it in items:
        g = ugroups[it["user"]]
        for d in it["relevant_docs"]:
            if not acl[d] & g:
                errs.append(f"{it['id']}: user {it['user']} cannot read relevant doc {d}")
        if it.get("restricted_doc") and acl[it["restricted_doc"]] & g:
            errs.append(f"{it['id']}: user {it['user']} CAN read {it['restricted_doc']} (not access_denied)")
        for ev in it["evidence"]:
            ev_n = " ".join(ev.split())
            if not any(ev_n in texts[d] for d in it["relevant_docs"]):
                errs.append(f"{it['id']}: evidence not found: {ev!r}")
    return errs


def main() -> None:
    items = build()
    errs = validate(items)
    if errs:
        raise SystemExit("\n".join(errs))
    out = HERE / "benchmark.jsonl"
    with out.open("w", encoding="utf-8") as f:
        for it in items:
            f.write(json.dumps(it, ensure_ascii=False) + "\n")
    from collections import Counter
    print(f"wrote {len(items)} questions to {out}: {dict(Counter(i['category'] for i in items))}")


if __name__ == "__main__":
    main()

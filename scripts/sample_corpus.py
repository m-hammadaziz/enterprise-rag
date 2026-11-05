"""Source text for the synthetic 'Corvane Systems' enterprise corpus.

Corvane Systems is a fictional company. All names, figures and vendors are invented
for benchmarking. Content uses a tiny markdown dialect (#, ##, ###, '- ' bullets,
'| a | b |' tables) that build_sample_corpus.py renders to PDF / DOCX / HTML / MD.
"""

DOCS = [
# ---------------------------------------------------------------------------
dict(slug="employee-handbook", fmt="pdf", groups=["all-staff"],
     title="Corvane Employee Handbook 2026",
     description="Working hours, leave, remote work, conduct",
     body="""
# Corvane Employee Handbook 2026

## 1. Working Hours

Corvane's standard working week is 38 hours. Core collaboration hours are 10:00 to 15:00 in each employee's local time zone, and meetings should not be scheduled outside core hours without the attendee's agreement.

Overtime for non-exempt employees must be approved in advance by a manager and is paid at 1.5 times the base hourly rate.

## 2. Annual Leave

Full-time employees receive 25 days of paid annual leave per calendar year, accrued monthly. Employees with five or more years of service receive 28 days.

Up to 5 unused days may be carried over into the next year; carried-over days expire on 31 March. Leave requests of more than 10 consecutive working days must be submitted at least 30 days in advance.

## 3. Sick Leave

Employees receive 12 days of paid sick leave per year. A medical certificate is required for absences longer than 3 consecutive days.

## 4. Parental Leave

The primary caregiver receives 20 weeks of fully paid parental leave. The secondary caregiver receives 6 weeks of fully paid leave, which must be taken within 12 months of the birth or adoption.

## 5. Remote Work

Employees may work remotely up to 3 days per week with manager approval. Fully remote arrangements require approval from the department head and HR.

Working from another country is allowed for up to 30 days per calendar year and must be registered with HR at least 2 weeks before travel. Corvane provides a one-time home office stipend of 600 USD for new hires.

## 6. Public Holidays

Each office observes 11 public holidays per year according to its local calendar. In addition, the whole company closes for a winter shutdown between 27 and 31 December.

## 7. Code of Conduct

Gifts from vendors or customers worth more than 75 USD must be declared to the Compliance team within 5 working days. Concerns can be raised anonymously through the EthicsLine portal, which is operated by an independent third party.

## 8. Learning Budget

Every employee has an annual learning budget of 1,500 USD for courses, conferences and certifications. Unused learning budget does not roll over.
"""),
# ---------------------------------------------------------------------------
dict(slug="travel-expense-policy", fmt="docx", groups=["all-staff"],
     title="Travel and Expense Policy",
     description="Flights, hotels, per diem, approval limits, reimbursement",
     body="""
# Travel and Expense Policy

## Booking travel

All business travel must be booked through the Navio travel portal. Bookings made outside Navio are only reimbursed when the portal had no availability, and a screenshot proving this must be attached to the claim.

## Flights

Economy class is required for flights under 6 hours. Premium economy is allowed for flights of 6 hours or longer. Business class requires written approval from a Vice President.

## Hotels

The nightly hotel cap is 220 USD in standard cities and 320 USD in high-cost cities. The high-cost city list is New York, London, Zurich, Tokyo and San Francisco.

## Meals and per diem

The daily meal per diem is 75 USD for domestic travel and 95 USD for international travel. Alcohol is not reimbursable unless it is part of an approved client entertainment event.

## Approval limits

Expenses up to 500 USD are approved by the direct manager. Expenses between 500 and 5,000 USD require director approval. Anything above 5,000 USD requires approval from the CFO.

## Submitting claims

Expense claims must be submitted within 30 days of the expense date. Itemised receipts are required for every expense over 25 USD. Approved claims are reimbursed in the next payroll run.

## Corporate cards

Employees who travel more than four times a year are eligible for a corporate card. Personal use of the corporate card is prohibited, and repeated misuse leads to the card being withdrawn.
"""),
# ---------------------------------------------------------------------------
dict(slug="information-security-policy", fmt="pdf", groups=["all-staff", "contractors"],
     title="Information Security Policy",
     description="Passwords, MFA, devices, data classification, incident reporting",
     body="""
# Information Security Policy

## 1. Passwords and Authentication

Passwords must be at least 14 characters long. Multi-factor authentication is mandatory for all company systems, and hardware security keys are required for production access and for administrators.

Passwords must be stored in the company password manager, Keyhold. Sharing account credentials is prohibited.

## 2. Devices

Company laptops must have full-disk encryption enabled and must lock automatically after 5 minutes of inactivity. Operating system security patches must be installed within 14 days of release.

Personal devices may access email and chat only through the managed mobile app. Lost or stolen devices must be reported to IT within 1 hour.

## 3. Data Classification

Corvane uses four data classification levels: Public, Internal, Confidential and Restricted. Customer personal data is classified as Restricted. Restricted data must never be stored on removable media or in personal cloud storage.

## 4. Reporting Security Incidents

Suspected security incidents must be reported to the Security Operations Center within 1 hour of discovery via the #sec-incidents channel or by email to soc@corvane.example. Phishing emails should be reported with the Report Phish button.

## 5. Access Reviews

Managers review their team's access rights every quarter. Access for leavers is revoked within 4 hours of their departure.

## 6. Security Training

All staff and contractors must complete security awareness training within 14 days of joining and annually afterwards.
"""),
# ---------------------------------------------------------------------------
dict(slug="incident-response-runbook", fmt="md", groups=["engineering"],
     title="Incident Response Runbook",
     description="Severity levels, on-call, paging, postmortems",
     body="""
# Incident Response Runbook

## Severity levels

- SEV1: complete outage or data loss affecting customers. Response within 15 minutes, all hands, status page update within 30 minutes.
- SEV2: major feature degraded for many customers. Response within 30 minutes.
- SEV3: minor degradation or a single customer affected. Response within 4 business hours.

## On-call rotation

The primary on-call rotation is weekly and hands over every Monday at 10:00 UTC. Each team keeps a primary and a secondary on-call engineer. On-call engineers receive a stipend of 300 USD per week of on-call duty.

Pages are sent through PagerTree. If the primary does not acknowledge a page within 10 minutes, it escalates automatically to the secondary.

## Running an incident

For every SEV1 and SEV2 the on-call engineer opens a dedicated Slack channel named #inc-<date>-<short-name> and assigns an Incident Commander. The Incident Commander owns communication; engineers focus on mitigation.

Customer-facing updates are posted on status.corvane.example at least every 30 minutes during a SEV1.

## Postmortems

A blameless postmortem is required for every SEV1 and SEV2 and must be published within 5 business days of the incident. Action items are tracked in the RELIABILITY Jira project and must have an owner and a due date.

## Rollback first

When a deploy is the suspected cause, roll back first and investigate afterwards. Rollbacks do not require change approval.
"""),
# ---------------------------------------------------------------------------
dict(slug="deployment-guide", fmt="html", groups=["engineering"],
     title="Deployment Guide",
     description="Release process, canary, freeze windows, rollback",
     body="""
# Deployment Guide

## Release cadence

Production deploys run on a continuous release train. Services deploy through the Foundry pipeline, which runs unit tests, integration tests and a security scan before any production rollout.

Every change needs one approving code review. Changes to payment or authentication services need two approving reviews, one of them from a code owner.

## Canary rollout

New versions first receive 5 percent of traffic for 20 minutes. If the error rate stays below 1 percent and p95 latency does not increase by more than 10 percent, the rollout proceeds to 25 percent, then 50 percent, then 100 percent.

Automated canary analysis aborts and rolls back the deploy if either threshold is breached.

## Deploy freezes

There are no production deploys on Fridays after 14:00 UTC or during weekends. A company-wide code freeze applies from 20 December to 3 January. Emergency fixes during a freeze need approval from the VP of Engineering.

## Feature flags

New user-facing features must ship behind a feature flag managed in Flagpole. Flags that have been fully rolled out for more than 60 days must be removed from the code.

## Rollback

Any engineer can roll back a service with the command foundry rollback <service> <version>. A rollback typically completes in under 4 minutes.
"""),
# ---------------------------------------------------------------------------
dict(slug="platform-architecture", fmt="docx", groups=["engineering"],
     title="Platform Architecture Overview",
     description="Services, data stores, regions, SLOs",
     body="""
# Platform Architecture Overview

## Hosting and regions

The Corvane platform runs on Kubernetes clusters hosted by Skyline Cloud Hosting. The primary region is eu-central (Frankfurt) and the disaster recovery region is eu-west (Dublin).

The recovery point objective (RPO) is 15 minutes and the recovery time objective (RTO) is 4 hours. Disaster recovery failover is tested twice a year.

## Core services

- Gateway: public API gateway, written in Go, handles authentication and rate limiting.
- Ledger: billing and invoicing service, written in Kotlin.
- Insight: analytics query engine, written in Rust.
- Notifier: email and webhook delivery, written in Python.

## Data stores

The primary transactional database is PostgreSQL 16 with streaming replication. Analytics data is stored in ClickHouse. Redis is used for caching and rate limiting. Object storage holds customer file uploads with 30-day versioning.

## Service level objectives

The public API has an availability SLO of 99.95 percent per calendar month. The p95 latency target for API requests is 300 milliseconds.

## Rate limits

The default API rate limit is 1,000 requests per minute per customer. Enterprise plan customers have a limit of 5,000 requests per minute.
"""),
# ---------------------------------------------------------------------------
dict(slug="q3-2026-financial-report", fmt="pdf", groups=["finance", "exec"],
     title="Q3 2026 Financial Report",
     description="Revenue, margin, operating expenses, cash for Q3 2026",
     body="""
# Q3 2026 Financial Report

## 1. Summary

Corvane recorded total revenue of 18.4 million USD in Q3 2026, an increase of 22 percent year over year. Subscription revenue was 16.1 million USD and professional services revenue was 2.3 million USD.

## 2. Margins

Gross margin was 74 percent, up from 71 percent in Q2 2026, mainly due to lower hosting costs after the renegotiated Skyline contract. Operating margin was negative 6 percent.

## 3. Operating Expenses

Total operating expenses were 14.7 million USD. Research and development was the largest category at 6.2 million USD, followed by sales and marketing at 5.4 million USD and general and administrative at 3.1 million USD.

## 4. Cash and Runway

Cash and cash equivalents at the end of Q3 2026 were 41.5 million USD. Net cash burn in the quarter was 2.8 million USD, which gives an estimated runway of more than 14 quarters at the current burn rate.

## 5. Customers

The company ended the quarter with 1,240 paying customers, including 86 enterprise customers. Net revenue retention was 112 percent.

## 6. Outlook

Management expects Q4 2026 revenue between 19.5 and 20.2 million USD and targets reaching operating break-even in Q2 2027.
"""),
# ---------------------------------------------------------------------------
dict(slug="fy2027-budget-plan", fmt="docx", groups=["finance", "exec"],
     title="FY2027 Budget Plan",
     description="Department budgets and hiring plan for fiscal year 2027",
     body="""
# FY2027 Budget Plan

## Overview

The approved total operating budget for fiscal year 2027 is 64 million USD, a 9 percent increase over fiscal year 2026. Fiscal year 2027 runs from 1 February 2027 to 31 January 2028.

## Department budgets

| Department | Budget (USD) | Planned new hires |
| Engineering | 26.5 million | 34 |
| Sales and Marketing | 20.0 million | 22 |
| Customer Success | 6.5 million | 9 |
| General and Administrative | 11.0 million | 6 |

## Hiring plan

The plan adds 71 new hires in total, bringing year-end headcount to approximately 520 employees. Hiring is front-loaded: 60 percent of new roles should be filled by the end of Q2.

## Contingency

A contingency reserve of 2.5 million USD is held centrally by the CFO. Any department reallocation above 250,000 USD requires approval from the executive team.

## Travel

The company-wide travel budget is capped at 1.8 million USD for the year.
"""),
# ---------------------------------------------------------------------------
dict(slug="data-retention-policy", fmt="html", groups=["all-staff"],
     title="Data Retention Policy",
     description="How long records are kept and how they are deleted",
     body="""
# Data Retention Policy

## Purpose

This policy defines how long Corvane keeps business records and customer data, and how data is deleted at the end of its retention period. The Legal team owns this policy and reviews it every year.

## Retention periods

| Record type | Retention period |
| Financial and tax records | 10 years |
| Employee personnel files | 7 years after employment ends |
| Customer contracts | 6 years after contract end |
| Application logs | 90 days |
| Security audit logs | 2 years |
| Recruiting records of unsuccessful candidates | 12 months |

## Customer data after termination

After a customer terminates, their production data is deleted within 60 days. Backups containing the data age out within a further 35 days.

## Legal hold

A legal hold issued by the Legal team suspends all deletion for the affected records until the hold is released in writing.

## Deletion requests

Data subject deletion requests must be completed within 30 days of receipt and logged in the privacy request tracker.
"""),
# ---------------------------------------------------------------------------
dict(slug="skyline-hosting-contract-summary", fmt="pdf", groups=["legal"],
     title="Skyline Cloud Hosting Contract Summary",
     description="Key terms of the master services agreement with Skyline Cloud Hosting",
     body="""
# Skyline Cloud Hosting Contract Summary

## 1. Parties and Term

The master services agreement between Corvane Systems and Skyline Cloud Hosting was renegotiated effective 1 July 2026 for a term of 3 years, ending on 30 June 2029.

## 2. Commercial Terms

Corvane commits to a minimum spend of 2.4 million USD per contract year. In exchange Skyline grants an 18 percent discount on list prices. Unused committed spend does not roll over to the next year.

## 3. Service Levels

Skyline guarantees 99.99 percent monthly uptime for compute. If uptime falls below the guarantee, Corvane receives service credits of 10 percent of the monthly fee, rising to 25 percent below 99.5 percent uptime.

## 4. Liability

Skyline's liability is capped at 12 months of fees paid. The cap does not apply to data protection breaches or gross negligence.

## 5. Termination

Either party may terminate for convenience with 180 days written notice after the first contract year. Termination for material breach requires a 30-day cure period.

## 6. Data Protection

All customer data must remain in the European Union. Skyline must notify Corvane of a personal data breach within 24 hours.
"""),
# ---------------------------------------------------------------------------
dict(slug="sales-playbook", fmt="md", groups=["sales"],
     title="Sales Playbook",
     description="Deal stages, discounts, approvals, commissions",
     body="""
# Sales Playbook

## Deal stages

Corvane uses five opportunity stages: Discovery, Qualification, Technical Validation, Proposal and Negotiation. An opportunity may only move to Proposal after the MEDDIC qualification checklist is complete.

## Discount approval

- Discounts up to 10 percent can be approved by the account executive.
- Discounts from 10 to 20 percent need approval from the regional sales director.
- Discounts above 20 percent need approval from the Chief Revenue Officer.
- Multi-year contracts may receive an additional 5 percent discount per extra committed year, up to a maximum of 10 percent.

## Contract terms

The standard contract term is 12 months with annual upfront payment. Payment terms longer than net 45 require approval from Finance.

## Commissions

Account executives earn 10 percent commission on first-year annual contract value for new business. Commission is paid after the customer's first invoice is paid. Renewals pay 3 percent commission.

## Free trials

Self-serve trials last 14 days. Sales-assisted proofs of concept may last up to 30 days and require a written success plan.
"""),
# ---------------------------------------------------------------------------
dict(slug="product-pricing-faq", fmt="html", groups=["sales"],
     title="Product Pricing FAQ",
     description="Plans, list prices, add-ons",
     body="""
# Product Pricing FAQ

## What plans do we sell?

Corvane Insight is sold in three plans: Starter, Growth and Enterprise. Starter costs 49 USD per user per month, Growth costs 99 USD per user per month, and Enterprise pricing is quoted individually with a minimum of 50 seats.

## Is there an annual discount?

Customers who pay annually receive a 15 percent discount compared to monthly billing on Starter and Growth plans.

## What add-ons are available?

The Advanced Security add-on costs 12 USD per user per month and includes SSO enforcement, audit log export and customer-managed encryption keys. Premium Support costs 20 percent of the annual subscription value and includes a 1-hour response time for critical issues.

## What does the free plan include?

There is no free plan. Prospects can start a 14-day free trial of the Growth plan without a credit card.

## Do nonprofits get a discount?

Registered nonprofit organisations receive a 30 percent discount on Starter and Growth plans.
"""),
# ---------------------------------------------------------------------------
dict(slug="project-atlas-board-memo", fmt="docx", groups=["exec"],
     title="Board Memo: Project Atlas",
     description="Confidential acquisition proposal",
     body="""
# Board Memo: Project Atlas

## Strictly confidential

This memo is restricted to the executive team and the board of directors. Do not forward.

## Proposal

Project Atlas is the proposed acquisition of Brightline Data, a data-quality startup with 45 employees based in Lisbon. The proposed purchase price is 38 million USD, paid 70 percent in cash and 30 percent in Corvane stock.

## Rationale

Brightline's anomaly detection technology would be integrated into Corvane Insight and is expected to add 4 million USD of annual recurring revenue within 18 months of closing.

## Timeline

The board vote is scheduled for 12 November 2026. If approved, the target closing date is 31 January 2027.

## Risks

The main risks are retention of Brightline's engineering team and integration effort. A retention pool of 3 million USD is proposed for key Brightline employees.
"""),
# ---------------------------------------------------------------------------
dict(slug="contractor-onboarding-guide", fmt="md", groups=["contractors", "all-staff"],
     title="Contractor Onboarding Guide",
     description="Access, timesheets, invoicing and offboarding for contractors",
     body="""
# Contractor Onboarding Guide

## Before day one

Contractors must sign the Corvane NDA and the contractor agreement before receiving any system access. Accounts are created by IT using the contractor's corvane-ext.example email address.

## Access

Contractor accounts expire automatically after 90 days and must be renewed by the sponsoring manager. Contractors do not receive access to production systems unless a security exception is approved.

## Timesheets and invoicing

Timesheets are submitted weekly in the Tempo tool by Monday 12:00 for the previous week. Invoices are submitted monthly and are paid within 30 days of receipt.

## Equipment

Contractors use their own devices unless the engagement lasts longer than 6 months, in which case a company laptop can be requested.

## Offboarding

On the last day the sponsoring manager files an offboarding ticket. All company data must be deleted from personal devices, and the contractor confirms this in writing.
"""),
# ---------------------------------------------------------------------------
dict(slug="benefits-overview", fmt="html", groups=["all-staff"],
     title="Benefits Overview 2026",
     description="Health insurance, pension, wellness, equipment",
     body="""
# Benefits Overview 2026

## Health insurance

Corvane pays 100 percent of the health insurance premium for employees and 75 percent for dependants. The insurance provider in the United States is Northstar Health; other countries use local providers.

## Retirement

In the United States, Corvane matches 401(k) contributions dollar for dollar up to 4 percent of base salary. Matching contributions vest immediately. In other countries, the company contributes 5 percent of base salary to the local pension plan.

## Wellness

Every employee receives a wellness allowance of 50 USD per month, which can be spent on gym memberships, fitness classes or mental health apps. Employees and their families also have free access to the Calmwave counselling service.

## Equipment

Employees can choose a MacBook Pro or a Lenovo ThinkPad, and laptops are refreshed every 3 years.

## Employee referral bonus

Employees who refer a candidate who is hired and stays for 90 days receive a referral bonus of 3,000 USD. For engineering roles the referral bonus is 5,000 USD.
"""),
]

# Structured datasets (become rows in the `records` table).
CSVS = [
    dict(slug="kpi-monthly-2026", groups=["all-staff"], title="Company KPIs by Month (2026)",
         description="Monthly ARR, logo churn, NPS and API uptime",
         header=["month", "arr_musd", "logo_churn_pct", "nps", "api_uptime_pct", "support_tickets"],
         rows=[
             ["2026-01", "62.1", "1.1", "41", "99.97", "1830"],
             ["2026-02", "63.0", "0.9", "43", "99.99", "1712"],
             ["2026-03", "64.4", "1.3", "40", "99.91", "1955"],
             ["2026-04", "65.2", "1.0", "44", "99.98", "1804"],
             ["2026-05", "66.9", "0.8", "46", "99.96", "1690"],
             ["2026-06", "68.0", "1.2", "45", "99.93", "1748"],
             ["2026-07", "69.8", "0.7", "47", "99.99", "1622"],
             ["2026-08", "71.1", "0.9", "48", "99.88", "1901"],
             ["2026-09", "72.6", "0.8", "49", "99.97", "1655"],
         ]),
    dict(slug="office-locations", groups=["all-staff"], title="Office Locations and Headcount",
         description="Offices, cities, office leads and headcount",
         header=["office", "city", "country", "opened", "headcount", "office_lead_role"],
         rows=[
             ["Corvane HQ", "Berlin", "Germany", "2016", "182", "Chief Operating Officer"],
             ["Corvane Lisbon", "Lisbon", "Portugal", "2019", "96", "Head of Engineering Lisbon"],
             ["Corvane Austin", "Austin", "United States", "2020", "88", "VP Sales Americas"],
             ["Corvane Toronto", "Toronto", "Canada", "2022", "41", "Director of Customer Success"],
             ["Corvane Singapore", "Singapore", "Singapore", "2024", "27", "Head of APAC"],
             ["Corvane Krakow", "Krakow", "Poland", "2025", "15", "Engineering Manager Krakow"],
         ]),
    dict(slug="compensation-bands", groups=["hr", "exec"], title="Compensation Bands 2026 (Engineering)",
         description="Salary ranges per engineering level, Berlin baseline",
         header=["level", "title", "salary_min_eur", "salary_max_eur", "equity_units"],
         rows=[
             ["L1", "Associate Engineer", "52000", "64000", "200"],
             ["L2", "Software Engineer", "62000", "78000", "400"],
             ["L3", "Senior Software Engineer", "76000", "96000", "800"],
             ["L4", "Staff Engineer", "94000", "118000", "1600"],
             ["L5", "Principal Engineer", "115000", "140000", "3000"],
         ]),
]

USERS = [
    dict(name="hammad", groups=["all-staff", "engineering", "finance", "legal", "hr", "sales", "exec"],
         is_admin=True, demo_api_key="demo-hammad"),
    dict(name="alice", groups=["all-staff", "engineering"], demo_api_key="demo-alice"),
    dict(name="bob", groups=["all-staff", "finance"], demo_api_key="demo-bob"),
    dict(name="carol", groups=["all-staff", "legal", "hr"], demo_api_key="demo-carol"),
    dict(name="dave", groups=["all-staff", "sales"], demo_api_key="demo-dave"),
    dict(name="erin", groups=["all-staff", "engineering", "finance", "legal", "hr", "sales", "exec"],
         is_admin=True, demo_api_key="demo-erin"),
    dict(name="frank", groups=["contractors"], demo_api_key="demo-frank"),
]

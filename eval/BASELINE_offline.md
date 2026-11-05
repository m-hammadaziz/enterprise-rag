# Benchmark report — 20261103-002138

## Configuration

| setting | value |
|---|---|
| questions | `215` |
| llm | `none (extractive)` |
| embed_backend | `hash:hash-384` |
| rerank_backend | `lexical:` |
| agent_mode | `hybrid_rerank` |
| final_top_k | `6` |
| min_evidence_score | `0.45` |

## Retrieval quality (ablation)

Relevance = retrieved chunk contains a gold evidence span. Answerable questions only.

| mode | n | hit@1 | hit@5 | recall@5 | recall@10 | MRR@10 | nDCG@10 | doc_hit@5 | p50 ms | p95 ms |
|---|---|---|---|---|---|---|---|---|---|---|
| vector | 172 | 86.0% | 100.0% | 99.7% | 99.7% | 0.920 | 0.934 | 100.0% | 3 | 6 |
| keyword | 172 | 87.8% | 98.8% | 98.0% | 99.7% | 0.926 | 0.938 | 100.0% | 3 | 5 |
| hybrid | 172 | 87.8% | 100.0% | 99.7% | 99.7% | 0.934 | 0.945 | 100.0% | 5 | 7 |
| hybrid_rerank | 172 | 97.1% | 100.0% | 99.7% | 100.0% | 0.984 | 0.981 | 100.0% | 8 | 11 |

## End-to-end agent

| metric | value |
|---|---|
| questions | 215 (errors: 0) |
| **overall accuracy** | **84.2%** |
| answerable accuracy (all required facts present) | 84.0% |
| answerable fact coverage | 86.0% |
| false abstention rate (answerable) | 5.1% |
| abstention recall (unanswerable + access denied) | 85.0% |
| abstention precision | 79.1% |
| hallucination rate on negatives | 15.0% |
| **ACL leak rate** | **0.0%** (violations in retrieval: 0) |
| citation precision (evidence-level) | 95.2% |
| citation precision (document-level) | 97.9% |
| citation recall | 95.2% |
| answers with ≥1 citation | 100.0% |

### Latency and cost

| metric | value |
|---|---|
| latency p50 / p95 / mean | 12 / 28 / 14 ms |
| stage means (ms) | db_ms=6.5, embed_ms=0.4, generate_ms=0.3, plan_ms=0.0, rerank_ms=2.7, retrieve_ms=9.6, total_ms=14.0 |
| LLM calls per question | 0.00 |
| tokens in / out | 0 / 0 |
| cost total / per question | $0.0000 / $0.00000 |

### By category

| category | n | accuracy | abstain rate | p50 ms |
|---|---|---|---|---|
| access_denied | 20 | 95.0% | 95.0% | 22 |
| catalog | 3 | 100.0% | 0.0% | 14 |
| factual | 143 | 87.4% | 4.2% | 10 |
| multi_hop | 10 | 0.0% | 30.0% | 14 |
| structured | 15 | 100.0% | 0.0% | 12 |
| table | 4 | 100.0% | 0.0% | 9 |
| unanswerable | 20 | 75.0% | 75.0% | 24 |

### Failures (34)

| id | category | question | answer |
|---|---|---|---|
| q027 | factual | Which cities count as high-cost for hotel limits? | The nightly hotel cap is 220 USD in standard cities and 320 USD in high-cost cities. [S1] |
| q030 | factual | Who approves an expense of 3,000 USD? | Employees who refer a candidate who is hired and stays for 90 days receive a referral bonus of 3,000 USD. [S4] |
| q031 | factual | Who has to approve expenses above 5,000 USD? | Expenses between 500 and 5,000 USD require director approval. [S1] |
| q035 | factual | What is the minimum password length? | I couldn't find enough evidence in the documents you have access to to answer this question, so I won't guess. Try rephrasing, or ask the do |
| q047 | factual | What is the response time for a SEV1 incident? | For every SEV1 and SEV2 the on-call engineer opens a dedicated Slack channel named #inc-<date>-<short-name> and assigns an Incident Commande |
| q048 | factual | What is the response time target for SEV2 incidents? | I couldn't find enough evidence in the documents you have access to to answer this question, so I won't guess. Try rephrasing, or ask the do |
| q052 | factual | Which tool sends pages to on-call engineers? | I couldn't find enough evidence in the documents you have access to to answer this question, so I won't guess. Try rephrasing, or ask the do |
| q053 | factual | After how long does an unacknowledged page escalate to the secondary? | I couldn't find enough evidence in the documents you have access to to answer this question, so I won't guess. Try rephrasing, or ask the do |
| q054 | factual | How often must the status page be updated during a SEV1? | I couldn't find enough evidence in the documents you have access to to answer this question, so I won't guess. Try rephrasing, or ask the do |
| q061 | factual | What error rate threshold does canary analysis use? | Automated canary analysis aborts and rolls back the deploy if either threshold is breached. [S1] |
| q077 | factual | What API rate limit do Enterprise customers get? | The default API rate limit is 1,000 requests per minute per customer. [S1] |
| q080 | factual | What was subscription revenue in Q3 2026? | Corvane recorded total revenue of 18.4 million USD in Q3 2026, an increase of 22 percent year over year. [S1] |
| q086 | factual | How many paying customers did Corvane have at the end of Q3? | This policy defines how long Corvane keeps business records and customer data, and how data is deleted at the end of its retention period. [ |
| q094 | factual | How many new hires are planned in FY2027? | Department: Engineering; Budget (USD): 26.5 million; Planned new hires: 34 [S1] Department: Sales and Marketing; Budget (USD): 20.0 million; |
| q099 | factual | How long are personnel files kept after someone leaves? | I couldn't find enough evidence in the documents you have access to to answer this question, so I won't guess. Try rephrasing, or ask the do |
| q104 | factual | Who owns the data retention policy? | This policy defines how long Corvane keeps business records and customer data, and how data is deleted at the end of its retention period. [ |
| q114 | factual | Who can approve a 15 percent discount? | Customers who pay annually receive a 15 percent discount compared to monthly billing on Starter and Growth plans. [S1] |
| q122 | factual | What is the Starter plan price? | Corvane Insight is sold in three plans: Starter, Growth and Enterprise. [S1] Registered nonprofit organisations receive a 30 percent discoun |
| q163 | multi_hop | Which cloud provider hosts the platform, and what uptime does that provider guar | The Corvane platform runs on Kubernetes clusters hosted by Skyline Cloud Hosting. [S2] |
| q164 | multi_hop | Why did gross margin improve in Q3 2026, and what discount does the renegotiated | Gross margin was 74 percent, up from 71 percent in Q2 2026, mainly due to lower hosting costs after the renegotiated Skyline contract. [S1] |
| q165 | multi_hop | What is the SEV1 response time and how many reviews does a change to the authent | I couldn't find enough evidence in the documents you have access to to answer this question, so I won't guess. Try rephrasing, or ask the do |
| q166 | multi_hop | Compare the annual leave and the sick leave allowance for full-time employees. | Full-time employees receive 25 days of paid annual leave per calendar year, accrued monthly. [S1] |
| q167 | multi_hop | What is the hotel cap in Tokyo and the international meal per diem? | The daily meal per diem is 75 USD for domestic travel and 95 USD for international travel. [S1] |
| q168 | multi_hop | How many employees does Brightline Data have and how many people work in Corvane | Project Atlas is the proposed acquisition of Brightline Data, a data-quality startup with 45 employees based in Lisbon. [S1] |
| q169 | multi_hop | What were Q3 2026 revenue and Q3 net cash burn? | Net cash burn in the quarter was 2.8 million USD, which gives an estimated runway of more than 14 quarters at the current burn rate. [S1] |
| q170 | multi_hop | How quickly must a security incident be reported and how quickly must a SEV2 be  | I couldn't find enough evidence in the documents you have access to to answer this question, so I won't guess. Try rephrasing, or ask the do |
| q171 | multi_hop | What is the Growth plan list price and what discount can an account executive ap | I couldn't find enough evidence in the documents you have access to to answer this question, so I won't guess. Try rephrasing, or ask the do |
| q172 | multi_hop | How long are security audit logs kept, and how long are application logs kept? | Security audit logs / 2 years [S1] |
| q177 | unanswerable | What was revenue in Q3 2024? | Corvane recorded total revenue of 18.4 million USD in Q3 2026, an increase of 22 percent year over year. [S1] |
| q178 | unanswerable | How many days of paid bereavement leave do employees get? | Employees receive 12 days of paid sick leave per year. [S1] Full-time employees receive 25 days of paid annual leave per calendar year, accr |
| q180 | unanswerable | Which Kubernetes version do our clusters run? | The Corvane platform runs on Kubernetes clusters hosted by Skyline Cloud Hosting. [S1] |
| q188 | unanswerable | What was the NPS in December 2026? | kpi-monthly-2026 (Company KPIs by Month (2026)): month: 2026-01 (January 2026); arr musd: 62.1; logo churn pct: 1.1; nps: 41; api uptime pct |
| q190 | unanswerable | How many employees work in the Tokyo office? | Employees may work remotely up to 3 days per week with manager approval. [S1] |
| q212 | access_denied | How much is the on-call stipend? | Corvane provides a one-time home office stipend of 600 USD for new hires. [S1] |

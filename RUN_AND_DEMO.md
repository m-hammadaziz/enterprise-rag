# Run & Demo Guide (Windows)

A step-by-step guide to running this project on your own laptop, understanding what each step does, and presenting it in a 5-minute demo.

> Everything below is typed in the **VS Code terminal** (PowerShell) inside `E:\enterprise-rag`.
> Open it with **View → Terminal** (or press <kbd>Ctrl</kbd>+<kbd>`</kbd>).

---

## 0. What you need (already installed on your laptop)

| Tool | Why | Check it works |
|---|---|---|
| **Docker Desktop** | runs the PostgreSQL + pgvector database | open Docker Desktop and wait until it says *Engine running* |
| **Python 3.13** | runs the API, ingestion, tests, benchmark | `python --version` |
| **VS Code** | editor + terminal | — |
| **Groq API key** | the LLM that writes answers | already in your `.env` |

---

## 1. One-time setup (≈5–10 minutes)

### 1.1 Open the project
In VS Code use **File → Open Folder… → `E:\enterprise-rag`**. If a yellow bar says *Restricted Mode*, click **Trust**.

### 1.2 Activate the virtual environment
A virtual environment (`.venv`) is a private folder of Python packages just for this project.

```powershell
.\.venv\Scripts\Activate.ps1
```
Your prompt should now start with `(.venv)`.

> **If you see "running scripts is disabled on this system"**, run this once and then try again:
> `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`
>
> **If `.venv` is missing or broken**, create a fresh one: `python -m venv .venv`

### 1.3 Install the packages
```powershell
pip install -r requirements-dev.txt
```
This downloads FastAPI, LangGraph, the Postgres driver, PDF/Word readers and PyTorch + sentence-transformers (the AI models), about 1 GB in total. You only do it once.

### 1.4 Check your `.env`
`.env` holds your settings and secrets. **Never commit or share it.** Yours should contain at least:

```ini
DATABASE_URL=postgresql://rag:rag@localhost:5432/rag
GROQ_API_KEY=gsk_...your key...
GROQ_BASE_URL=https://api.groq.com/openai/v1
LLM_MODEL=openai/gpt-oss-120b
EMBED_MODEL=BAAI/bge-small-en-v1.5
```

Optional: for accurate cost numbers, add your model's prices from Groq's pricing page (USD per 1 million tokens):
```ini
LLM_INPUT_PRICE_PER_MTOK=...
LLM_OUTPUT_PRICE_PER_MTOK=...
```

See `.env.example` for every option.

---

## 2. Start everything (do this every time)

### 2.1 Start the database
```powershell
docker compose up -d db
docker ps          # you should see "rag-db" ... "Up"
```
`-d` runs it in the background. The database keeps its data between restarts.

### 2.2 Load the sample documents and users (first time only)
```powershell
python -m scripts.ingest --manifest data/sample/manifest.json
python -m scripts.seed_users
```

**What happens:** 18 files (PDF, Word, HTML, Markdown, CSV) for the fictional company *Corvane Systems* are read, cut into chunks, turned into vectors by the **bge-small** model, and stored in Postgres with their **allowed groups**. The first run downloads the embedding model (~130 MB).

You'll see lines like `[created] #1 v1 'Corvane Employee Handbook 2026': 8 chunks`. Run the same command again and every line says `unchanged`, because ingestion is idempotent.

`seed_users` creates seven demo users and their API keys:

| API key | user | can read |
|---|---|---|
| `demo-hammad` | hammad | everything + exec (**admin**, project owner) |
| `demo-alice` | alice | all-staff, engineering |
| `demo-bob` | bob | all-staff, finance |
| `demo-carol` | carol | all-staff, legal, hr |
| `demo-dave` | dave | all-staff, sales |
| `demo-erin` | erin | everything + exec (**admin**) |
| `demo-frank` | frank | contractors only |

### 2.3 Start the API
```powershell
uvicorn app.main:app --reload
```
Wait for `Application startup complete`. **Leave this terminal open**: it is your server. Open a **second terminal** (the **+** button in the terminal panel) for the next steps, and activate the venv there too (`.\.venv\Scripts\Activate.ps1`).

---

## 3. Use it

### 3.1 The dashboard (best for demos)
Open **http://localhost:8000** in Edge.

- **Left:** choose who is asking (alice, bob, …). Below that you see the documents that person can read.
- **Middle:** click an example question or type your own and press **Enter**.
- **Answer card:** green = answered, with numbered sources (click a number to jump to its source). Orange = refused, with the reason.
- **"How this answer was produced":** the searches the agent ran, where the time went, tokens and cost.
- **Compare all users** (top right): asks the same question as all 7 people at once, the best way to show permissions.

### 3.2 The raw API page (for developers)
Open **http://localhost:8000/docs**. This is an interactive page that FastAPI generates automatically.

1. Click **POST /ask → Try it out**.
2. In **X-API-Key** type `demo-bob`.
3. In the body put:
   ```json
   { "question": "What was total revenue in Q3 2026?" }
   ```
4. Click **Execute**. The first question takes longer because the reranker model downloads (~90 MB) and the models load.

Look at the response:

| field | meaning |
|---|---|
| `answer` | the text, with `[S1]` style citation markers |
| `citations` | title, section, page and snippet of each source used |
| `abstained` | `true` = it refused because it lacked evidence |
| `tool_calls` | which data sources the agent chose |
| `timings` | milliseconds per step (plan, embed, db, rerank, generate) |
| `usage` | tokens and cost in USD |

Now change the key to `demo-alice` and ask the **same** question. Alice is not in finance, so the agent refuses and doesn't reveal that the report exists.

Other endpoints to try: **GET /me**, **GET /documents**, **POST /search**, **GET /health**.

### 3.3 From PowerShell
```powershell
$h = @{ "X-API-Key" = "demo-dave"; "Content-Type" = "application/json" }
$body = '{"question":"What is the headcount of the Lisbon office?"}'
(Invoke-RestMethod -Method Post http://localhost:8000/ask -Headers $h -Body $body) | ConvertTo-Json -Depth 5
```

### 3.4 The automatic demo script
With the API running, in your second terminal:
```powershell
python -m scripts.demo
```
This plays the full story: cited answers, permission differences, refusal, CSV data, the document catalog, search internals, and a live upload → access change → delete.

---

## 4. Check quality

### 4.1 Tests (about 2 seconds)
```powershell
pytest
```
You should see **44 passed**. Tests run in offline mode against a separate `rag_test` database, so they never touch your real data and need no API key.

### 4.2 Benchmark
```powershell
python -m eval.run_benchmark --skip-agent            # search quality only, free, ~1 min
python -m eval.run_benchmark --limit 40              # quick end-to-end run with the LLM
python -m eval.run_benchmark --judge                 # all 215 questions + LLM-as-judge
```
Open the report it prints: `eval/reports/<date-time>/report.md`. In VS Code, right-click it and choose **Open Preview**.

> Groq's free tier has rate limits. The full run makes about 500 LLM calls, so if you see `429` errors, use `--limit 40` or wait a minute and rerun.

---

## 5. A 5-minute demo talk track

| # | Show | Say |
|---|---|---|
| 1 | README architecture diagram | "Employees ask questions; the agent searches only what they're allowed to see, cites sources, and refuses rather than guesses." |
| 2 | Dashboard (`localhost:8000`) as **bob**: Q3 revenue | "Answer with a citation to the exact report, section and page." |
| 3 | Switch on **Compare all users**, ask it again | "Alice isn't in finance. The filter runs **inside the SQL query**, so restricted text never reaches the LLM. No leak, and she isn't even told the document exists." |
| 4 | **alice**: "What is the Wi-Fi password for the Berlin office?" | "Nothing answers this, so it abstains instead of hallucinating." |
| 5 | **dave**: "Headcount of the Lisbon office?" | "The agent picked the structured-data tool: this answer comes from a CSV, not a document." |
| 6 | Change **Search mode** (under the box) to *Vector only*, then *Hybrid + rerank*, and open "How this answer was produced" | "Vector plus keyword search, fused with RRF, then a cross-encoder reranks the results. Look at the `ranks`." |
| 7 | `python -m scripts.demo` (lifecycle part) | "An admin uploads a document for engineering, then grants finance access. Answers change immediately." |
| 8 | `eval/reports/.../report.md` | "215-question benchmark: retrieval ablation, accuracy, abstention, ACL leak rate, citation precision, latency p95, cost." |
| 9 | `app/agent.py` top comment | "The LangGraph flow: plan → retrieve → evidence gate → generate → validate citations, with one retry before abstaining." |

---

## 6. Stop and restart

| To | Do |
|---|---|
| stop the API | press <kbd>Ctrl</kbd>+<kbd>C</kbd> in the uvicorn terminal |
| stop the database | `docker compose stop db` |
| start again next time | Docker Desktop → `docker compose up -d db` → activate venv → `uvicorn app.main:app --reload` (no need to ingest again) |
| wipe the database completely | `docker compose down -v`, then redo step 2.2 |

---

## 7. Troubleshooting

| Problem | Fix |
|---|---|
| `docker: command not found` / cannot connect | start **Docker Desktop** and wait for *Engine running* |
| `port 5432 is already allocated` | another Postgres is running. Stop it, or change compose to `"5433:5432"` and `DATABASE_URL` to `...localhost:5433/rag` |
| `connection refused` on `localhost:5432` | the DB isn't up yet: `docker ps`, wait 10 s |
| `Invalid API key` (401) | header must be exactly `X-API-Key: demo-alice`, and you must run `python -m scripts.seed_users` first |
| every answer abstains | data not loaded: run step 2.2 and check `GET /health` shows `"documents": 18` |
| strange answers after switching models | re-run ingestion (step 2.2). It re-embeds automatically when the model changes. |
| `429 Too Many Requests` | Groq rate limit: wait a minute, use `--limit` |
| first request is slow | models load on first use, and later requests are fast |

---

## 8. Learn by changing things

1. **Add your own document:** put a PDF in `data/raw/` and run
   `python -m scripts.ingest --path data/raw/yourfile.pdf --groups engineering`. Then ask about it as alice (sees it) and bob (doesn't).
2. **Change permissions live:** as erin, call **PATCH /documents/{id}/acl** with `{"allowed_groups": ["finance"]}` and watch who can answer.
3. **Tune retrieval:** in `.env` set `FINAL_TOP_K=3` or `RERANK_BACKEND=none`, restart the API, rerun `python -m eval.run_benchmark --skip-agent` and compare the reports.
4. **Tune the refusal threshold:** raise `MIN_EVIDENCE_SCORE_CROSS_ENCODER` (e.g. `0.2`) and check the benchmark's *false abstention* vs *hallucination on negatives*. That trade-off is the core of RAG evaluation.
5. **Read the code in this order:** `app/main.py` → `app/agent.py` → `app/tools.py` → `app/retrieval.py` → `app/ingest/pipeline.py`.

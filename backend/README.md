# InternAssist — uAgents backend

InternAssist accepts a public job-posting URL, creates a resume-grounded cover letter, supports chat-based revisions, and generates a PDF from the **latest** draft.

## Requirements

- Python 3.11 (the pinned uAgents dependencies are intended for Python 3.11)
- An ASI:One Pro / OpenAI-compatible API key and the exact compatible base URL/model shown in your provider dashboard
- Optional Agentverse API key for remote PDF resource delivery

## Run locally (Windows PowerShell)

From the repository root:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r backend/requirements.txt
Copy-Item backend/.env.example backend/.env
# Edit backend/.env and set your real credentials; never commit this file.
python backend/app/agent.py
```

If starting inside `backend/`, use `python -m app.agent` instead. Keep credentials in `backend/.env`, not source code or chat messages.

## Configure your resume

Copy `backend/app/data/resume.example.json` to `backend/app/data/resume.local.json` and replace the fictional content with your own truthful details. `resume.local.json` is gitignored. The example resume is only a demo fixture.

## Use the agent

1. Send a **specific job listing URL**, not a job portal homepage. For Naukri, open the individual job and copy its full URL.
2. If the site blocks automated reading or times out, paste the description like this:

   ```text
   Job description:
   Software Engineering Intern

   Responsibilities:
   ...
   Requirements:
   ...
   ```

3. Review the letter in chat. Send revision instructions as ordinary chat text (for example, “make it shorter and emphasize my Python project”).
4. Click **Generate PDF** or send `generate_pdf`.

The scraper uses Jina Reader with a bounded timeout. It does not bypass bot checks, login walls, or site restrictions. If retrieval fails, the pasted-description path is the intended fallback. The generator is instructed to use only resume facts and applies deterministic placeholder/number checks; still review every letter before using it.

## PDF delivery

- `PDF_STORAGE=local`: writes the PDF under `backend/output/`. The agent sends the path as a message; this is a local-development fallback, **not a downloadable chat attachment**.
- `PDF_STORAGE=agentverse`: attempts to upload the PDF to Agentverse storage and send an `agent-storage://` resource. Configure `AGENTVERSE_API_KEY` and verify this live in ASI:One. If remote delivery fails, the implementation falls back to a local file.

Do not claim Agentverse delivery works until tested with your own account and current platform permissions. A local path only exists on the machine running the agent.

## Run tests

From repository root:

```powershell
python -m pytest backend/tests -q
```

Tests should not require real API credentials or make live requests. A successful unit-test run does not prove ASI:One discovery, mailbox registration, or remote asset delivery; those need the manual checks below.

## Manual acceptance checklist

- [ ] Agent starts and appears in Agentverse/ASI:One as configured.
- [ ] A public, accessible job listing URL produces a draft.
- [ ] A Naukri homepage is rejected as a homepage, with instructions to use a listing URL.
- [ ] A timeout / blocked site gives a clear fallback, not invented job details.
- [ ] `Job description:` plus pasted text creates a draft without fetching a URL.
- [ ] Revision requests update the current content and the next PDF uses the revised draft.
- [ ] The generated PDF opens and contains the approved latest text.
- [ ] Agentverse mode returns a real resource to the recipient; test this live before demo day.

## Limitations

- In-memory sessions reset when the process restarts and are not shared across replicas.
- Automated readers cannot guarantee access to every job site.
- The local PDF fallback does not attach a file to ASI:One.
- No live ASI:One / Agentverse credentials or service delivery are exercised by unit tests.

# InternAssist

![tag:innovationlab](https://img.shields.io/badge/innovationlab-3D8BD3)
![tag:hackathon](https://img.shields.io/badge/hackathon-5F43F1)

InternAssist is an ASI:One agent that helps students create resume-grounded cover letters for internship and job applications.

<p align="center">
  <img src="assets/internassist-avatar.svg" alt="InternAssist avatar" width="160" />
</p>

## What it does

1. Accepts a public job-listing URL or a pasted job description.
2. Extracts role details from the listing.
3. Creates one tailored cover letter using only the configured resume information.
4. Lets the user review the draft and request revisions in chat.
5. Generates a PDF of the latest approved letter.

## Agent details

- **Name:** InternAssist
- **Agent address:** `agent1q05kkcnxkvaguqdj79ha6ur3df2aspvsel5gr2cxjt2xc88cy5uyw0catw3`
- **Protocol:** Agent Chat Protocol (ACP)
- **Availability:** Agentverse Mailbox and ASI:One

## Use it in ASI:One

Send InternAssist a specific public job-listing URL. If a site blocks automated reading, send:

```text
Job description:
[paste the job description here]
```

Review the generated draft, send any revision instructions in the chat, then choose **Generate PDF**.

## Run locally

Python 3.11 is required.

```zsh
cd backend
source ../.venv/bin/activate
export SSL_CERT_FILE="$(python -m certifi)"
export USE_MAILBOX=true
python -m app.agent
```

Keep the process running while using the mailbox-connected agent. Configuration belongs in `backend/.env`; do not commit that file.

## Tests

From the repository root:

```zsh
source .venv/bin/activate
python -m pytest backend/tests -q
```

## Notes

- Use a specific job listing URL, not a job portal home page.
- The agent does not bypass login walls, bot protection, or inaccessible job sites.
- Local PDF delivery writes to the machine running the agent. Agentverse storage delivery requires its own configured credentials.

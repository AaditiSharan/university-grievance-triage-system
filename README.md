# university-grievance-triage-system
 AI-assisted triage system that reads each grievance, figures out what kind it is, flags sensitive ones, sends it to the right office, ranks its urgency, and shows all of this on a dashboard where humans make the final call.
 
Builds labelled grievance categories and explicit
sensitivity rules covering routine academic,
administrative and high-priority welfare-related
submissions. Includes valid, incomplete, conflicting and
edge-case records so the representation supports
systematic reasoning and independent validation.

Combines language classification with rule-based
sensitivity escalation and priority ranking so urgent
cases receive appropriate routing without suppressing
normal requests. Compares the reasoning or classifier
against a simple baseline and separately measure
correctness, false decisions and failure cases before
final integration.

Deploys a grievance-cell dashboard showing category,
sensitivity evidence, routing destination, priority and
human-review status. Makes evidence, confidence,
exceptions and human review visible so the resulting
workflow remains understandable and accountable in
practical use.

## Staff grievance resolution

Faculty can read grievances routed to their provisioned department. Staff can
review and resolve grievances routed to their provisioned department, while
administrators retain cross-department access. Department queue and decision
permissions are enforced by the API; a user's `department` is provisioned on
their `users` record and is never accepted from public registration.

The staff dashboard keeps triage suggestions separate from human decisions,
records reviewer notes and resolution solutions, and appends each status
transition to the status history. Resolved and closed grievances are read-only
through the normal review workflow; reopening requires a separate authorized
workflow, which is not currently provided. Students can see their saved staff
resolution on both tracking and submissions views, but not reviewer notes or
internal audit details. Bulk actions require a solution and explicit
approval for every selected grievance. Draft generation is an explicit,
non-persisting action that uses stored triage category/route context to prepare
editable response text. Sensitive-flagged cases are rejected by the backend
and must be handled by a human. Drafts are never sent or used to resolve a case
without an individually approved staff decision.

## Run locally

Run locally

Prerequisites: Python 3.10+ (tick "Add Python to PATH" when installing), Node.js 18+ and Git.

From the repository root, create a virtual environment (one time only), activate it, install the Python dependencies, train the TF-IDF/Logistic Regression models on data/processed/train.csv, and start the API:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m src.classifier.train
$env:SECRET_KEY = (python -c "import secrets; print(secrets.token_urlsafe(32))")
python -m uvicorn src.api.main:app --reload --port 8000```


On macOS or Linux, activate with source .venv/bin/activate and set the key with export SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))").

If PowerShell says running scripts is disabled, run this once and try again:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned```

requirements.txt includes torch and sentence-transformers, which are large downloads and are not used yet. If you only want to run the app, you can remove those two lines before installing.

In another terminal, install and start the React app:
```
powershell
cd frontend
npm install
npm run dev```

The API is available at http://localhost:8000/api, and the frontend at http://localhost:5173. Staff and faculty accounts are allowed to self-register only when their email matches the configured institutional domains. Configure these domains with the environment variable STAFF_EMAIL_DOMAINS (for example, STAFF_EMAIL_DOMAINS=example.edu,university.edu). Register a user through the app. To provision an administrator, first register that account, then promote it from the local database:

```powershell
python -c "from src.db.connection import SessionLocal; from src.db.models import User; db=SessionLocal(); user=db.query(User).filter_by(username='YOUR_USERNAME').one(); user.role='admin'; db.commit(); db.close()"
```
Training uses the dataset's true_master and true_subcategory labels as-is, including UNCLEAR. For a fresh checkout, train before accepting submissions; the generated model files are stored under src/classifier/models/.

Submissions receive triage suggestions and remain in submitted status until a reviewer records a human decision in the admin dashboard. Sensitivity, priority, routing and incident matches are explanations and recommendations; they do not close, resolve or otherwise decide a grievance automatically.

Run the API integration and edge-case tests with:

```powershell
python -m pytest -q tests\test_end_to_end.py```

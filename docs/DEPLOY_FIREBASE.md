# Deploying UniResolve AI on Firebase

This puts the whole project online in one Firebase project:

| Part | Where it runs |
|---|---|
| React website | Firebase Hosting (`https://YOUR_PROJECT_ID.web.app`) |
| FastAPI backend + AI pipeline | Cloud Run service `uniresolve-api` (same project) |
| Users and grievances | Cloud Firestore |

Firebase Hosting forwards every `/api/...` request to Cloud Run, so the website and
the backend share one address. Login stays the app's own username/password (JWT).

Everything below is done in the browser. You do **not** need to install anything
on your computer: the commands run in **Google Cloud Shell**, a free terminal
inside the browser.

---

## Part 1 — Create the Firebase project (about 5 minutes)

1. Go to <https://console.firebase.google.com> and sign in with your Google account.
2. Click **Create a project** (or **Add project**).
3. Type a name, for example `uniresolve`. Under the name you will see the
   **project ID** (for example `uniresolve-1a2b3`). **Write it down** — you need it later.
4. Click **Continue**. Turn **off** Google Analytics (not needed). Click **Create project**, then **Continue**.

### Switch to the Blaze plan

Cloud Run needs the pay-as-you-go **Blaze** plan. At student/demo usage it stays
inside the free tier, but Google asks for a card.

1. In the bottom-left corner of the Firebase console, click **Spark** → **Upgrade**.
2. Choose **Blaze**, add or create a billing account, and confirm.
3. Optional but recommended: when asked, set a **budget alert** (for example ₹100 or $2)
   so you get an email if anything ever costs money.

### Create the Firestore database

1. In the left menu click **Build → Firestore Database → Create database**.
2. Edition: **Standard**. Database ID: leave as `(default)`.
3. Location: choose **nam5 (United States)**. (It must match the backend region `us-central1`.)
4. Choose **Start in production mode**, then click **Create**.

---

## Part 2 — Deploy the backend to Cloud Run (about 10 minutes)

1. Open <https://console.cloud.google.com>.
2. At the top, click the project picker and select your Firebase project.
3. Click the **Activate Cloud Shell** button (the `>_` icon, top-right). A terminal
   opens at the bottom of the page. If it asks to authorize, click **Authorize**.
4. Paste these lines one at a time and press **Enter** after each.
   Replace `YOUR_PROJECT_ID` with your project ID from Part 1.

```bash
PROJECT_ID=YOUR_PROJECT_ID
gcloud config set project $PROJECT_ID
git clone https://github.com/AaditiSharan/university-grievance-triage-system.git
cd university-grievance-triage-system
gcloud services enable run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com firestore.googleapis.com
```

5. Give the backend permission to use Firestore:

```bash
PROJECT_NUMBER=$(gcloud projects describe $PROJECT_ID --format='value(projectNumber)')
gcloud projects add-iam-policy-binding $PROJECT_ID --member=serviceAccount:$PROJECT_NUMBER-compute@developer.gserviceaccount.com --role=roles/datastore.user
```

6. Deploy. Change `university.edu,lpu.in` to the email domains that staff and faculty
   are allowed to register with (comma-separated, no spaces):

```bash
gcloud run deploy uniresolve-api --source . --region us-central1 --allow-unauthenticated --set-env-vars "^@^SECRET_KEY=$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')@STAFF_EMAIL_DOMAINS=university.edu,lpu.in"
```

- If it asks *"Deploying from source requires an Artifact Registry Docker repository… create?"*, type `Y`.
- The first build takes 5–10 minutes (it installs Python packages and trains the classifier).
- When it finishes it prints a **Service URL**. Open `SERVICE_URL/api/health` in a
  new tab — you should see `{"status":"ok", ...}`.

---

## Part 3 — Deploy the website to Firebase Hosting (about 5 minutes)

Still in Cloud Shell, inside the `university-grievance-triage-system` folder:

```bash
cd frontend && npm ci && npm run build && cd ..
npx -y firebase-tools@latest login --no-localhost
```

The login command prints a link. Open it, sign in with the same Google account,
copy the code it shows, paste it back into Cloud Shell and press **Enter**. Then:

```bash
npx -y firebase-tools@latest deploy --only hosting,firestore:rules --project $PROJECT_ID
```

When it says **Deploy complete!**, open `https://YOUR_PROJECT_ID.web.app`.

---

## Part 4 — Make yourself admin

1. On the website, register a normal (student) account.
2. In the Firebase console go to **Firestore Database → Data → users**.
3. Click the document named `u_YOUR_USERNAME`, click the `role` field, change
   `student` to `admin`, and click **Update**.
4. On the website, log out and log in again. The Admin dashboard now appears.

---

## Updating after you change the code

Open Cloud Shell again and run:

```bash
cd university-grievance-triage-system
git pull
gcloud run deploy uniresolve-api --source . --region us-central1
cd frontend && npm ci && npm run build && cd ..
npx -y firebase-tools@latest deploy --only hosting --project YOUR_PROJECT_ID
```

The `SECRET_KEY` and allowed domains you set the first time are kept. Skip the
first `gcloud run deploy` line if you only changed `frontend/`, and skip the last
three lines if you only changed the backend.

---

## Troubleshooting

| Problem | Fix |
|---|---|
| `gcloud run deploy` fails with a *permission* or *Cloud Build* error | Run `gcloud projects add-iam-policy-binding $PROJECT_ID --member=serviceAccount:$PROJECT_NUMBER-compute@developer.gserviceaccount.com --role=roles/cloudbuild.builds.builder` and deploy again. |
| Website loads but login/submit says *network error* or 404 | Check that the Cloud Run service is named `uniresolve-api` in region `us-central1` (these must match `firebase.json`). |
| Backend logs say *SECRET_KEY must be set* | Re-run the full deploy command from Part 2, step 6. |
| Backend logs mention Firestore *PermissionDenied* | Re-run Part 2, step 5, and check that the Firestore database exists (Part 1). |
| Staff/faculty registration is refused | The email domain is not in `STAFF_EMAIL_DOMAINS`. Change it with `gcloud run services update uniresolve-api --region us-central1 --update-env-vars "^@^STAFF_EMAIL_DOMAINS=university.edu,lpu.in"`. |

Backend logs: Google Cloud console → **Cloud Run → uniresolve-api → Logs**.

---

## How it works (for developers)

- `Dockerfile` builds the backend image, installs `requirements-deploy.txt`
  (pinned, without torch) and retrains the classifier so the model files match
  the installed scikit-learn. It sets `DB_BACKEND=firestore`.
- `src/db/firestore_store.py` implements the same helpers as `src/db/crud.py`
  on Firestore. `crud.py` switches to it automatically when the request's
  database session is a `FirestoreSession` (returned by `get_db()` when
  `DB_BACKEND=firestore`). Local development still uses SQLite by default.
- Firestore layout: `users/u_<username>`, `counters/users` (numeric user ids),
  `grievances/<GRV-ID>` (with the AI analysis, human decision, status history
  and audit events stored inside the document), and `audit_logs` for events
  not tied to a grievance.
- `firestore.rules` blocks all direct browser access; only the backend's
  service account can read and write.
- `firebase.json` serves `frontend/dist` and rewrites `/api/**` to the
  `uniresolve-api` Cloud Run service.

### Running the Firestore tests locally

Install the Firebase CLI, Java 21 and `pip install google-cloud-firestore`, then:

```bash
firebase emulators:start --only firestore --project demo-test
# in another terminal
FIRESTORE_EMULATOR_HOST=127.0.0.1:8080 python -m pytest tests/test_firestore_backend.py
```

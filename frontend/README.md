# Frontend workspace

The MVP uses Streamlit. Presentation code lives here; PDF extraction, policy
interpretation, and evidence validation stay in `backend/`.

Entry point:

```powershell
streamlit run frontend/app.py
```

The app keeps the processed document and the last result in
`st.session_state`. A content fingerprint prevents PDF reprocessing on ordinary
reruns, and the provider is called only on an explicit **Ask** action.

`frontend/messages.py` holds UI-safe copy and translates application-level LLM
errors into friendly messages without echoing exception text or secrets.

See the repository-level `README.md` for setup, environment variables, privacy
notes, limitations, and deployment steps.

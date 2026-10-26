# Frontend workspace

The MVP uses Streamlit. Keep presentation code here; keep PDF extraction,
policy interpretation, and evidence validation in `backend/`.

Planned entry point: `frontend/app.py`.

Run from the repository root once the entry point is implemented:

```powershell
streamlit run frontend/app.py
```

The entry point should cache the processed document in `st.session_state` so
ordinary Streamlit reruns do not re-extract the same PDF or repeat an LLM call.

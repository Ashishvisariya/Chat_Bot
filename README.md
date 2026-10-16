# LangGraph + Groq Chatbot (Render-ready)

Streamlit chat UI with LangGraph, Groq, and SQLite conversation history.

## Run locally

1. Install Python 3.12.
2. Create a virtual environment and install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Copy `.env.example` to `.env` and add your Groq API key.
4. Run:
   ```bash
   streamlit run frontand.py
   ```

## Deploy to Render

1. Push the contents of this folder to a GitHub repository. Do not commit `.env` or database files.
2. In Render, choose **New + → Blueprint** and connect the repository. Render will read `render.yaml`.
3. When prompted, enter `GROQ_API_KEY` in the environment settings. Never put the key in source code.
4. Deploy the service and open the generated `onrender.com` URL.

The Blueprint configures a persistent disk mounted at `/var/data`, and SQLite is stored at `/var/data/chat_history.db`. A persistent disk requires a paid Render web service; the `starter` plan is selected for this reason. If you change to a free instance, its filesystem is ephemeral and chat history may disappear on restart/redeploy.

## Notes

- Chat history is stored in one SQLite database on the persistent disk.
- This is a single-instance/small-project setup. SQLite on a persistent disk is not ideal for multiple service instances or heavy concurrent writes.
- Treat this as a personal/demo app: there is no user login or per-user access control. Do not use it for sensitive conversations without adding authentication and authorization.

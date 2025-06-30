
# from fastapi import FastAPI, Request
# from fastapi.responses import RedirectResponse, HTMLResponse
# from google_auth_oauthlib.flow import Flow
# import os

# app = FastAPI()

# # Set redirect URI to match Google Console
# REDIRECT_URI = "http://localhost:8080/callback"

# # Path to your credentials.json
# CLIENT_SECRETS_FILE = os.path.join(os.path.dirname(__file__), "credentials.json")

# # Scopes we need to access Google Calendar
# SCOPES = ["https://www.googleapis.com/auth/calendar.events"]

# # Store credentials in memory (or use database/session in real app)
# user_credentials = {}

# @app.get("/")
# def home():
#     return {"message": "Go to /authorize to start Google OAuth"}

# @app.get("/authorize")
# def authorize():
#     flow = Flow.from_client_secrets_file(
#         CLIENT_SECRETS_FILE,
#         scopes=SCOPES,
#         redirect_uri=REDIRECT_URI
#     )
#     auth_url, _ = flow.authorization_url(prompt='consent')
#     return RedirectResponse(auth_url)

# @app.get("/callback")
# def callback(request: Request):
#     flow = Flow.from_client_secrets_file(
#         CLIENT_SECRETS_FILE,
#         scopes=SCOPES,
#         redirect_uri=REDIRECT_URI
#     )
#     flow.fetch_token(authorization_response=str(request.url))

#     credentials = flow.credentials
#     user_credentials['token'] = credentials.token
#     user_credentials['refresh_token'] = credentials.refresh_token
#     user_credentials['client_id'] = credentials.client_id
#     user_credentials['client_secret'] = credentials.client_secret

#     return HTMLResponse("<h2>Authentication Successful! You can now book appointments.</h2>")

# backend/main.py
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse, JSONResponse
from google_auth_oauthlib.flow import Flow
from agent.langgraph_flow import langgraph_agent
from pydantic import BaseModel
from dotenv import load_dotenv
import os
from agent.oauth_utils import get_google_flow
from agent.token_store import stored_token





app = FastAPI()
graph = langgraph_agent()
load_dotenv()

# backend/main.py

REQUIRED_ENV_VARS = ["GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET", "GOOGLE_REDIRECT_URI", "GEMINI_API_KEY"]

missing = [var for var in REQUIRED_ENV_VARS if not os.getenv(var)]
if missing:
    raise RuntimeError(f"❌ Missing required environment variables in backend: {', '.join(missing)}")


class TokenPayload(BaseModel):
    token: str

stored_token = {}  # In-memory token storage

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # or restrict to ['http://localhost:8501']
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def root():
    return {"message": "Booking Agent API is running!"}

@app.post("/chat/token")
async def save_token(request: Request):
    data = await request.json()
    token = data.get("token")
    if token:
        stored_token["token"] = token
        return JSONResponse(content={"status": "success"})
    else:
        return JSONResponse(status_code=400, content={"error": "Missing token"})

@app.get("/authorize")
def authorize():
    flow = get_google_flow()
    auth_url, _ = flow.authorization_url(prompt='consent')
    return RedirectResponse(auth_url)

from fastapi import Request
from fastapi.responses import JSONResponse

from fastapi import Request
from fastapi.responses import JSONResponse
import google.generativeai as genai
import os

@app.post("/chat")
async def chat_endpoint(request: Request):
    print("📥 Received POST request to /chat")

    try:
        body = await request.json()
        print("📦 Request body:", body)
    except Exception as e:
        print("❌ Failed to parse JSON body:", e)
        return JSONResponse(status_code=400, content={"response": "Invalid JSON body."})

    message = body.get("message", "")
    print("🗣️ Message received from user:", message)

    try:
        result = graph.invoke({"input": message})
        print("✅ LangGraph agent result:", result)
        return {"response": result.get("output", "Sorry, I didn’t understand that.")}
    except Exception as e:
        print("❌ Error during LangGraph agent call:", e)
        return JSONResponse(status_code=500, content={"response": f"Error: {str(e)}"})
    





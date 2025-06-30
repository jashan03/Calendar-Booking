
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
import traceback
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
import traceback
import json






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
async def receive_token(token_data: dict):
    print("📥 Received token at backend:", token_data)
    stored_token["token"] = json.dumps(token_data) # This correctly stores the stringified JSON
    return {"status": "success"}

@app.get("/authorize")
def authorize():
    flow = get_google_flow()
    auth_url, _ = flow.authorization_url(prompt='consent')
    return RedirectResponse(auth_url)

# In your /chat endpoint, add better error logging:
@app.post("/chat")
async def chat_endpoint(request: Request):
    try:
        body = await request.json()
        message = body.get("message", "").strip()
        token = body.get("token")  # ✅ Token from frontend (optional)

        if not message:
            return JSONResponse(status_code=400, content={"response": "Message cannot be empty."})

        print("🟡 Received message:", message)

        # ✅ Store token if provided (for future use)
        if token:
            stored_token["token"] = token
            print("🔐 Token saved from incoming request")

        # ✅ DEBUG: Show current stored token state
        print("🧪 Current stored token:", stored_token.get("token"))

        # Initial state for LangGraph
        initial_state = {
        "input": message,
        "token": token,
        "intent": "",
        "summary": "",
        "start_time": "",
        "duration_minutes": 0,
        "output": ""
    }

        print("🔍 Invoking LangGraph with initial_state:", initial_state)
        result = graph.invoke(initial_state)
        print("✅ LangGraph result:", result)

        if result.get("intent") == "error":
            return JSONResponse(
                status_code=400,
                content={
                    "response": result.get("output", "Agent error."),
                    "type": "agent_error"
                }
            )

        return {"response": result.get("output", "✅ Request processed but no output.")}

    except Exception as e:
        print("❌ Exception occurred during /chat processing")
        traceback.print_exc()

        return JSONResponse(
            status_code=500,
            content={
                "response": f"❌ Internal Server Error: {str(e)}",
                "type": type(e).__name__,
                "trace": traceback.format_exc()
            }
        )

    
@app.get("/callback")
async def callback(code: str):
    flow = get_google_flow()
    flow.fetch_token(code=code)
    creds = flow.credentials
    token_json = creds.to_json()
    stored_token["token"] = token_json
    return {"token": token_json}  # ✅ Ensure this returns JSON

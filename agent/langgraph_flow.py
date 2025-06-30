# agent/langgraph_flow.py

import os
import json
from datetime import datetime, timedelta, timezone 
import traceback
from typing import TypedDict, Literal

from dotenv import load_dotenv
from langgraph.graph import StateGraph
from langchain.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableLambda
from langchain_google_genai import ChatGoogleGenerativeAI
from agent.token_store import stored_token


from .calendar import check_availability, book_event

load_dotenv()

model = ChatGoogleGenerativeAI(
    model="models/gemini-1.5-pro-latest",
    google_api_key=os.getenv("GEMINI_API_KEY")
)

class AgentState(TypedDict):
    input: str
    token: str
    intent: Literal["booking", "check_availability", "error", "unknown"]
    summary: str
    start_time: str
    duration_minutes: int
    output: str

# Define prompt template

prompt = ChatPromptTemplate.from_template(
    """You are a helpful assistant for processing calendar booking requests.
The current date is {current_date} and the current time is {current_time}.
The current timezone is Asia/Kolkata (IST).

User query: {user_input}

Respond with only a valid JSON object. Do not include any markdown, text, or backticks.

The JSON must contain:
- "intent": one of "booking", "check_availability", or "query_schedule"
- "summary": short event title (if booking). If the user does not provide a specific title, use a default like "Meeting" or "Appointment".
- "start_time": ISO format datetime (e.g., "YYYY-MM-DDTHH:MM:SS").
  - **Prioritize the current date for bookings unless explicitly stated otherwise.**
  - If the user provides only a time (e.g., "3 PM", "14:00"), assume it's for the *current date* ({current_date}) if that time is in the future.
  - If the provided time is in the past relative to the current time, assume it's for *tomorrow*.
  - If the user specifies "today" or a similar phrase, use {current_date}.
  - If the user specifies a day (e.g., "tomorrow", "Tuesday", "next Monday"), infer the correct date.
- "duration_minutes": integer, default 30 if not mentioned.

Respond with only this JSON object — no commentary, no formatting, no extra characters.
"""
)


def handle_input(state):
    try:
        state.setdefault("intent", "unknown")
        state.setdefault("output", "")

        # Get current time for context
        ist_timezone = timezone(timedelta(hours=5, minutes=30))
        now_ist = datetime.now(ist_timezone)
        current_date_str = now_ist.strftime("%Y-%m-%d")
        current_time_str = now_ist.strftime("%H:%M:%S")

        chain = prompt | model
        response = chain.invoke({
            "user_input": state["input"],
            "current_date": current_date_str,
            "current_time": current_time_str
        })

        print("🔍 Raw model output:", response.content)

        try:
            parsed = json.loads(response.content)
        except json.JSONDecodeError as e:
            return {
                **state,
                "intent": "error",
                "output": f"❌ JSON parse error: {e}\nRaw response: {response.content}"
            }

        extracted_summary = parsed.get("summary", "")
        if not extracted_summary and parsed.get("intent") == "booking":
            extracted_summary = "Meeting" # Default summary if model doesn't provide one

        # Handle start_time parsing and date inference
        start_time_from_model = parsed.get("start_time", "")
        inferred_start_dt = None

        if start_time_from_model:
            try:
                # Attempt 1: Parse as full ISO datetime (e.g., "2025-07-01T10:00:00")
                inferred_start_dt = datetime.fromisoformat(start_time_from_model)
                if inferred_start_dt.tzinfo is None:
                    inferred_start_dt = inferred_start_dt.replace(tzinfo=ist_timezone)

            except ValueError:
                # Attempt 2: If full ISO fails, try to parse as just time (e.g., "10:00:00" or "10:00")
                time_part = None
                try:
                    time_part = datetime.strptime(start_time_from_model, "%H:%M:%S").time()
                except ValueError:
                    try:
                        time_part = datetime.strptime(start_time_from_model, "%H:%M").time()
                    except ValueError:
                        # Model provided something completely unparseable, 'inferred_start_dt' remains None
                        pass

                if time_part:
                    # Construct datetime for TODAY with the parsed time
                    inferred_start_dt = now_ist.replace(
                        hour=time_part.hour,
                        minute=time_part.minute,
                        second=time_part.second,
                        microsecond=0
                    )

                    # LOGIC REFINEMENT HERE:
                    # If the inferred time is *before or equal to* the current time,
                    # and the user did NOT explicitly say "today", assume it's for tomorrow.
                    # This prevents booking meetings in the immediate past of the current day.
                    # We need to be careful if user says "book for today at 9PM" and it's 9:20PM.
                    # Let's simplify and just say: if the time is already past on *this* date, push to tomorrow.
                    if inferred_start_dt < now_ist:
                        inferred_start_dt += timedelta(days=1)
                        print(f"DEBUG: Inferred time {inferred_start_dt.strftime('%H:%M')} for today ({current_date_str}) is in the past ({now_ist.strftime('%H:%M')}), setting for tomorrow.")

                    inferred_start_dt = inferred_start_dt.astimezone(ist_timezone) # Ensure IST timezone


        # Fallback to an empty string if no valid datetime could be inferred, or convert to ISO
        final_start_time_iso = inferred_start_dt.isoformat() if inferred_start_dt else ""

        return {
            **state,
            "intent": parsed.get("intent", "unknown"),
            "summary": extracted_summary,
            "start_time": final_start_time_iso,
            "duration_minutes": parsed.get("duration_minutes", 30),
            "output": "Processing your request..."
        }

    except Exception as e:
        # Re-raise or log more specifically if needed
        print(f"❌ Error in handle_input: {e}")
        traceback.print_exc() # Print full traceback
        return {
            **state,
            "intent": "error",
            "output": str(e)
        }
def handle_booking(state):
    try:
        start = state.get("start_time")
        if not start:
            state["output"] = "I didn't get the time. Please try again with a valid time."
            return state

        duration = state.get("duration_minutes", 30)
        # Use the summary from state, or a fallback if still somehow empty
        summary = state.get("summary") or "Meeting" # Ensures it's never empty

        # Convert to datetime and calculate end time
        # Ensure start_dt has timezone info before adding timedelta
        start_dt = datetime.fromisoformat(start)
        # If it doesn't have timezone (which it should if handle_input is good), assign IST
        if start_dt.tzinfo is None:
             ist_timezone = timezone(timedelta(hours=5, minutes=30))
             start_dt = start_dt.replace(tzinfo=ist_timezone)

        end_dt = start_dt + timedelta(minutes=duration)

        book_event(summary, start_dt.isoformat(), end_dt.isoformat(), state["token"])
        state["output"] = f"✅ Successfully booked: {summary} at {start_dt.strftime('%I:%M %p')}"
    except Exception as e:
        print(f"❌ Booking error in handle_booking: {e}") # Add this for better debugging
        traceback.print_exc() # Print full traceback
        state["output"] = f"❌ Booking error: {str(e)}"
        state["intent"] = "error"
    return state

def handle_availability(state):
    try:
        events = check_availability(state["token"])
        if not events:
            state["output"] = "You're free all day!"
        else:
            event_list = "\n".join([
                f"• {e['summary']} ({e['start'].get('dateTime', 'all day')})"
                for e in events
            ])
            state["output"] = f"Today's events:\n{event_list}"
    except Exception as e:
        state["output"] = f"❌ Calendar error: {str(e)}"
        state["intent"] = "error"
    return state

def handle_error(state):
    return {
        **state,
        "output": f"❌ Error: {state.get('output', 'Unknown error occurred')}"
    }

def langgraph_agent():
    builder = StateGraph(AgentState)

    # Add all nodes
    builder.add_node("input", RunnableLambda(handle_input))
    builder.add_node("book", RunnableLambda(handle_booking))
    builder.add_node("check", RunnableLambda(handle_availability))
    builder.add_node("error_handler", RunnableLambda(handle_error))
    builder.add_node("end", lambda x: x)

    # Set up conditional routing
    builder.add_conditional_edges(
        "input",
        lambda s: s.get("intent", "unknown"),
        {
            "booking": "book",
            "check_availability": "check",
            "query_schedule": "check", 
            "error": "error_handler",
            "unknown": "end"
        }
    )

    # Simple linear flows
    builder.add_edge("book", "end")
    builder.add_edge("check", "end")
    builder.add_edge("error_handler", "end")

    # Set entry and finish points
    builder.set_entry_point("input")
    builder.set_finish_point("end")

    return builder.compile()
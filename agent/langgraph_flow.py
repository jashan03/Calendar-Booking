# agent/langgraph_flow.py

import os
import json
from datetime import datetime, timedelta
from typing import TypedDict, Literal

from dotenv import load_dotenv
from langgraph.graph import StateGraph
from langchain.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableLambda
from langchain_google_genai import ChatGoogleGenerativeAI

from .calendar import check_availability, book_event

load_dotenv()

model = ChatGoogleGenerativeAI(
    model="models/gemini-1.5-pro-latest",
    google_api_key=os.getenv("GEMINI_API_KEY")
)

class AgentState(TypedDict):
    input: str
    intent: Literal["booking", "check_availability", "unknown"]
    summary: str
    start_time: str
    duration_minutes: int
    output: str

def langgraph_agent():
    builder = StateGraph(AgentState)

    prompt = ChatPromptTemplate.from_template(
        "You are an AI assistant that helps users schedule appointments on their Google Calendar.\n"
        "Extract the user's intent, time, and duration.\n"
        "User said: '{user_input}'\n"
        "Respond in this JSON format:\n"
        """{
            "intent": "booking" | "check_availability" | "unknown",
            "summary": "string",
            "start_time": "RFC3339 format or empty string",
            "duration_minutes": integer
        }"""
    )

    def handle_input(state):
        chain = prompt | model
        response = chain.invoke({"user_input": state["input"]})

        try:
            parsed = json.loads(response.content)
            state["intent"] = parsed.get("intent", "unknown")
            state["summary"] = parsed.get("summary", "Meeting with user")
            state["start_time"] = parsed.get("start_time", "")
            state["duration_minutes"] = parsed.get("duration_minutes", 30)
            state["output"] = f"Got it. I will schedule: {state['summary']} at {state['start_time']}"
        except Exception as e:
            print("❌ Failed to parse Gemini output:", e)
            state["intent"] = "unknown"
            state["output"] = "I couldn’t understand the time or intent. Please rephrase your request."
        return state

    def handle_booking(state):
        try:
            start = state.get("start_time")
            if not start:
                state["output"] = "I didn’t get the time. Please try again with a valid time."
                return state

            duration = state.get("duration_minutes", 30)
            summary = state.get("summary", "Meeting with user")

            # Convert to datetime and calculate end time
            start_dt = datetime.fromisoformat(start)
            end_dt = start_dt + timedelta(minutes=duration)

            book_event(summary, start_dt.isoformat(), end_dt.isoformat())
            reply = model.invoke("The meeting has been booked. Anything else you’d like?")
            state["output"] = reply.content

        except Exception as e:
            print("❌ Booking error:", e)
            state["output"] = "Something went wrong while booking. Please make sure your calendar is connected."
        return state

    def handle_availability(state):
        try:
            events = check_availability()
            if not events:
                state["output"] = "You’re free all day!"
            else:
                state["output"] = f"You already have {len(events)} events tomorrow."
        except Exception as e:
            print("❌ Availability error:", e)
            state["output"] = "I couldn’t access your calendar. Please connect it at /authorize."
        return state

    # Build the graph
    builder.add_node("input", RunnableLambda(handle_input))
    builder.add_conditional_edges("input", lambda s: s["intent"], {
        "booking": "book",
        "check_availability": "check",
        "unknown": "end"
    })
    builder.add_node("book", RunnableLambda(handle_booking))
    builder.add_node("check", RunnableLambda(handle_availability))
    builder.add_node("end", lambda x: x)

    builder.set_entry_point("input")
    return builder.compile()

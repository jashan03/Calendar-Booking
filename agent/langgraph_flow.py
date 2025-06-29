# agent/langgraph_flow.py
from langgraph.graph import StateGraph
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableLambda
from .calendar import check_availability, book_event
from dotenv import load_dotenv
import os
from typing import TypedDict, List, Literal
from langgraph.graph import StateGraph




load_dotenv()

model = ChatGoogleGenerativeAI(
    model="models/gemini-1.5-pro-latest",  # ✅ Use a supported model
    google_api_key=os.getenv("GEMINI_API_KEY")
)

def parse_intent(input_text):
    if "schedule" in input_text or "book" in input_text:
        return "booking"
    elif "available" in input_text:
        return "check_availability"
    return "unknown"

class AgentState(TypedDict):
    input: str
    intent: Literal["booking", "check_availability", "unknown"]
    output: str

def langgraph_agent():
    
    builder = StateGraph(AgentState)

    prompt = ChatPromptTemplate.from_template(
        "You are an AI assistant that helps users schedule appointments on their Google Calendar.\n"
        "User said: '{user_input}'\n"
        "Based on this input, determine if the user wants to book a meeting, check availability, or something else.\n"
        "Respond helpfully and concisely."
)

    def handle_input(state):
        chain = prompt | model
        response = chain.invoke({"user_input": state["input"]})

        intent = parse_intent(state["input"])  # still using your rule-based intent
        state["intent"] = intent
        state["output"] = response.content     # model reply
        return state

    def handle_booking(state):
        try:
            book_event("Meeting with user", "2025-06-30T15:00:00", "2025-06-30T15:30:00")
            reply = model.invoke("I've booked the meeting. Anything else you’d like?")
            state["output"] = reply.content
        except Exception as e:
            state["output"] = "It looks like your Google Calendar isn’t connected. Please visit http://localhost:8080/authorize to connect."
        return state



    def handle_availability(state):
        try:
            events = check_availability()
            if not events:
                state["output"] = "You’re free all day!"
            else:
                state["output"] = f"You already have {len(events)} events tomorrow."
        except Exception as e:
            state["output"] = "I couldn’t access your calendar. Please connect it at http://localhost:8080/authorize."
        return state

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

"""
Hip Fracture Clinical AI Agent.

Uses Anthropic SDK native tool_use (no LangChain agent dependency).
Tools are defined as plain functions and registered via JSON schema.

Supports both Anthropic (Claude) and OpenAI backends.
Set ANTHROPIC_API_KEY or OPENAI_API_KEY in environment.
"""

import os
# Pin OpenMP before heavy imports (xgboost/torch duplicate libomp deadlocks SHAP).
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")
import json

from agent_tools import (
    query_patient_data,
    predict_walking_recovery,
    predict_rehab_access,
    search_clinical_guideline,
)

SYSTEM_PROMPT = """You are a clinical decision support AI assistant specialising in hip fracture care.
You have access to data from the Australian and New Zealand Hip Fracture Registry (ANZHFR),
containing records of 97,429 hip fracture patients.

You have four tools available:
1. query_patient_data - for statistical questions about the patient population
2. predict_walking_recovery - for estimating 120-day walking recovery probability (XGBoost AUC 0.84)
3. predict_rehab_access - for estimating probability of rehabilitation discharge (XGBoost AUC 0.78)
4. search_clinical_guideline - for evidence-based clinical care standards

Guidelines for your responses:
- Always use the most appropriate tool(s) before answering
- Cite the data source or guideline when making clinical statements
- Clearly distinguish between population statistics and individual patient predictions
- Include confidence levels and model limitations when presenting predictions
- Recommend clinical review for all patient-specific assessments — you assist, not replace, clinicians
- Be concise and structured; use bullet points for clinical recommendations"""

# Tool registry: name -> callable
TOOL_REGISTRY = {
    "query_patient_data": query_patient_data,
    "predict_walking_recovery": predict_walking_recovery,
    "predict_rehab_access": predict_rehab_access,
    "search_clinical_guideline": search_clinical_guideline,
}

# Anthropic tool schema definitions
ANTHROPIC_TOOLS = [
    {
        "name": "query_patient_data",
        "description": (
            "Query the ANZHFR hip fracture dataset (97,429 patients) to answer statistical "
            "questions about counts, proportions, averages, trends, or comparisons."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "question": {"type": "string", "description": "The statistical question to answer"}
            },
            "required": ["question"],
        },
    },
    {
        "name": "predict_walking_recovery",
        "description": (
            "Predict whether a patient will recover walking ability by 120 days post-discharge. "
            "XGBoost model, AUC 0.84. Strongest predictor: pre-admission walking ability."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "patient_json": {
                    "type": "string",
                    "description": (
                        "JSON string of patient features: age, sex (1=Male,2=Female), "
                        "walk (1=No aids,2=Stick,3=Frame,4=Wheelchair), asa (1-5), "
                        "frailty (1-9), cogstat (1=Normal,2=Impaired), "
                        "ftype (1-4 fracture type), ptype (1=Public,2=Private), "
                        "uresidence (1=Home,2=Aged care)"
                    ),
                }
            },
            "required": ["patient_json"],
        },
    },
    {
        "name": "predict_rehab_access",
        "description": (
            "Predict whether a patient will be discharged to a rehabilitation unit. "
            "XGBoost model, AUC 0.78. Key predictors: residence, cognition, age, insurance type."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "patient_json": {
                    "type": "string",
                    "description": "JSON string of patient features (same schema as predict_walking_recovery)",
                }
            },
            "required": ["patient_json"],
        },
    },
    {
        "name": "search_clinical_guideline",
        "description": (
            "Search ACSQHC Hip Fracture Clinical Care Standards (2016 & 2023) for "
            "evidence-based guidelines on care protocols, quality benchmarks, and best practices."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "The clinical topic to search for"}
            },
            "required": ["query"],
        },
    },
]

# OpenAI-format tool schemas
OPENAI_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": t["name"],
            "description": t["description"],
            "parameters": t["input_schema"],
        },
    }
    for t in ANTHROPIC_TOOLS
]


def _call_tool(name: str, tool_input: dict) -> str:
    """Dispatch tool call and return string result."""
    fn = TOOL_REGISTRY.get(name)
    if fn is None:
        return f"Unknown tool: {name}"
    try:
        return fn.invoke(tool_input)
    except Exception as e:
        return f"Tool error ({name}): {str(e)}"


class HipFractureAgent:
    """
    Stateful agent with conversation history.
    Implements the tool-use loop directly with Anthropic or OpenAI SDK.
    """

    def __init__(self, provider: str = "anthropic"):
        self.provider = provider
        self.history: list = []
        self._client = None

    def _get_client(self):
        if self._client is None:
            if self.provider == "anthropic":
                import anthropic
                self._client = anthropic.Anthropic(
                    api_key=os.environ.get("ANTHROPIC_API_KEY")
                )
            else:
                from openai import OpenAI
                self._client = OpenAI(
                    api_key=os.environ.get("OPENAI_API_KEY")
                )
        return self._client

    def chat(self, user_message: str) -> str:
        self.history.append({"role": "user", "content": user_message})

        if self.provider == "anthropic":
            answer = self._anthropic_loop()
        else:
            answer = self._openai_loop()

        self.history.append({"role": "assistant", "content": answer})
        return answer

    def _anthropic_loop(self) -> str:
        client = self._get_client()
        messages = list(self.history)

        for _ in range(6):  # max iterations
            response = client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=2048,
                system=SYSTEM_PROMPT,
                tools=ANTHROPIC_TOOLS,
                messages=messages,
            )

            if response.stop_reason == "end_turn":
                # Extract text from content blocks
                return " ".join(
                    b.text for b in response.content if hasattr(b, "text")
                )

            if response.stop_reason == "tool_use":
                # Add assistant's response to messages
                messages.append({"role": "assistant", "content": response.content})

                # Process all tool calls
                tool_results = []
                for block in response.content:
                    if block.type == "tool_use":
                        result = _call_tool(block.name, block.input)
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": result,
                        })

                messages.append({"role": "user", "content": tool_results})
            else:
                break

        return "I was unable to complete the request within the allowed steps."

    def _openai_loop(self) -> str:
        from openai import OpenAI
        client = self._get_client()
        messages = [{"role": "system", "content": SYSTEM_PROMPT}] + list(self.history)

        for _ in range(6):
            response = client.chat.completions.create(
                model="gpt-4o",
                tools=OPENAI_TOOLS,
                messages=messages,
            )
            msg = response.choices[0].message

            if msg.tool_calls:
                messages.append(msg)
                for tc in msg.tool_calls:
                    args = json.loads(tc.function.arguments)
                    result = _call_tool(tc.function.name, args)
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": result,
                    })
            else:
                return msg.content or ""

        return "Unable to complete request within allowed steps."

    def reset(self):
        self.history = []


if __name__ == "__main__":
    provider = "anthropic" if os.environ.get("ANTHROPIC_API_KEY") else "openai"
    print(f"Using provider: {provider}")
    agent = HipFractureAgent(provider=provider)

    questions = [
        "What is the overall 30-day mortality rate in the dataset?",
        "For a 85-year-old female, ASA IV, frailty 7, using a walking frame — predict her walking recovery.",
        "What does the guideline say about time to surgery?",
    ]
    for q in questions:
        print(f"\nQ: {q}")
        print(agent.chat(q))

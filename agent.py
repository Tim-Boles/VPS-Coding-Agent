import google.generativeai as genai
import os
import argparse

# --- ADK Integration (Conceptual - for more advanced use) ---
# from adk.core import агент
# from adk.core.llm import Llm
# from adk.llm.gemini import GeminiLlm
# from adk.core.tool import Tool
#
# class MySimpleTool(Tool):
#     def _invoke(self, query: str) -> str:
#         return f"You asked about: {query}. This is a placeholder tool response."
#
# class TerminalAgent(agent.Agent):
#     def __init__(self, llm: Llm):
#         super().__init__(llm=llm, tools=[MySimpleTool()])
#
#     def think(self, prompt: str) -> str:
#         return self.invoke(prompt)
# --- End ADK Conceptual ---

def main():
    parser = argparse.ArgumentParser(description="Communicate with Gemini AI.")
    parser.add_argument("--api_key", type=str, help="Your Gemini API Key")
    args = parser.parse_args()

    api_key = args.api_key or os.getenv("GEMINI_API_KEY")

    if not api_key:
        print("🚨 Error: Gemini API key not found.")
        print("Please provide it using --api_key argument or set GEMINI_API_KEY environment variable.")
        return

    genai.configure(api_key=api_key)

    # For simplicity, using a recent stable model. Check documentation for the latest.
    model = genai.GenerativeModel('gemini-2.5-flash-preview-05-20') # Or other suitable models

    print("🤖 Gemini AI Agent is ready. Type 'exit' or 'quit' to end.")
    print("----------------------------------------------------")

    # --- ADK Conceptual Initialization (if you expand to use it) ---
    # gemini_llm = GeminiLlm(model_name='gemini-1.5-flash', api_key=api_key)
    # adk_agent = TerminalAgent(llm=gemini_llm)
    # ---

    while True:
        try:
            user_input = input("You: ")
            if user_input.lower() in ["exit", "quit"]:
                print("👋 Exiting agent...")
                break

            if not user_input:
                continue

            # Simple Gemini API call
            response = model.generate_content(user_input)
            # print(f"Gemini: {response.text}") # For non-streaming

            # For streaming response (better UX for terminal)
            print("Gemini: ", end="", flush=True)
            for chunk in response:
                print(chunk.text, end="", flush=True)
            print("\n----------------------------------------------------")


            # --- ADK Conceptual Usage (if you expand to use it) ---
            # This is a simplified representation. ADK provides more structured ways
            # to handle conversations, state, and tool use.
            # agent_response = adk_agent.think(user_input)
            # print(f"ADK Agent: {agent_response}")
            # print("----------------------------------------------------")
            # ---

        except KeyboardInterrupt:
            print("\n👋 Exiting agent...")
            break
        except Exception as e:
            print(f"💥 An error occurred: {e}")
            # Consider adding more robust error handling or retries
            break

if __name__ == "__main__":
    main()
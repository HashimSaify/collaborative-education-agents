"""
re_verify.py
------------
A utility script to verify the Google Gemini API key and model connectivity.
Useful for debugging environment issues.
"""

import os
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from colorama import init, Fore

# Initialize colorama for cross-platform colored output
init(autoreset=True)

def verify_connection():
    load_dotenv()
    api_key = os.getenv("GOOGLE_API_KEY")
    model_name = os.getenv("GOOGLE_MODEL", "gemini-2.0-flash")
    
    print(f"\n🔍 {Fore.CYAN}Testing Gemini API Key...")
    print(f"   Model: {Fore.YELLOW}{model_name}")
    print(f"   Key:   {Fore.YELLOW}{api_key[:10]}...{api_key[-4:] if api_key else ''}")

    if not api_key:
        print(f"\n❌ {Fore.RED}Error: GOOGLE_API_KEY not found in .env file.")
        return

    try:
        # Initialize the LLM
        llm = ChatGoogleGenerativeAI(
            model=model_name,
            google_api_key=api_key,
            temperature=0.3
        )
        
        # Perform a simple invocation
        print(f"\n📡 {Fore.CYAN}Sending test request...")
        response = llm.invoke("Hello, this is a system connectivity test. Please reply with 'Gemini Online'.")
        
        print(f"\n✅ {Fore.GREEN}Success! Connection established.")
        print(f"🤖 {Fore.MAGENTA}Gemini Response: {Fore.WHITE}{response.content.strip()}")
        
    except Exception as e:
        print(f"\n❌ {Fore.RED}Verification Failed!")
        print(f"{Fore.RED}{str(e)}")
        
        if "404" in str(e):
            print(f"\n💡 {Fore.BLUE}Tip: Check if the model name '{model_name}' is correct and available for your key.")
        elif "429" in str(e):
            print(f"\n💡 {Fore.BLUE}Tip: You have hit the rate limit. Please wait a few minutes and try again.")
        elif "API_KEY_INVALID" in str(e) or "expired" in str(e):
            print(f"\n💡 {Fore.BLUE}Tip: Your API key appears to be invalid or expired. Please check AI Studio.")

if __name__ == "__main__":
    verify_connection()

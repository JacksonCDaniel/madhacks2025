from llm import run_interviewer_agent

def main():
    print("Starting Claude interview simulation...\n")

    user_input = "I'm ready to begin the interview."

    response = run_interviewer_agent(user_input)

    print("\nINTERVIEWER RESPONSE:\n")
    print(response)

if __name__ == "__main__":
    main()


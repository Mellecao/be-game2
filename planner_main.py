from dotenv import load_dotenv
load_dotenv()

from crewai import Crew
from agents import create_planner
from tasks import create_trello_review_task


def main():
    print("=" * 50)
    print("  PLANNER AGENT — Leitura do Trello")
    print("  CrewAI + Ollama (Gemma 4)")
    print("=" * 50)
    print()

    planner = create_planner()
    task = create_trello_review_task(planner)

    crew = Crew(
        agents=[planner],
        tasks=[task],
        verbose=True,
    )

    result = crew.kickoff()
    print("\n" + "=" * 50)
    print("RESULTADO DO PLANNER:")
    print("=" * 50)
    print(result)


if __name__ == "__main__":
    main()

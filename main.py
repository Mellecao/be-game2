import sys
from crewai import Crew
from agents import create_copywriter
from tasks import create_landing_page_task


def main():
    if len(sys.argv) > 1:
        briefing = " ".join(sys.argv[1:])
    else:
        print("=" * 50)
        print("  GERADOR DE COPY PARA LANDING PAGES")
        print("  CrewAI + Ollama (Gemma 4)")
        print("=" * 50)
        print()
        print("Descreva o produto/servico para a landing page.")
        print("Inclua: nome, publico-alvo, diferencial.")
        print("(Digite e pressione Enter)\n")
        briefing = input("> ")

    if not briefing.strip():
        print("Briefing vazio. Encerrando.")
        return

    print("\nCriando agente e executando...\n")

    copywriter = create_copywriter()
    task = create_landing_page_task(copywriter, briefing)

    crew = Crew(
        agents=[copywriter],
        tasks=[task],
        verbose=True,
    )

    result = crew.kickoff()

    output_path = "output/landing-page.md"
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(str(result))

    print(f"\nResultado salvo em: {output_path}")


if __name__ == "__main__":
    main()

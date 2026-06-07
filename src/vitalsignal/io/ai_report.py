"""Generate optional AI summaries from structured deterministic report data."""

import json
import os
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any


DEFAULT_MODEL = "gpt-4.1-mini"
OPENAI_TEMPERATURE = 0.1
SYSTEM_PROMPT = (
    "Tu rédiges une synthèse médicale prudente en français pour un prototype "
    "éducatif. Tu ne poses aucun diagnostic, ne recommandes aucun traitement et "
    "n'affirmes jamais une cause certaine. Tu peux proposer des axes de lecture, "
    "des corrélations temporelles à vérifier et des questions utiles, mais tu dois "
    "toujours distinguer les faits observés des hypothèses prudentes. Tu reformules "
    "uniquement les données structurées fournies et tu n'inventes aucun contexte "
    "opératoire absent. Pour alléger la lecture, cite les constantes par leur nom "
    "court uniquement : ART_MAP, NIBP_MAP, MAP, SpO2, HR, EtCO2."
)


@dataclass(frozen=True)
class AISummary:
    """AI summary result with fallback information."""

    text: str
    used_ai: bool
    model: str | None
    fallback_reason: str | None


AIClient = Callable[[str, list[dict[str, str]]], str]


def has_openai_api_key() -> bool:
    """Return whether an OpenAI API key is available locally."""
    _load_dotenv_if_present()
    return bool(os.getenv("OPENAI_API_KEY"))


def generate_ai_summary(
    report_data: dict[str, Any],
    local_summary: str,
    client: AIClient | None = None,
    api_key: str | None = None,
    model: str | None = None,
) -> AISummary:
    """Generate an AI summary or return the deterministic local summary."""
    if api_key is None or model is None:
        _load_dotenv_if_present()

    selected_model = model if model is not None else os.getenv("OPENAI_MODEL", DEFAULT_MODEL)
    selected_api_key = api_key if api_key is not None else os.getenv("OPENAI_API_KEY")

    if client is None and not selected_api_key:
        return AISummary(local_summary, False, None, "missing_api_key")

    messages = _build_messages(report_data)

    try:
        if client is None:
            client = _openai_client(selected_api_key)
        text = client(selected_model, messages)
    except Exception as error:
        return AISummary(local_summary, False, selected_model, f"api_error: {error}")

    return AISummary(text.strip(), True, selected_model, None)


def _build_messages(report_data: dict[str, Any]) -> list[dict[str, str]]:
    """Build tightly constrained messages for the AI model."""
    payload = json.dumps(report_data, ensure_ascii=False, indent=2)
    user_prompt = (
        "À partir du JSON suivant, rédige une synthèse courte, explicative, "
        "prudente et non diagnostique. Ne fais pas une liste exhaustive de tous "
        "les épisodes. Résume en 4 à 6 puces Markdown courtes, chacune commençant "
        "par '- '. Sépare les idées :\n"
        "- lecture principale de l'indice et des signaux concernés ;\n"
        "- mise en regard temporelle des signaux quand les données le permettent ;\n"
        "- questions de vérification utiles pour un professionnel de santé ;\n"
        "- limites de causalité et limites contextuelles.\n"
        "Tu dois apporter une réflexion qualitative prudente sur corrélation et "
        "causalité potentielle : utilise des formulations comme 'à vérifier', "
        "'à mettre en regard', 'pourrait faire discuter', 'sans permettre de "
        "conclure'. Tu ne dois jamais affirmer qu'une anomalie en cause une autre. "
        "Ajoute un bref enseignement médical si utile, mais uniquement à partir "
        "des signaux fournis. Mentionne la nécessité d'une interprétation par un "
        "professionnel de santé. N'ajoute aucune information qui n'est pas présente "
        "dans le JSON.\n\n"
        f"{payload}"
    )
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]


def _load_dotenv_if_present(path: str = ".env") -> None:
    """Load simple KEY=VALUE entries from a local .env file without overwriting env."""
    env_path = Path(path)
    if not env_path.is_file():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        if line.startswith("export "):
            line = line.removeprefix("export ").strip()
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip("\"'")
        if key:
            os.environ.setdefault(key, value)


def _openai_client(api_key: str | None) -> AIClient:
    """Create a small OpenAI adapter only when the dependency is needed."""
    from openai import OpenAI

    openai_client = OpenAI(api_key=api_key)

    def call_model(model: str, messages: list[dict[str, str]]) -> str:
        response = openai_client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=OPENAI_TEMPERATURE,
        )
        content = response.choices[0].message.content
        return content or ""

    return call_model

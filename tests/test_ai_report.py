from vitalsignal.io.ai_report import OPENAI_TEMPERATURE, generate_ai_summary, has_openai_api_key


def test_generate_ai_summary_uses_local_summary_without_api_key() -> None:
    result = generate_ai_summary(
        {"case_id": 42},
        local_summary="Synthèse locale",
        api_key="",
    )

    assert result.text == "Synthèse locale"
    assert result.used_ai is False
    assert result.fallback_reason == "missing_api_key"


def test_openai_temperature_keeps_summary_mostly_stable() -> None:
    assert OPENAI_TEMPERATURE == 0.1


def test_has_openai_api_key_reads_local_dotenv(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    assert has_openai_api_key() is False

    tmp_path.joinpath(".env").write_text("OPENAI_API_KEY=test-key\n", encoding="utf-8")

    assert has_openai_api_key() is True


def test_generate_ai_summary_calls_injected_client() -> None:
    captured = {}

    def fake_client(model: str, messages: list[dict[str, str]]) -> str:
        captured["model"] = model
        captured["messages"] = messages
        return "Synthèse IA prudente."

    result = generate_ai_summary(
        {"case_id": 42, "priority_score": {"value": 25}},
        local_summary="Synthèse locale",
        client=fake_client,
        model="gpt-4.1-mini",
    )

    assert result.used_ai is True
    assert result.model == "gpt-4.1-mini"
    assert result.text == "Synthèse IA prudente."
    assert "ne poses aucun diagnostic" in captured["messages"][0]["content"]
    assert "corrélations temporelles à vérifier" in captured["messages"][0]["content"]
    assert "faits observés des hypothèses prudentes" in captured["messages"][0]["content"]
    assert "cite les constantes par leur nom court uniquement" in captured["messages"][0]["content"]
    assert "4 à 6 puces Markdown courtes" in captured["messages"][1]["content"]
    assert "chacune commençant par '- '" in captured["messages"][1]["content"]
    assert "questions de vérification utiles" in captured["messages"][1]["content"]
    assert "corrélation et causalité potentielle" in captured["messages"][1]["content"]
    assert "jamais affirmer qu'une anomalie en cause une autre" in captured["messages"][1]["content"]
    assert '"case_id": 42' in captured["messages"][1]["content"]


def test_generate_ai_summary_falls_back_on_client_error() -> None:
    def failing_client(model: str, messages: list[dict[str, str]]) -> str:
        raise RuntimeError("network down")

    result = generate_ai_summary(
        {"case_id": 42},
        local_summary="Synthèse locale",
        client=failing_client,
        model="gpt-4.1-mini",
    )

    assert result.used_ai is False
    assert result.text == "Synthèse locale"
    assert result.fallback_reason == "api_error: network down"


def test_generate_ai_summary_keeps_short_signal_names() -> None:
    def fake_client(model: str, messages: list[dict[str, str]]) -> str:
        return "EtCO2 est utilisable. HR reste stable."

    result = generate_ai_summary(
        {"case_id": 42},
        local_summary="Synthèse locale",
        client=fake_client,
        model="gpt-4.1-mini",
    )

    assert result.text == "EtCO2 est utilisable. HR reste stable."
    assert "dioxyde de carbone" not in result.text
    assert "fréquence cardiaque" not in result.text


def test_generate_ai_summary_loads_local_dotenv(
    tmp_path,
    monkeypatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_MODEL", raising=False)
    tmp_path.joinpath(".env").write_text(
        "OPENAI_API_KEY=test-key\nOPENAI_MODEL=test-model\n",
        encoding="utf-8",
    )
    captured = {}

    def fake_client(model: str, messages: list[dict[str, str]]) -> str:
        captured["model"] = model
        captured["messages"] = messages
        return "Synthèse IA prudente."

    result = generate_ai_summary(
        {"case_id": 42},
        local_summary="Synthèse locale",
        client=fake_client,
    )

    assert result.used_ai is True
    assert result.model == "test-model"
    assert captured["model"] == "test-model"

"""Tests du moteur LLM local (A0) : backend fake et erreurs, sans modèle téléchargé."""

from __future__ import annotations

import json
from typing import Literal

import pytest
from pydantic import BaseModel, Field

from agents import llm
from api.models import QCM


@pytest.fixture(autouse=True)
def _isoler(monkeypatch: pytest.MonkeyPatch) -> None:
    for cle in ("LLM_BACKEND", "LLM_MODEL_PATH", "LLM_N_CTX", "LLM_MODEL", "LLM_FAKE_REPONSE"):
        monkeypatch.delenv(cle, raising=False)
    llm.reinitialiser()


class _Choix(BaseModel):
    index: int = Field(ge=1)
    justification: str = Field(min_length=10)
    niveau: Literal["debutant", "avance"]


class _Selection(BaseModel):
    choix: list[_Choix] = Field(min_length=2)
    commentaire: str | None = None


# --------------------------------------------------------------------------- backend fake


def test_fake_est_configure(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_BACKEND", "fake")
    assert llm.est_configure()


def test_fake_structure_respecte_le_schema(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_BACKEND", "fake")
    reponse = llm.generer_structure("s", "p", _Selection)
    assert isinstance(reponse, _Selection)
    assert len(reponse.choix) == 2
    assert reponse.choix[0].index == 1 and reponse.choix[0].niveau == "debutant"
    assert len(reponse.choix[0].justification) >= 10


def test_fake_structure_modele_imbrique(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_BACKEND", "fake")
    qcm = llm.generer_structure("s", "p", QCM)
    assert len(qcm.choix) >= 2 and qcm.bonne_reponse == 0


def test_fake_deterministe(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_BACKEND", "fake")
    assert llm.generer_structure("s", "p", QCM) == llm.generer_structure("autre", "chose", QCM)
    assert llm.generer_texte("s", "bonjour") == llm.generer_texte("s", "bonjour")


def test_fake_reponse_imposee(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_BACKEND", "fake")
    donnees = {"choix": [{"index": 3, "justification": "Explique la MSE.", "niveau": "avance"}] * 2}
    monkeypatch.setenv("LLM_FAKE_REPONSE", json.dumps(donnees))
    reponse = llm.generer_structure("s", "p", _Selection)
    assert reponse.choix[0].index == 3


def test_fake_reponse_imposee_invalide(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_BACKEND", "fake")
    monkeypatch.setenv("LLM_FAKE_REPONSE", '{"choix": []}')
    with pytest.raises(llm.LLMIndisponible):
        llm.generer_structure("s", "p", _Selection)


def test_fake_texte(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_BACKEND", "fake")
    assert "MSE" in llm.generer_texte("s", "Explique la MSE", max_tokens=50)


# --------------------------------------------------------------------------- erreurs et configuration


def test_modele_absent(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_BACKEND", "llamacpp")
    monkeypatch.setenv("LLM_MODEL_PATH", "models/__absent__.gguf")
    assert not llm.est_configure()
    with pytest.raises(llm.LLMIndisponible, match="introuvable"):
        llm.generer_structure("s", "p", QCM)
    with pytest.raises(llm.LLMIndisponible):
        llm.generer_texte("s", "p")


def test_backend_inconnu(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_BACKEND", "anthropic")
    assert not llm.est_configure()
    with pytest.raises(llm.LLMIndisponible, match="inconnu"):
        llm.generer_texte("s", "p")


def test_chemin_relatif_part_de_la_racine(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_MODEL_PATH", "models/x.gguf")
    assert llm.chemin_modele() == llm.RACINE / "models" / "x.gguf"


def test_hors_ligne_force() -> None:
    import os

    assert os.environ["HF_HUB_OFFLINE"] == "1"


# --------------------------------------------------------------------------- validation et nouvelle tentative


class _FauxLlama:
    """Imite ``llama_cpp.Llama.create_chat_completion`` avec des réponses préparées."""

    def __init__(self, reponses: list[str]) -> None:
        self.reponses = reponses
        self.appels: list[dict] = []

    def create_chat_completion(self, **kwargs: object) -> dict:
        self.appels.append(kwargs)
        return {"choices": [{"message": {"content": self.reponses.pop(0)}}]}


def test_nouvelle_tentative_si_invalide(monkeypatch: pytest.MonkeyPatch) -> None:
    faux = _FauxLlama(['{"choix": []}', json.dumps(
        {"choix": [{"index": 1, "justification": "Assez longue.", "niveau": "avance"}] * 2})])
    monkeypatch.setattr(llm, "_llama", lambda: faux)
    reponse = llm.generer_structure("s", "p", _Selection, max_tokens=64)
    assert len(reponse.choix) == 2
    assert len(faux.appels) == 2
    assert faux.appels[0]["response_format"]["type"] == "json_object"
    assert faux.appels[0]["response_format"]["schema"] == _Selection.model_json_schema()
    assert faux.appels[0]["max_tokens"] == 64
    assert "invalide" in faux.appels[1]["messages"][-1]["content"]


def test_echec_apres_deux_tentatives(monkeypatch: pytest.MonkeyPatch) -> None:
    faux = _FauxLlama(["pas du json", '{"choix": []}'])
    monkeypatch.setattr(llm, "_llama", lambda: faux)
    with pytest.raises(llm.LLMIndisponible, match="2 tentatives"):
        llm.generer_structure("s", "p", _Selection)


def test_texte_llamacpp_sans_contrainte(monkeypatch: pytest.MonkeyPatch) -> None:
    faux = _FauxLlama(["  Bonjour.  "])
    monkeypatch.setattr(llm, "_llama", lambda: faux)
    assert llm.generer_texte("s", "p") == "Bonjour."
    assert "response_format" not in faux.appels[0]


# --------------------------------------------------------------------------- grammaire llama.cpp bornée


class _Long(BaseModel):
    titre: str = Field(json_schema_extra={"maxLength": 1100, "minLength": 300})
    court: str = Field(json_schema_extra={"maxLength": 50, "minLength": 5})
    limite: str = Field(json_schema_extra={"maxLength": 200})
    points: list[str] = Field(min_length=1, max_length=12,
                              json_schema_extra={"items": {"type": "string", "maxLength": 400}})
    choix: list[_Choix] = Field(default_factory=list, json_schema_extra={"minItems": 11, "maxItems": 15})
    huit: list[str] = Field(default_factory=list, json_schema_extra={"minItems": 2, "maxItems": 8})


def test_borner_schema_recursif() -> None:
    original = _Long.model_json_schema()
    borne = llm.borner_schema(original)
    props = borne["properties"]
    assert llm.MAX_LENGTH_GRAMMAIRE == 200 and llm.MAX_ITEMS_GRAMMAIRE == 10
    # maxLength > 200 : supprimé (pas ramené à 200) ; minLength ramené sous le plafond
    assert "maxLength" not in props["titre"] and props["titre"]["minLength"] == 200
    assert props["court"]["maxLength"] == 50 and props["court"]["minLength"] == 5  # inchangés
    assert props["limite"]["maxLength"] == 200  # à la limite : conservé
    assert "maxLength" not in props["points"]["items"]
    # maxItems plafonné à 10, minItems reste cohérent ; 8 (Critic) inchangé
    assert props["points"]["maxItems"] == 10 and props["points"]["minItems"] == 1
    assert props["choix"]["maxItems"] == 10 and props["choix"]["minItems"] == 10
    assert props["huit"]["maxItems"] == 8 and props["huit"]["minItems"] == 2
    # l'original n'est pas modifié
    assert original["properties"]["titre"]["maxLength"] == 1100
    assert original["properties"]["points"]["maxItems"] == 12


def test_grammaire_llamacpp_bornee(monkeypatch: pytest.MonkeyPatch) -> None:
    """Le schéma envoyé à llama.cpp est borné ; la validation Pydantic reste celle du modèle."""
    faux = _FauxLlama([json.dumps({"titre": "t", "court": "c", "limite": "l", "points": ["a"]})])
    monkeypatch.setattr(llm, "_llama", lambda: faux)
    reponse = llm.generer_structure("s", "p", _Long, max_tokens=32)
    schema = faux.appels[0]["response_format"]["schema"]
    assert reponse.titre == "t"
    assert "maxLength" not in schema["properties"]["titre"]
    assert "maxLength" not in schema["properties"]["points"]["items"]
    assert schema["properties"]["court"]["maxLength"] == 50


def test_validation_pydantic_garde_les_limites(monkeypatch: pytest.MonkeyPatch) -> None:
    """Une borne retirée de la grammaire reste appliquée par Pydantic."""

    class _Borne(BaseModel):
        texte: str = Field(max_length=300)

    valide = json.dumps({"texte": "ok"})
    faux = _FauxLlama([json.dumps({"texte": "x" * 301}), valide])
    monkeypatch.setattr(llm, "_llama", lambda: faux)
    assert llm.generer_structure("s", "p", _Borne).texte == "ok"
    assert "maxLength" not in faux.appels[0]["response_format"]["schema"]["properties"]["texte"]
    assert len(faux.appels) == 2


def test_json_coupe_demande_plus_court(monkeypatch: pytest.MonkeyPatch) -> None:
    """JSON tronqué par ``max_tokens`` : la 2e tentative demande une réponse plus courte."""
    valide = json.dumps({"choix": [{"index": 1, "justification": "Assez longue.", "niveau": "avance"}] * 2})
    faux = _FauxLlama(['{"choix": [{"index": 1, "justification": "Une phrase coup', valide])
    monkeypatch.setattr(llm, "_llama", lambda: faux)
    assert len(llm.generer_structure("s", "p", _Selection).choix) == 2
    consigne = faux.appels[1]["messages"][-1]["content"]
    assert "coupée" in consigne and "plus court" in consigne


def test_erreur_de_schema_ne_demande_pas_plus_court(monkeypatch: pytest.MonkeyPatch) -> None:
    valide = json.dumps({"choix": [{"index": 1, "justification": "Assez longue.", "niveau": "avance"}] * 2})
    faux = _FauxLlama(['{"choix": []}', valide])
    monkeypatch.setattr(llm, "_llama", lambda: faux)
    llm.generer_structure("s", "p", _Selection)
    consigne = faux.appels[1]["messages"][-1]["content"]
    assert "invalide" in consigne and "plus court" not in consigne


def test_schema_explainer_borne() -> None:
    """Cas réel qui faisait planter llama.cpp : le schéma Explication de l'Explainer (O2)."""
    from agents.explainer import Explication

    def bornes(s: object) -> list[int]:
        if isinstance(s, dict):
            return [v for k, v in s.items() if k in ("maxLength", "maxItems")] + \
                   [b for v in s.values() for b in bornes(v)]
        if isinstance(s, list):
            return [b for v in s for b in bornes(v)]
        return []

    original = Explication.model_json_schema()
    borne = llm.borner_schema(original)
    assert max(bornes(original)) > 200
    assert max(bornes(borne)) <= 200
    props = borne["properties"]
    # bornes longues (idée 220, explication 1100, exemple 500, lien 300) : supprimées
    for champ in ("idee_cle", "explication", "exemple", "lien_precedente"):
        assert "maxLength" not in props[champ], champ
    # points à retenir (180) et nombre de points (3) : conservés
    assert props["a_retenir"]["items"]["maxLength"] == 180
    assert props["a_retenir"]["maxItems"] == 3


def _grammaire_valide(schema: dict) -> bool:
    """Initialiser la grammaire côté C++ comme llama.cpp (vocabulaire seul du modèle GGUF).

    C'est l'initialisation C++ qui applique la limite de profondeur (256) ; ignoré sans
    ``llama_cpp`` ou sans modèle téléchargé.
    """
    llama_cpp = pytest.importorskip("llama_cpp")
    from llama_cpp.llama_grammar import json_schema_to_gbnf

    chemin = llm.RACINE / "models" / "qwen2.5-3b-instruct-q4_k_m.gguf"
    if not chemin.is_file():
        pytest.skip(f"modèle absent : {chemin}")
    modele = llama_cpp.Llama(model_path=str(chemin), vocab_only=True, verbose=False)
    vocab = llama_cpp.llama_model_get_vocab(modele.model)
    gbnf = json_schema_to_gbnf(json.dumps(schema))
    echantillonneur = llama_cpp.llama_sampler_init_grammar(vocab, gbnf.encode(), b"root")
    if not echantillonneur:
        return False
    llama_cpp.llama_sampler_free(echantillonneur)
    return True


@pytest.mark.parametrize("nom", ["Explication", "Jugement", "VerdictQCM"])
def test_grammaires_reelles_convertibles(nom: str) -> None:
    """Les schémas réels de l'Explainer et du Critic donnent une grammaire llama.cpp valide."""
    from agents import critic, explainer

    modele = {"Explication": explainer.Explication, "Jugement": critic.Jugement,
              "VerdictQCM": critic.VerdictQCM}[nom]
    schema = llm.borner_schema(modele.model_json_schema())
    if nom == "Jugement":
        assert schema["properties"]["affirmations"]["maxItems"] == critic.MAX_AFFIRMATIONS == 8
    assert _grammaire_valide(schema)

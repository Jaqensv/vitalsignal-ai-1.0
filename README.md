# VitalSignal AI

VitalSignal AI est un prototype éducatif d'analyse de signaux vitaux
peropératoires issus de VitalDB. Il analyse des enregistrements réalisés pendant
une intervention chirurgicale et produit une lecture technique non diagnostique.

Le projet vise trois usages pour la V1 :

* analyser une intervention VitalDB précise ;
* rechercher des interventions contenant certaines anomalies ;
* produire des rapports structurés et une synthèse courte.

## Périmètre

Un `case_id` VitalDB correspond à l'enregistrement d'une intervention
chirurgicale. Ce n'est pas une mesure isolée ni un suivi postopératoire.

Signaux actuellement traités :

* `ART_MAP` : pression artérielle moyenne invasive ;
* `NIBP_MAP` : pression artérielle moyenne non invasive ;
* `SpO2` : saturation périphérique en oxygène ;
* `HR` : fréquence cardiaque ;
* `EtCO2` : dioxyde de carbone en fin d'expiration.

Le pipeline détecte des anomalies simples, contrôle l'exploitabilité des signaux
et calcule un indice de priorité technique. Cet indice sert à orienter la lecture,
pas à mesurer une gravité clinique.

## Limites

Ce prototype ne prend pas en compte le contexte clinique complet :

* médicaments, anesthésie, ventilation, perfusions ou transfusions ;
* gestes chirurgicaux et étapes de l'intervention ;
* antécédents, biologie, contexte préopératoire ou postopératoire ;
* qualité réelle du capteur, positionnement patient ou référentiel physique.

Les données VitalDB proviennent d'un contexte hospitalier sud-coréen. Une
utilisation française ou européenne nécessiterait une validation externe
multicentrique.

VitalSignal AI n'est pas un dispositif médical et ne fournit pas de diagnostic.

## Installation

Python cible : `3.11`.

```bash
python3.11 -m venv .venv
.venv/bin/pip install -r requirements.txt
PYTHONPATH=src .venv/bin/python -m pytest
```

Interface Streamlit :

```bash
.venv/bin/pip install -r requirements-ui.txt
make ui
```

Lancement Docker :

```bash
cp .env.example .env
make docker-build
make docker-up
```

L'interface est ensuite disponible sur `http://localhost:8501`.

Docker fige l'environnement Python, Streamlit et dépendances. Le fichier `.env`
reste local : il n'est pas copié dans l'image Docker. Docker Compose le monte en
lecture seule dans le conteneur pour que l'application puisse charger
`OPENAI_API_KEY` et `OPENAI_MODEL`. Si tu ne veux pas utiliser la synthèse IA,
laisse simplement `OPENAI_API_KEY` vide.

Commandes utiles :

```bash
make test
make demo
make clean-cache
make docker-down
```

La suppression des données locales éventuelles est volontairement séparée :

```bash
make clean-cases
```

### Note pyarrow

Sur certains environnements macOS restreints ou sandboxés, `pyarrow` peut afficher
des warnings du type :

```text
sysctlbyname failed ... Operation not permitted
```

Ces messages viennent de la détection bas niveau des capacités CPU par `pyarrow`.
Ils sont non bloquants tant que la commande continue et produit le rapport ou lance
l'interface. Ils ne signifient pas que l'analyse VitalSignal AI a échoué.

## Cache local VitalDB

La première analyse d'une intervention nécessite un téléchargement depuis VitalDB.
Les constantes récupérées sont ensuite stockées localement dans `cases/`.

Au chargement suivant de la même intervention avec le même intervalle, VitalSignal AI
lit directement la copie locale :

```text
1re analyse intervention 42 → téléchargement VitalDB → cache local
2e analyse intervention 42 → lecture depuis cases/
```

Ce cache rend l'interface plus rapide, réduit les appels réseau et permet de
retravailler hors ligne sur les interventions déjà téléchargées. Le dossier
`cases/` est ignoré par Git.

Pour supprimer les données VitalDB mises en cache :

```bash
make clean-cases
```

## Utilisation CLI

Analyser une intervention :

```bash
PYTHONPATH=src .venv/bin/python -m vitalsignal.main 3
```

Exporter un rapport :

```bash
PYTHONPATH=src .venv/bin/python -m vitalsignal.main 3 --format json --output reports/intervention_3.json
PYTHONPATH=src .venv/bin/python -m vitalsignal.main 3 --format markdown --output reports/intervention_3.md
```

Rechercher des anomalies sur plusieurs interventions :

```bash
PYTHONPATH=src .venv/bin/python -m vitalsignal.search_cli --start-case-id 1 --end-case-id 5 --anomaly tachycardia
```

Auditer la distribution de l'indice :

```bash
PYTHONPATH=src .venv/bin/python -m vitalsignal.score_audit_cli --start-case-id 1 --end-case-id 50 --output reports/score_audit_1_50.json
```

Par défaut, les commandes de scan refusent les plages trop larges afin d'éviter un
téléchargement VitalDB involontairement long.

## Interface

L'interface Streamlit contient deux vues :

* `Analyser une intervention` : analyse détaillée d'une intervention ;
* `Rechercher des anomalies` : scan multi-cas par type d'anomalie.

L'analyse détaillée affiche :

* l'indice de priorité ;
* une synthèse courte ;
* une timeline chronologique ;
* des graphiques par constante ;
* l'exploitabilité des signaux ;
* des exports Markdown et JSON.

La recherche multi-cas affiche un graphique de fréquence des anomalies et un
tableau des interventions correspondantes. Par sécurité, l'interface refuse les
scans de plus de 50 interventions et affiche une progression pendant le scan.

Dans l'interface, l'intervalle d'échantillonnage est fixé à `2 s` pour l'analyse
détaillée et pour la recherche multi-cas, afin de garder les résultats comparables.

## IA

L'agent IA est optionnel. Le pipeline déterministe fonctionne sans clé API.

Configuration locale possible dans `.env` :

```text
OPENAI_API_KEY=
OPENAI_MODEL=gpt-4.1-mini
```

Pour la V1, le choix par défaut est un modèle peu coûteux (`gpt-4.1-mini`). La
valeur médicale du prototype vient d'abord du pipeline déterministe : règles,
contrôle qualité, indice de priorité, graphiques et données structurées. L'IA
sert à produire une synthèse courte et à formuler des pistes de lecture, pas à
remplacer l'analyse logicielle ni l'expertise clinique.

La synthèse IA reçoit des données structurées et doit rester prudente. Elle peut
proposer des axes de lecture, des corrélations à vérifier et des questions utiles,
mais ne doit pas conclure à une causalité ni poser de diagnostic. En cas d'échec
ou d'absence de clé, une synthèse locale déterministe reste disponible.

Pour alléger l'affichage, la synthèse IA utilise les noms courts des constantes
(`ART_MAP`, `SpO2`, `HR`, etc.) sans répéter leur signification entre parenthèses.

Le réglage OpenAI utilise une température de `0.1`. Ce choix garde des réponses
majoritairement stables, tout en laissant assez de souplesse pour formuler des
questions de vérification et une lecture qualitative moins mécanique.

Évolution V2 possible : comparer plusieurs modèles sur les mêmes rapports
structurés, par exemple un modèle plus avancé pour améliorer la qualité de la
synthèse, ou un modèle local pour explorer un fonctionnement offline. Cette
évolution devra être évaluée sur des critères simples : coût, latence, stabilité
des réponses, clarté pour un utilisateur français/européen et absence de
surinterprétation médicale.

Autre piste V2 : exposer le pipeline via FastAPI pour fournir des endpoints JSON
à un front séparé ou à d'autres outils. Cette API n'est pas nécessaire à la V1,
car l'interface Streamlit couvre déjà l'usage démonstrateur local.

## Avertissement

Ce projet est destiné à un usage éducatif, démonstratif et portfolio.
Il ne constitue pas un dispositif médical.
Les résultats doivent être interprétés par un professionnel de santé qualifié.

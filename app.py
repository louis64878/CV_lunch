import streamlit as st
import requests
import os
from openai import OpenAI

# Configuration de la page web
st.set_page_config(page_title="Louis - Multi-Source Job d'Été", page_icon="💼", layout="wide")

st.title("💼 Assistant Job d'Été Multi-Source")
st.write("Ce bot recherche des contrats saisonniers de 1 mois (août) à Lille sur Jooble, Adzuna et France Travail, accessibles sans voiture.")

# Barre latérale pour gérer les clés API
st.sidebar.header("Configuration")
openai_key = st.sidebar.text_input("Clé API OpenRouter", type="password", placeholder="sk-or-v1-...")

# Choix de la plateforme de recherche
source_recherche = st.sidebar.selectbox(
    "Source de recherche d'emploi",
    ["Jooble (Recommandé)", "Adzuna", "France Travail"]
)

# Configuration dynamique des clés selon la source choisie
jooble_key = "e81b59bc-ab6e-4e58-9841-a23ccdb6919f"
adzuna_key = "5635953427e68b32d0b87e0166256c87"

if source_recherche == "Jooble (Recommandé)":
    api_jooble = st.sidebar.text_input("Clé API Jooble", value=jooble_key, type="password")
elif source_recherche == "Adzuna":
    api_adzuna_id = st.sidebar.text_input("Adzuna App ID (Requis)", placeholder="Ex: a1b2c3d4")
    api_adzuna_key = st.sidebar.text_input("Adzuna App Key", value=adzuna_key, type="password")
elif source_recherche == "France Travail":
    ft_client_id = st.sidebar.text_input("Client ID France Travail", type="password")
    ft_client_secret = st.sidebar.text_input("Client Secret France Travail", type="password")

# Informations du candidat (Louis Guiffant)
PROFIL_LOUIS = {
    "nom": "Louis Guiffant",
    "email": "guiffantlouis123@gmail.com",
    "telephone": "0768445324",
    "ville": "Lille",
    "etudes": "École d'ingénieur au CESI",
    "disponibilite": "Disponible uniquement durant tout le mois d'août 2026 (contrat saisonnier court de 1 mois)",
    "competences": "Restauration, service en salle, polyvalence, sens du contact, dynamique, rigoureux",
    "langues": "Français (Langue maternelle), Anglais (Courant)",
    "experiences": "Bénévole (organisation d'événements, vente), stages d'observation en entreprise (Airbus Atlantic, prothésiste)"
}

# =====================================================================
# FONCTIONS D'APPEL AUX APIS DE RECHERCHE D'EMPLOI
# =====================================================================

# 1. JOOBLE API
def recuperer_offres_jooble(api_key):
    url = f"https://fr.jooble.org/api/{api_key}"
    headers = {"Content-Type": "application/json"}
    payload = {
        "keywords": "restauration",
        "location": "Lille",
        "page": "1"
    }
    try:
        r = requests.post(url, headers=headers, json=payload)
        r.raise_for_status()
        return r.json().get("jobs", [])
    except Exception as e:
        st.error(f"Erreur d'appel API Jooble : {e}")
        return []

def filtrer_offres_jooble(offres):
    valides = []
    exclusions_alternance = ["alternance", "apprentissage", "professionnalisation", "contrat pro", "apprenti", "alternant"]
    exclusions_voiture = ["permis b exigé", "véhicule indispensable", "permis obligatoire", "voiture personnelle", "permis b obligatoire"]
    exclusions_longs_contrats = ["6 mois", "12 mois", "un an", "1 an", "2 ans", "longue durée", "cdi", "durée indéterminée"]

    for item in offres:
        titre = item.get("title", "").lower()
        desc = item.get("snippet", "").lower() # Jooble utilise 'snippet' pour la description

        if any(mot in titre or mot in desc for mot in exclusions_alternance):
            continue
        if any(mot in titre or mot in desc for mot in exclusions_voiture):
            continue
        if any(mot in titre or mot in desc for mot in exclusions_longs_contrats):
            continue

        valides.append({
            "id": item.get("id"),
            "titre": item.get("title"),
            "entreprise": item.get("company", "Non spécifié"),
            "lieu": item.get("location", "Lille"),
            "description": item.get("snippet", ""),
            "lien": item.get("link") # Lien direct de l'offre
        })
    return valides

# 2. ADZUNA API
def recuperer_offres_adzuna(app_id, app_key):
    url = "https://api.adzuna.com/v1/api/jobs/fr/search/1"
    params = {
        "app_id": app_id,
        "app_key": app_key,
        "what": "restauration",
        "where": "Lille",
        "results_per_page": 40,
        "content-type": "application/json"
    }
    try:
        r = requests.get(url, params=params)
        r.raise_for_status()
        return r.json().get("results", [])
    except Exception as e:
        st.error(f"Erreur d'appel API Adzuna : {e}")
        return []

def filtrer_offres_adzuna(offres):
    valides = []
    exclusions_alternance = ["alternance", "apprentissage", "professionnalisation", "contrat pro", "apprenti", "alternant"]
    exclusions_voiture = ["permis b exigé", "véhicule indispensable", "permis obligatoire", "voiture personnelle", "permis b obligatoire"]
    exclusions_longs_contrats = ["6 mois", "12 mois", "un an", "1 an", "2 ans", "longue durée", "cdi", "durée indéterminée"]

    for item in offres:
        titre = item.get("title", "").lower()
        desc = item.get("description", "").lower()

        if any(mot in titre or mot in desc for mot in exclusions_alternance):
            continue
        if any(mot in titre or mot in desc for mot in exclusions_voiture):
            continue
        if any(mot in titre or mot in desc for mot in exclusions_longs_contrats):
            continue

        valides.append({
            "id": item.get("id"),
            "titre": item.get("title"),
            "entreprise": item.get("company", {}).get("display_name", "Non spécifié"),
            "lieu": item.get("location", {}).get("display_name", "Lille"),
            "description": item.get("description", ""),
            "lien": item.get("redirect_url") # Lien direct Adzuna
        })
    return valides

# 3. FRANCE TRAVAIL API
def obtenir_token_ft(client_id, client_secret):
    url = "https://entreprise.francetravail.fr/connexion/oauth2/access_token?realm=/partenaire"
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    data = {
        "grant_type": "client_credentials",
        "client_id": client_id,
        "client_secret": client_secret,
        "scope": "api_offresdemploiv2 o2dsoffre"
    }
    try:
        r = requests.post(url, headers=headers, data=data)
        r.raise_for_status()
        return r.json().get("access_token")
    except Exception as e:
        st.error(f"Erreur d'authentification France Travail : {e}")
        return None

def recuperer_offres_ft(token):
    url = "https://api.francetravail.io/partenaire/offresdemploi/v2/offres/search"
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
    params = {
        "commune": "59350",
        "motsCles": "restauration",
        "publieeDepuis": "14",
        "typeContrat": "CDD,SAI",
        "range": "0-49"
    }
    try:
        r = requests.get(url, headers=headers, params=params)
        if r.status_code == 204:
            return []
        r.raise_for_status()
        return r.json().get("resultats", [])
    except Exception as e:
        st.error(f"Erreur de récupération France Travail : {e}")
        return []

def filtrer_offres_ft(offres):
    valides = []
    exclusions_alternance = ["alternance", "apprentissage", "professionnalisation", "contrat pro", "apprenti", "alternant"]
    exclusions_voiture = ["permis b exigé", "véhicule indispensable", "permis obligatoire", "voiture personnelle", "permis b obligatoire"]
    exclusions_longs_contrats = ["6 mois", "12 mois", "un an", "1 an", "2 ans", "longue durée"]

    for item in offres:
        titre = item.get("intitule", "").lower()
        desc = item.get("description", "").lower()
        is_alternance = item.get("alternance", False)

        if is_alternance:
            continue
        if any(mot in titre or mot in desc for mot in exclusions_alternance):
            continue
        if any(mot in titre or mot in desc for mot in exclusions_voiture):
            continue
        if any(mot in titre or mot in desc for mot in exclusions_longs_contrats):
            continue

        valides.append({
            "id": item.get("id"),
            "titre": item.get("intitule"),
            "entreprise": item.get("entreprise", {}).get("nom", "Non spécifié"),
            "lieu": item.get("lieu", {}).get("libelle", "Lille"),
            "description": item.get("description", ""),
            "lien": f"https://candidat.pole-emploi.fr/offres/recherche/detail/{item.get('id')}"
        })
    return valides

# =====================================================================
# SYSTEME DE GENERATION DE LETTRE
# =====================================================================
def generer_lettre(offre, key):
    client = OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=key,
        default_headers={"HTTP-Referer": "http://localhost:3000", "X-Title": "CV Bot Louis"}
    )
    prompt = f"""
    Rédige une lettre de motivation professionnelle et percutante pour un job d'été d'un mois en restauration.
    
    Candidat :
    - Nom : {PROFIL_LOUIS['nom']}
    - Profil : Étudiant en école d'ingénieur au CESI. Recherche un job d'été (restauration/accueil) à Lille.
    - Disponibilité : {PROFIL_LOUIS['disponibilite']} (disponible immédiatement et uniquement du 1er au 31 août 2026).
    - Compétences : {PROFIL_LOUIS['competences']}
    - Expériences : {PROFIL_LOUIS['experiences']}
    - Contact : {PROFIL_LOUIS['email']} | {PROFIL_LOUIS['telephone']}
    
    Offre :
    - Poste : {offre.get('titre')}
    - Entreprise : {offre.get('entreprise')}
    - Description : {offre.get('description')[:1000]}
    
    Instructions :
    - Rédige en français. Sois poli, dynamique et motivé.
    - Précise que tu habites à Lille et que tu utilises les transports en commun métro/bus (pas besoin de voiture).
    - IMPORTANT : Explique très clairement que tu proposes tes services spécifiquement pour le mois d'août 2026 pour un contrat de 1 mois (remplacement saisonnier idéal).
    - Fais court (environ 200 mots).
    """
    try:
        response = client.chat.completions.create(
            model="openrouter/free",  # Utilise automatiquement le modèle gratuit du moment
            messages=[
                {"role": "system", "content": "Tu es un consultant en recrutement."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"Erreur lors de la rédaction de la lettre : {e}"

# =====================================================================
# INTERFACE PRINCIPALE STREAMLIT
# =====================================================================

# Étape d'alerte si la clé OpenRouter n'est pas configurée
if not openai_key:
    st.info("💡 Saisissez votre clé API OpenRouter dans la barre latérale pour activer la rédaction automatique de lettres de motivation.")

# Déclencheur principal de recherche
if st.button(f"🔍 Rechercher les offres sur {source_recherche}"):
    offres_valides = []

    with st.spinner("Recherche d'offres en cours..."):
        # 1. Traitement Jooble
        if source_recherche == "Jooble (Recommandé)":
            if not api_jooble:
                st.warning("Veuillez saisir votre clé API Jooble.")
            else:
                offres_brutes = recuperer_offres_jooble(api_jooble)
                offres_valides = filtrer_offres_jooble(offres_brutes)

        # 2. Traitement Adzuna
        elif source_recherche == "Adzuna":
            if not api_adzuna_id or not api_adzuna_key:
                st.warning("Veuillez saisir votre App ID et App Key pour Adzuna.")
            else:
                offres_brutes = recuperer_offres_adzuna(api_adzuna_id, api_adzuna_key)
                offres_valides = filtrer_offres_adzuna(offres_brutes)

        # 3. Traitement France Travail
        elif source_recherche == "France Travail":
            if not ft_client_id or not ft_client_secret:
                st.warning("Veuillez configurer vos accès France Travail.")
            else:
                token = obtenir_token_ft(ft_client_id, ft_client_secret)
                if token:
                    offres_brutes = recuperer_offres_ft(token)
                    offres_valides = filtrer_offres_ft(offres_brutes)

        # Sauvegarde en mémoire session de Streamlit
        st.session_state["offres_web"] = offres_valides
        if offres_valides:
            st.success(f"{len(offres_valides)} offres d'emploi validées (CDD d'août sans permis ni voiture) !")
        else:
            st.error("Aucune offre valide trouvée avec vos critères de recherche.")

# Affichage dynamique des résultats et bouton de rédaction
if "offres_web" in st.session_state and st.session_state["offres_web"]:
    for index, offre in enumerate(st.session_state["offres_web"]):
        titre = offre.get('titre')
        entreprise = offre.get('entreprise')
        lieu = offre.get('lieu')
        lien = offre.get('lien')
        
        with st.expander(f"📌 {titre} - {entreprise} ({lieu})"):
            st.write(f"**Lien officiel :** [Consulter et postuler à l'offre]({lien})")
            st.text_area("Description du poste", offre.get("description", ""), height=150, disabled=True, key=f"desc_{offre.get('id')}_{index}")
            
            if st.button("✨ Rédiger ma lettre de motivation", key=f"btn_{offre.get('id')}_{index}"):
                if not openai_key:
                    st.error("Action impossible : Entrez votre clé OpenRouter dans la barre latérale pour générer la lettre.")
                else:
                    with st.spinner("Rédaction en cours par l'IA..."):
                        lettre_redigee = generer_lettre(offre, openai_key)
                        st.text_area("Lettre de motivation générée", lettre_redigee, height=300, key=f"lettre_{offre.get('id')}_{index}")

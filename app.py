import streamlit as st
import requests
import os
from bs4 import BeautifulSoup
from openai import OpenAI

# =====================================================================
# ENREGISTREZ VOTRE CLÉ OPENROUTER ICI POUR QU'ELLE SOIT PRÉ-REMPLIE
# =====================================================================
CLE_OPENROUTER_PAR_DEFAUT = "sk-or-v1-VOTRE_CLE_REELLE" # <--- Remplacez par votre clé sk-or-v1...

# Configuration de la page web
st.set_page_config(page_title="Louis - Multi-Source Job d'Été", page_icon="💼", layout="wide")

st.title("💼 Assistant Job d'Été Multi-Source")
st.write("Ce bot vous aide à trouver des contrats saisonniers à Lille pour août et rédige vos lettres de motivation.")

# Barre latérale : Choix du mode d'utilisation
st.sidebar.header("Navigation")
mode_utilisation = st.sidebar.radio(
    "Choisissez une action :",
    ["🔍 Recherche automatique", "✍️ Rédiger depuis une annonce copiée"]
)

st.sidebar.write("---")
st.sidebar.header("Configuration des Clés API")

# Utilise la clé par défaut si elle est configurée
openai_key = st.sidebar.text_input("Clé API OpenRouter", value=CLE_OPENROUTER_PAR_DEFAUT, type="password")

# Paramètres selon le mode choisi
if mode_utilisation == "🔍 Recherche automatique":
    source_recherche = st.sidebar.selectbox(
        "Source de recherche d'emploi",
        ["Jooble (Recommandé)", "Adzuna", "France Travail", "LinkedIn (via Apify)"]
    )
    
    # Clés API pré-remplies
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
    elif source_recherche == "LinkedIn (via Apify)":
        apify_token = st.sidebar.text_input("Apify API Token (Requis)", type="password", placeholder="apify_api_...")

# Profil du candidat (Louis Guiffant)
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
# FONCTIONS D'APPEL AUX APIS & SCRAPING DE LIENS
# =====================================================================

def extraire_texte_url(url):
    """Tente d'ouvrir un lien d'annonce et de nettoyer le texte pour l'IA."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    try:
        r = requests.get(url, headers=headers, timeout=10)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        
        # Supprime le code javascript et CSS inutile
        for element in soup(["script", "style", "nav", "footer", "header"]):
            element.decompose()
            
        texte_brut = soup.get_text(separator="\n")
        # Nettoyage des espaces blancs multiples
        lignes = (line.strip() for line in texte_brut.splitlines())
        blocs = (phrase.strip() for line in lignes for phrase in line.split("  "))
        texte_propre = "\n".join(b for b in blocs if b)
        
        return texte_propre[:2500]  # Limite aux 2500 premiers caractères utiles
    except Exception as e:
        return None

# 1. JOOBLE API
def recuperer_offres_jooble(api_key):
    url = f"https://jooble.org/api/{api_key}"
    headers = {"Content-Type": "application/json"}
    payload = {
        "keywords": "restauration",
        "location": "Lille, France",
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
        desc = item.get("snippet", "").lower()

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
            "lien": item.get("link")
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
            "lien": item.get("redirect_url")
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

# 4. LINKEDIN VIA APIFY
def recuperer_offres_linkedin(apify_token):
    url = f"https://api.apify.com/v2/acts/solidcode~linkedin-jobs-scraper/run-sync-get-dataset-items?token={apify_token}"
    headers = {"Content-Type": "application/json"}
    payload = {
        "keywords": "restauration",
        "location": "Lille, France",
        "maxResults": 15,
        "datePosted": "any"
    }
    try:
        r = requests.post(url, headers=headers, json=payload)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        st.error(f"Erreur lors du scraping LinkedIn via Apify : {e}")
        return []

def filtrer_offres_linkedin(offres):
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

        entreprise_data = item.get("company", "Non spécifié")
        nom_entreprise = entreprise_data.get("name", "Non spécifié") if isinstance(entreprise_data, dict) else str(entreprise_data)

        valides.append({
            "id": item.get("id"),
            "titre": item.get("title"),
            "entreprise": nom_entreprise,
            "lieu": item.get("location", "Lille"),
            "description": item.get("description", ""),
            "lien": item.get("link") or f"https://www.linkedin.com/jobs/view/{item.get('id')}"
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
    - Description : {offre.get('description')[:1200]}
    
    Instructions :
    - Rédige en français. Sois poli, dynamique et motivé.
    - Précise que tu habites à Lille et que tu utilises les transports en commun métro/bus (pas besoin de voiture).
    - IMPORTANT : Explique très clairement que tu proposes tes services spécifiquement pour le mois d'août 2026 pour un contrat de 1 mois (remplacement de vacances ou surcroît saisonnier idéal).
    - Fais court (environ 200 mots).
    """
    try:
        response = client.chat.completions.create(
            model="openrouter/free",
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

if not openai_key or "VOTRE_CLE" in openai_key:
    st.info("💡 Saisissez votre clé API OpenRouter dans la barre latérale pour activer la rédaction de lettres de motivation.")

# MODE 1 : RECHERCHE AUTOMATIQUE
if mode_utilisation == "🔍 Recherche automatique":
    st.subheader(f"Recherche en direct sur {source_recherche}")
    
    if st.button(f"🔍 Rechercher les offres sur {source_recherche}"):
        offres_valides = []

        with st.spinner("Recherche d'offres en cours..."):
            if source_recherche == "Jooble (Recommandé)":
                if not api_jooble:
                    st.warning("Veuillez saisir votre clé API Jooble.")
                else:
                    offres_brutes = recuperer_offres_jooble(api_jooble)
                    offres_valides = filtrer_offres_jooble(offres_brutes)

            elif source_recherche == "Adzuna":
                if not api_adzuna_id or not api_adzuna_key:
                    st.warning("Veuillez saisir votre App ID et App Key pour Adzuna.")
                else:
                    offres_brutes = recuperer_offres_adzuna(api_adzuna_id, api_adzuna_key)
                    offres_valides = filtrer_offres_adzuna(offres_brutes)

            elif source_recherche == "France Travail":
                if not ft_client_id or not ft_client_secret:
                    st.warning("Veuillez configurer vos accès France Travail.")
                else:
                    token = obtenir_token_ft(ft_client_id, ft_client_secret)
                    if token:
                        offres_brutes = recuperer_offres_ft(token)
                        offres_valides = filtrer_offres_ft(offres_brutes)

            elif source_recherche == "LinkedIn (via Apify)":
                if not apify_token:
                    st.warning("Veuillez renseigner votre API Token d'Apify.")
                else:
                    offres_brutes = recuperer_offres_linkedin(apify_token)
                    offres_valides = filtrer_offres_linkedin(offres_brutes)

            st.session_state["offres_web"] = offres_valides
            if offres_valides:
                st.success(f"{len(offres_valides)} offres d'emploi validées (CDD d'août sans permis ni voiture) !")
            else:
                st.error("Aucune offre valide trouvée correspondant à vos critères d'accessibilité.")

    # Affichage des résultats de recherche
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
                    if not openai_key or "VOTRE_CLE" in openai_key:
                        st.error("Action impossible : Entrez votre clé OpenRouter valide dans la barre latérale.")
                    else:
                        with st.spinner("Rédaction en cours par l'IA..."):
                            lettre_redigee = generer_lettre(offre, openai_key)
                            st.text_area("Lettre de motivation générée", lettre_redigee, height=300, key=f"lettre_{offre.get('id')}_{index}")

# MODE 2 : COPIER-COLLER D'UNE ANNONCE (INDEED, HELLOWORK, ETC.)
elif mode_utilisation == "✍️ Rédiger depuis une annonce copiée":
    st.subheader("Rédigez votre lettre à partir d'un lien ou d'un copier-coller")
    st.write("Entrez le lien de l'annonce d'emploi pour tenter d'en extraire la description automatiquement :")
    
    # Zone d'import de lien
    url_saisie = st.text_input("Coller le lien de l'annonce (Indeed, HelloWork, LinkedIn, etc.)", placeholder="https://...")
    
    if url_saisie:
        if st.button("📥 Tenter de récupérer le texte de l'annonce automatiquement"):
            with st.spinner("Analyse et extraction de la page..."):
                texte_extrait = extraire_texte_url(url_saisie)
                if texte_extrait:
                    st.session_state["desc_saisie_manuelle"] = texte_extrait
                    st.success("Texte de l'annonce extrait avec succès ! Vous pouvez le relire ou le modifier ci-dessous.")
                else:
                    st.warning("Cette plateforme d'emploi bloque l'extraction automatisée (sécurité Cloudflare). Veuillez copier-coller manuellement le texte de l'annonce ci-dessous.")

    st.write("---")
    
    # Formulaire de saisie manuelle
    col1, col2 = st.columns(2)
    with col1:
        titre_saisi = st.text_input("Intitulé du poste recherché (Ex: Serveur de bar, Commis de cuisine)")
    with col2:
        entreprise_saisie = st.text_input("Nom de l'établissement / entreprise (Ex: Bistrot de la Gare)")
        
    # On charge la description extraite (ou vide par défaut)
    default_desc = st.session_state.get("desc_saisie_manuelle", "")
    description_saisie = st.text_area(
        "Texte ou description complète de l'annonce d'emploi", 
        value=default_desc, 
        height=250, 
        placeholder="Collez ici l'intégralité du texte de l'annonce d'emploi (obligatoire si la récupération de lien a échoué)."
    )

    if st.button("✨ Rédiger ma lettre de motivation sur mesure"):
        if not openai_key or "VOTRE_CLE" in openai_key:
            st.error("Action impossible : Veuillez d'abord renseigner votre clé OpenRouter valide dans la barre latérale gauche.")
        elif not titre_saisi or not description_saisie:
            st.warning("Veuillez renseigner au moins l'intitulé du poste et la description de l'annonce.")
        else:
            # Structuration de l'offre
            offre_manuelle = {
                "titre": titre_saisi,
                "entreprise": entreprise_saisie if entreprise_saisie else "votre établissement",
                "description": description_saisie
            }
            
            with st.spinner("Rédaction en cours par l'IA..."):
                lettre_manuelle = generer_lettre(offre_manuelle, openai_key)
                if lettre_manuelle:
                    st.success("Votre lettre de motivation sur mesure pour le mois d'août est prête !")
                    st.text_area("Lettre de motivation générée", lettre_manuelle, height=400)

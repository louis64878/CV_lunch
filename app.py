import streamlit as st
import requests
import os
from openai import OpenAI

# Configuration de la page web
st.set_page_config(page_title="Louis - Assistant Job d'Été", page_icon="💼", layout="wide")

st.title("💼 Assistant de Recherche de Job d'Été à Lille")
st.write("Ce bot recherche des contrats saisonniers en restauration pour le mois d'août à Lille, accessibles sans voiture.")

# Barre latérale pour entrer les clés API
st.sidebar.header("Configuration")
openai_key = st.sidebar.text_input("Clé API OpenRouter", type="password", placeholder="sk-or-v1-...")
ft_client_id = st.sidebar.text_input("Client ID France Travail", type="password")
ft_client_secret = st.sidebar.text_input("Client Secret France Travail", type="password")

# Informations du candidat
PROFIL_LOUIS = {
    "nom": "Louis Guiffant",
    "email": "guiffantlouis123@gmail.com",
    "telephone": "0768445324",
    "ville": "Lille",
    "etudes": "École d'ingénieur au CESI",
    "disponibilite": "Disponible uniquement durant tout le mois d'août 2026 (contrat de 1 mois complet)",
    "competences": "Restauration, service en salle, polyvalence, sens du contact, dynamique, rigoureux",
    "langues": "Français (Langue maternelle), Anglais (Courant)",
    "experiences": "Bénévole (organisation d'événements, vente), stages d'observation en entreprise (Airbus Atlantic, prothésiste)"
}

# Fonctions d'API
def obtenir_token(client_id, client_secret):
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

def recuperer_offres(token):
    url = "https://api.francetravail.io/partenaire/offresdemploi/v2/offres/search"
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
    params = {
        "commune": "59350",          # Lille
        "motsCles": "restauration",
        "publieeDepuis": "14",        # Offres des 14 derniers jours pour élargir le choix
        "typeContrat": "CDD,SAI",    # CDD et Saisonnier uniquement
        "range": "0-49"              # Récupère jusqu'à 50 offres
    }
    try:
        r = requests.get(url, headers=headers, params=params)
        if r.status_code == 204:
            return []
        r.raise_for_status()
        return r.json().get("resultats", [])
    except Exception as e:
        st.error(f"Erreur lors de la récupération des offres : {e}")
        return []

def filtrer_offres(offres):
    valides = []
    
    # Listes de filtres d'exclusion
    exclusions_alternance = ["alternance", "apprentissage", "professionnalisation", "contrat pro", "apprenti", "alternant"]
    exclusions_voiture = ["permis b exigé", "véhicule indispensable", "permis obligatoire", "voiture personnelle", "permis b obligatoire"]
    exclusions_longs_contrats = ["6 mois", "12 mois", "un an", "1 an", "2 ans", "longue durée"]

    for item in offres:
        titre = item.get("intitule", "").lower()
        desc = item.get("description", "").lower()
        is_alternance = item.get("alternance", False) # Détection de l'alternance par l'API

        # 1. Exclure si l'offre est officiellement une alternance
        if is_alternance:
            continue

        # 2. Exclure si des mots-clés d'alternance sont présents
        if any(mot in titre or mot in desc for mot in exclusions_alternance):
            continue

        # 3. Exclure si l'offre exige un permis ou un véhicule
        if any(mot in titre or mot in desc for mot in exclusions_voiture):
            continue

        # 4. Exclure si l'offre mentionne explicitement un contrat de longue durée
        if any(mot in desc for mot in exclusions_longs_contrats):
            continue

        # Sauvegarde des offres nettoyées
        valides.append({
            "id": item.get("id"),
            "titre": item.get("intitule"),
            "entreprise": item.get("entreprise", {}).get("nom", "Non spécifié"),
            "lieu": item.get("lieu", {}).get("libelle", "Lille"),
            "description": item.get("description", "")
        })
    return valides

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
    - IMPORTANT : Explique très clairement au recruteur que tu proposes tes services spécifiquement pour le mois d'août 2026 pour un contrat de 1 mois (idéal pour un remplacement de vacances ou un renfort saisonnier).
    - Fais court (environ 200 mots).
    """
    try:
        response = client.chat.completions.create(
            model="openrouter/free"
            messages=[
                {"role": "system", "content": "Tu es un consultant en recrutement."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"Erreur lors de la rédaction de la lettre : {e}"

# Logique de l'interface utilisateur
if not (openai_key and ft_client_id and ft_client_secret):
    st.info("💡 Veuillez entrer vos clés d'API dans la barre latérale gauche pour activer le robot.")
else:
    if st.button("🔍 Rechercher des offres réelles à Lille"):
        with st.spinner("Recherche en cours sur France Travail..."):
            token = obtenir_token(ft_client_id, ft_client_secret)
            if token:
                offres_brutes = recuperer_offres(token)
                offres_valides = filtrer_offres(offres_brutes)
                st.session_state["offres_web"] = offres_valides
                st.success(f"{len(offres_valides)} offres valides trouvées (CDD courts, sans voiture, hors alternance) !")

# Affichage des résultats
if "offres_web" in st.session_state and st.session_state["offres_web"]:
    for index, offre in enumerate(st.session_state["offres_web"]):
        titre = offre.get('titre')
        entreprise = offre.get('entreprise')
        lieu = offre.get('lieu')
        
        with st.expander(f"📌 {titre} - {entreprise} ({lieu})"):
            st.write(f"**Lien officiel :** [Consulter l'offre sur France Travail](https://candidat.pole-emploi.fr/offres/recherche/detail/{offre.get('id')})")
            st.text_area("Description du poste", offre.get("description", ""), height=150, disabled=True, key=f"desc_{offre.get('id')}")
            
            if st.button("✨ Rédiger ma lettre de motivation", key=f"btn_{offre.get('id')}"):
                with st.spinner("Rédaction en cours..."):
                    lettre_redigee = generer_lettre(offre, openai_key)
                    st.text_area("Lettre de motivation générée", lettre_redigee, height=300, key=f"lettre_{offre.get('id')}")

import streamlit as st
import requests
import os
from openai import OpenAI

# Configuration de la page web
st.set_page_config(page_title="Louis - Assistant Job d'Été", page_icon="💼", layout="wide")

st.title("💼 Assistant de Recherche de Job d'Été à Lille")
st.write("Ce bot recherche des jobs en restauration à Lille accessibles sans voiture et rédige vos lettres de motivation.")

# Barre latérale pour entrer les clés API de façon sécurisée
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
        "publieeDepuis": "7",         # MODIFIÉ : 7 est une valeur autorisée (offres de la semaine)
        "range": "0-29"              # Récupère les 30 premières offres d'un coup
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
    exclusions = ["permis b exigé", "véhicule indispensable", "permis obligatoire", "voiture personnelle", "permis b obligatoire"]
    for item in offres:
        titre = item.get("intitule", "").lower()
        desc = item.get("description", "").lower()
        if not any(mot in desc or mot in titre for mot in exclusions):
            valides.append(item)
    return valides

def generer_lettre(offre, key):
    client = OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=key,
        default_headers={"HTTP-Referer": "http://localhost:3000", "X-Title": "CV Bot Louis"}
    )
    prompt = f"""
    Rédige une lettre de motivation professionnelle pour un job d'été en restauration.
    
    Candidat :
    - Nom : {PROFIL_LOUIS['nom']}
    - Profil : Étudiant en école d'ingénieur au CESI. Recherche un job d'été (restauration/accueil) à Lille.
    - Compétences : {PROFIL_LOUIS['competences']}
    - Expériences : {PROFIL_LOUIS['experiences']}
    - Contact : {PROFIL_LOUIS['email']} | {PROFIL_LOUIS['telephone']}
    
    Offre :
    - Poste : {offre.get('intitule')}
    - Entreprise : {offre.get('entreprise', {}).get('nom', 'L\'établissement')}
    - Description : {offre.get('description', '')[:1000]}
    
    Instructions : Rédige en français, sois poli, professionnel et motivé. Précise que tu habites à Lille et que tu utilises les transports en commun (pas besoin de voiture). Fais court (200 mots).
    """
    try:
        response = client.chat.completions.create(
            model="meta-llama/llama-3-8b-instruct:free",
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
                st.success(f"{len(offres_valides)} offres trouvées !")

# Affichage des résultats
if "offres_web" in st.session_state and st.session_state["offres_web"]:
    for index, offre in enumerate(st.session_state["offres_web"]):
        titre = offre.get('intitule')
        entreprise = offre.get('entreprise', {}).get('nom', 'Non spécifié')
        lieu = offre.get('lieu', {}).get('libelle', 'Lille')
        
        with st.expander(f"📌 {titre} - {entreprise} ({lieu})"):
            st.write(f"**Lien officiel :** [Consulter l'offre sur France Travail](https://candidat.pole-emploi.fr/offres/recherche/detail/{offre.get('id')})")
            st.text_area("Description du poste", offre.get("description", ""), height=150, disabled=True, key=f"desc_{offre.get('id')}")
            
            if st.button("✨ Rédiger ma lettre de motivation", key=f"btn_{offre.get('id')}"):
                with st.spinner("Rédaction en cours..."):
                    lettre_redigee = generer_lettre(offre, openai_key)
                    st.text_area("Lettre de motivation générée", lettre_redigee, height=300, key=f"lettre_{offre.get('id')}")

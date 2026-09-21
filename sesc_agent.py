import os
import re
import urllib.parse
import requests
from bs4 import BeautifulSoup
import google.generativeai as genai

# Configurações via variáveis de ambiente
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
WHATSAPP_PHONE = os.getenv("WHATSAPP_PHONE")
CALLMEBOT_API_KEY = os.getenv("CALLMEBOT_API_KEY")

SESC_URL = "https://www.sescsp.org.br/programacao/"

# Configura o SDK do Gemini
genai.configure(api_key=GEMINI_API_KEY)

UNIDADES_ALVO = [
    "Santo André", "São Caetano",
    "Vila Mariana", "Pompeia", "Pinheiros", "Belenzinho", "Consolação",
    "Avenida Paulista", "14 Bis", "CineSesc", "Bom Retiro", "Carmo",
    "Centro de Pesquisa e Formação", "Ipiranga", "Santana", "Interlagos",
    "Itaquera", "Campo Limpo", "Santo Amaro", "24 de Maio", "Florêncio de Abreu"
]

def extrair_eventos_sesc():
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    }
    try:
        response = requests.get(SESC_URL, headers=headers, timeout=20)
        response.raise_for_status()
    except Exception as e:
        print(f"Erro na requisição: {e}")
        return []

    soup = BeautifulSoup(response.text, "html.parser")
    cards = soup.find_all("article") or soup.find_all("div", class_=re.compile(r"card|item|programacao"))
    
    eventos_brutos = []
    for card in cards:
        texto = card.get_text(separator=" ", strip=True)
        link_elem = card.find("a", href=True)
        link = link_elem["href"] if link_elem else ""
        if link and not link.startswith("http"):
            link = "https://www.sescsp.org.br" + link
            
        if texto:
            pertence_regiao = any(unidade.lower() in texto.lower() for unidade in UNIDADES_ALVO)
            if pertence_regiao or "sesc" in texto.lower():
                eventos_brutos.append(f"{texto} | Link: {link}")
                
    return eventos_brutos[:45]

def curadoria_gemini(eventos):
    if not eventos:
        return None

    texto_eventos = "\n---\n".join(eventos)

    prompt = f"""
Você é um curador cultural especializado e assistente pessoal de um casal em São Paulo/ABC Paulista.
Eles odeiam perder eventos legais por falta de aviso e detestam navegar no guia mensal lotado de atrações genéricas.

SEU OBJETIVO:
Analisar a lista de eventos brutos do Sesc SP e selecionar APENAS experiências que valham a pena (alta probabilidade de esgotar ou temática nichada/interessante).

PERFIL DE INTERESSE:
- AMAM:
  * Oficinas práticas manuais ou criativas (cerâmica, marcenaria, gravura, artes visuais, criação musical, laboratórios de tecnologia/ETA).
  * Cinema com proposta imersiva ou diferenciada (sessões temáticas, cinema ao ar livre/piscina, mostras de diretores de culto, debates com realizadores, sessões no CineSesc).
  * Shows e apresentações com artistas relevantes, independentes ou inusitados (ex: Supla cantando clássicos, encontros com artistas do rap como Hariel em formatos diferentes, batalhas de arte/Art Battle).
  * Artes visuais e exposições impactantes (estilo Grada Kilomba, intervenções, instalações conceituais).
  * Unidades de interesse: Capital (especialmente Pompeia, Vila Mariana, Pinheiros, Paulista, CineSesc, etc.) e ABC (Santo André e São Caetano).

- ODEIAM / EXCLUIR TOTALMENTE:
  * Qualquer programação infantil, contação de histórias para crianças, bebês ou famílias.
  * Ginástica multifuncional básica, zumba, caminhada, pilates, yoga comum, hidroginástica.
  * Reuniões institucionais ou palestras corporativas burocráticas.
  * Atrações sem originalidade ou genéricas.

EVENTOS BRUTOS:
---
{texto_eventos}
---

FORMATO DE RESPOSTA (direto para WhatsApp):
Selecione os melhores (de 2 a 5 destaques máximos). Para cada um:
🎟️ *[Nome da Atração]*
📍 *Local:* [Unidade do Sesc - Espaço]
🗓️ *Quando:* [Data e horário]
💡 *Por que vale a pena:* [1 frase direta destacando a singularidade da experiência]
🔗 *Link:* [URL direta]

Se nenhum evento tiver o nível de qualidade e interesse esperado, responda rigorosamente com: "NADA_RELEVANTE".
"""

    model = genai.GenerativeModel("gemini-2.5-flash")
    response = model.generate_content(prompt)
    return response.text.strip()

def enviar_whatsapp(mensagem):
    encoded_message = urllib.parse.quote(mensagem)
    url = f"https://api.callmebot.com/whatsapp.php?phone={WHATSAPP_PHONE}&text={encoded_message}&apikey={CALLMEBOT_API_KEY}"
    try:
        res = requests.get(url, timeout=15)
        if res.status_code == 200:
            print("Mensagem enviada com sucesso ao WhatsApp!")
        else:
            print(f"Erro CallMeBot: {res.status_code} - {res.text}")
    except Exception as e:
        print(f"Falha de conexão com CallMeBot: {e}")

if __name__ == "__main__":
    eventos = extrair_eventos_sesc()
    resultado = curadoria_gemini(eventos)
    
    if resultado and resultado != "NADA_RELEVANTE":
        cabecalho = "⚡ *RADAR SESC SP & ABC (Novidades Selecionadas)* ⚡\n\n"
        enviar_whatsapp(cabecalho + resultado)
    else:
        print("Nenhum evento relevante nesta rodada. Nenhuma mensagem disparada.")

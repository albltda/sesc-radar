import os
import urllib.parse
from bs4 import BeautifulSoup
from google import genai
import requests

# 1. Carrega variáveis de ambiente (configuradas nos Secrets do GitHub)
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
WHATSAPP_PHONE = os.environ.get("WHATSAPP_PHONE")
CALLMEBOT_API_KEY = os.environ.get("CALLMEBOT_API_KEY")

# Unidades de interesse: Capital e Grande ABC
UNIDADES_ALVO = [
    "santo andré",
    "são bernardo",
    "são caetano",
    "pompeia",
    "pinheiros",
    "avenida paulista",
    "cinesesc",
    "belenzinho",
    "vila mariana",
    "bom retiro",
    "consolação",
    "24 de maio",
    "itaim paulista",
    "santana",
    "ipiranga",
]


def coletar_eventos_sesc():
    """Raspagem da página de programação do Sesc SP."""
    url = "https://www.sescsp.org.br/programacao/"
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
    }

    try:
        response = requests.get(url, headers=headers, timeout=20)
        response.raise_for_status()
    except Exception as e:
        print(f"Erro ao acessar o portal do Sesc: {e}")
        return []

    soup = BeautifulSoup(response.text, "html.parser")
    eventos_encontrados = []

    # Procura blocos ou itens de programação no portal
    cards = soup.find_all(
        ["article", "div"],
        class_=lambda c: c and any(k in c.lower() for k in ["card", "item", "programacao"]),
    )

    for card in cards:
        texto = card.get_text(separator=" ", strip=True)
        if len(texto) < 30:
            continue

        texto_lower = texto.lower()
        # Filtra se pertence às unidades da Capital ou ABC
        pertence_alvo = any(u in texto_lower for u in UNIDADES_ALVO)

        if pertence_alvo:
            link_tag = card.find("a", href=True)
            link = link_tag["href"] if link_tag else ""
            if link and not link.startswith("http"):
                link = f"https://www.sescsp.org.br{link}"

            eventos_encontrados.append(f"- {texto} | Link: {link}")

    # Fallback se a estrutura do portal mudar e a classe específica não capturar
    if not eventos_encontrados:
        todos_links = soup.find_all("a", href=True)
        for a in todos_links:
            txt = a.get_text(strip=True)
            txt_lower = txt.lower()
            if any(u in txt_lower for u in UNIDADES_ALVO) and len(txt) > 20:
                link = (
                    a["href"]
                    if a["href"].startswith("http")
                    else f"https://www.sescsp.org.br{a['href']}"
                )
                eventos_encontrados.append(f"- {txt} | Link: {link}")

    return eventos_encontrados[:30]


def filtrar_com_gemini(eventos):
    """Usa o Gemini 2.5 Flash para selecionar e sintetizar os destaques."""
    if not eventos:
        return "Nenhum evento relevante encontrado nas unidades da Capital e ABC hoje."

    client = genai.Client(api_key=GEMINI_API_KEY)

    # Une os eventos antes para evitar o erro de backslash dentro da f-string
    eventos_formatados = "\n".join(eventos)

    prompt = f"""
Você é um curador cultural especializado na programação do Sesc SP (focado na Capital e Grande ABC).
Analise a lista bruta de eventos abaixo e filtre os melhores destaques.
Dê preferência para:
- Cinema (CineSesc, mostras especiais, cineclubes)
- Fotografia, artes visuais e oficinas práticas
- Debates, literatura, humanidades e sociedade
- Espetáculos e apresentações teatrais

Gere uma mensagem compacta, organizada por tópicos e pronta para envio via WhatsApp, com emojis e links curtos quando disponíveis.
Limite a mensagem a no máximo 1000 caracteres para não estourar o limite do mensageiro.

Eventos brutos:
{eventos_formatados}
"""

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
    )
    return response.text


def enviar_whatsapp(mensagem):
    """Dispara a mensagem formatada via CallMeBot."""
    if not WHATSAPP_PHONE or not CALLMEBOT_API_KEY:
        print("Credenciais do WhatsApp/CallMeBot não configuradas.")
        return

    msg_encoded = urllib.parse.quote(mensagem)
    url = f"https://api.callmebot.com/whatsapp.php?phone={WHATSAPP_PHONE}&text={msg_encoded}&apikey={CALLMEBOT_API_KEY}"

    try:
        res = requests.get(url, timeout=25)
        if res.status_code == 200:
            print("Mensagem enviada com sucesso ao WhatsApp!")
        else:
            print(f"Falha no envio via CallMeBot. Status: {res.status_code}, Resposta: {res.text}")
    except Exception as e:
        print(f"Erro na requisição para o CallMeBot: {e}")


def main():
    print("Iniciando coleta no portal do Sesc SP...")
    eventos = coletar_eventos_sesc()
    print(f"Total de itens pré-filtrados (Capital e ABC): {len(eventos)}")

    print("Passando curadoria pelo Gemini 2.5 Flash...")
    resumo = filtrar_com_gemini(eventos)
    print("\n--- RESUMO GERADO ---\n", resumo, "\n---------------------\n")

    print("Disparando notificação no WhatsApp...")
    enviar_whatsapp(resumo)


if __name__ == "__main__":
    main()

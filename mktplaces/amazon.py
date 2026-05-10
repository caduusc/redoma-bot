from modulos.playwright_func import (
    navigate, human_fill, human_click,
    find_element, extract_value, human_delay, human_click_locator, select_amazon_trackid
)

async def gerar_link_amazon(page, product_url: str, tag: str) -> dict:

    try:
        await navigate(page, product_url)
        btn_gerar = await find_element(page, [
            "#amzn-ss-get-link-button",
            "button[title='Obter link']",
            "button:has-text('Obter link')",
        ])
        if not btn_gerar:
            return {"success": False, "affiliate_link": None, "error": "Botão Gerar não encontrado."}

        await select_amazon_trackid(page, tag)

        btn = await find_element(page, [
            "#amzn-ss-get-link-btn-text-announce",
            "button:has-text('Obter link')",
        ])
        if not btn:
            return {"success": False, "affiliate_link": None, "error": "Botão gerar link não encontrado."}

        # Extrai o link gerado
        link = await extract_value(page, "#amzn-ss-text-shortlink-textarea")
        if not link:
            link = await extract_value(page, "textarea.amzn-ss-text-shortlink-textarea")

        if link:
            return {"success": True, "affiliate_link": link, "error": None}

        return {"success": False, "affiliate_link": None, "error": "Link não apareceu após gerar."}

    except Exception as e:
        return {"success": False, "affiliate_link": None, "error": str(e)}
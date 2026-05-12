from playwright.async_api import TimeoutError as PlaywrightTimeout

from modulos.playwright_func import (
    navigate,
    find_element,
    extract_value,
    human_delay,
    human_click_locator,
)


async def gerar_link_amazon(page, product_url: str) -> dict:

    try:
        await navigate(page, product_url)

        btn_gerar = await find_element(page, [
            "#amzn-ss-get-link-button",
            "button[title='Obter link']",
            "button:has-text('Obter link')",
        ])
        if not btn_gerar:
            return {"success": False, "affiliate_link": None, "error": "Botão Gerar não encontrado."}

        await human_click_locator(btn_gerar)
        await human_delay(1500, 3000)

        btn = await find_element(page, [
            "#amzn-ss-get-link-btn-text-announce",
            "button:has-text('Obter link')",
        ])
        if not btn:
            return {"success": False, "affiliate_link": None, "error": "Botão gerar link não encontrado."}

        # Aguarda o botão sair do estado disabled antes de clicar
        try:
            await btn.wait_for(state="enabled", timeout=15000)
        except PlaywrightTimeout:
            return {"success": False, "affiliate_link": None, "error": "Botão 'Obter link' não habilitou após 15s."}

        await human_click_locator(btn)
        await human_delay(1500, 3000)

        # Extrai o link gerado
        link = await extract_value(page, "#amzn-ss-text-shortlink-textarea")
        if not link:
            link = await extract_value(page, "textarea.amzn-ss-text-shortlink-textarea")

        if link:
            return {"success": True, "affiliate_link": link, "error": None}

        return {"success": False, "affiliate_link": None, "error": "Link não apareceu após gerar."}

    except Exception as e:
        return {"success": False, "affiliate_link": None, "error": str(e)}
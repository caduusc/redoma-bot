import asyncio

from modulos.playwright_func import (
    navigate,
    find_element,
    extract_value,
    human_delay,
    human_click_locator,
)

TEXTAREA_SELECTORS = [
    "#amzn-ss-text-shortlink-textarea",
    "textarea.amzn-ss-text-shortlink-textarea",
]


async def gerar_link_amazon(page, product_url: str) -> dict:

    try:
        await navigate(page, product_url)

        # O SiteStripe já carrega o link na textarea na maioria dos casos —
        # tenta extrair direto sem clicar em nada
        await human_delay(1500, 2500)

        link = await extract_value(page, TEXTAREA_SELECTORS[0])
        if not link:
            link = await extract_value(page, TEXTAREA_SELECTORS[1])

        if link:
            return {"success": True, "affiliate_link": link, "error": None}

        # Link não estava pronto — clica em "Obter link" e aguarda aparecer
        btn = await find_element(page, [
            "#amzn-ss-get-link-btn-text-announce",
            "#amzn-ss-get-link-button",
            "button[title='Obter link']",
            "button:has-text('Obter link')",
        ])
        if not btn:
            return {"success": False, "affiliate_link": None, "error": "Botão 'Obter link' não encontrado e textarea vazia."}

        # Aguarda o botão habilitar (até 15s)
        for _ in range(30):
            is_disabled = await btn.evaluate("el => el.disabled")
            if not is_disabled:
                break
            await asyncio.sleep(0.5)
        else:
            return {"success": False, "affiliate_link": None, "error": "Botão 'Obter link' não habilitou após 15s."}

        await human_click_locator(btn)
        await human_delay(1500, 3000)

        link = await extract_value(page, TEXTAREA_SELECTORS[0])
        if not link:
            link = await extract_value(page, TEXTAREA_SELECTORS[1])

        if link:
            return {"success": True, "affiliate_link": link, "error": None}

        return {"success": False, "affiliate_link": None, "error": "Link não apareceu após gerar."}

    except Exception as e:
        return {"success": False, "affiliate_link": None, "error": str(e)}
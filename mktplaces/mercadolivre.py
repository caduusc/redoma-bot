import random

from modulos.playwright_func import (
    navigate,
    find_element,
    extract_value,
    human_delay,
    human_click_locator,
)

MELI_AFFILIATE_URL = "https://www.mercadolivre.com.br/afiliados/linkbuilder#hub"


async def gerar_link_mercadolivre(page, product_url: str) -> dict:

    try:
        await navigate(page, MELI_AFFILIATE_URL)

        # Cola a URL do produto
        input_el = await find_element(page, [
            "#url-0",
            "textarea[placeholder*='mercadolivre']",
            "textarea[data-andes-textfield-input='true']",
        ])
        if not input_el:
            return {"success": False, "affiliate_link": None, "error": "Campo de input não encontrado."}

        await input_el.click()
        await human_delay(100, 200)
        await page.keyboard.press("Control+a")
        await page.keyboard.press("Backspace")
        await human_delay(150, 300)

        for char in product_url:
            await input_el.type(char, delay=random.randint(25, 50))

        # Clica em gerar
        btn = await find_element(page, [
            "button.links-form__button",
            "button:has-text('Gerar')",
            "button[data-andes-button-hierarchy='loud']",
        ])
        if not btn:
            return {"success": False, "affiliate_link": None, "error": "Botão gerar não encontrado."}

        await human_click_locator(btn)
        await human_delay(2000, 4000)

        # Extrai o link gerado
        link = await extract_value(page, "textarea[id*='copyLink']")
        if not link:
            link = await extract_value(page, "textarea[aria-label*='Copie o link']")

        if link:
            return {"success": True, "affiliate_link": link, "error": None}

        return {"success": False, "affiliate_link": None, "error": "Link não apareceu após gerar."}

    except Exception as e:
        return {"success": False, "affiliate_link": None, "error": str(e)}
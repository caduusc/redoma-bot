"""
Redoma — Funções de navegação Playwright (Stealth).

Módulo utilitário com funções reutilizáveis pra automação
de browser com foco em anti-detecção.

Usa o Chrome real instalado na máquina com seu perfil pessoal,
mantendo sessões logadas nas plataformas.

Tudo async. Tudo humanizado. Nenhuma plataforma vai saber
que não é gente de verdade.

Uso:
    from playwright_func import (
        BrowserSession,
        human_type,
        human_fill,
        human_click,
        human_delay,
        find_element,
        navigate,
        extract_text,
        extract_value,
    )

    session = BrowserSession()
    await session.start()            # abre Chrome, fica em standby
    page = session.get_page()        # pega a page quando tiver trabalho
    await navigate(page, url)        # navega
    await session.stop()             # encerra
"""

import asyncio
import os
import platform
import random
import logging

from playwright.async_api import (
    async_playwright,
    BrowserContext,
    Page,
    Playwright,
    Locator,
    TimeoutError as PlaywrightTimeout,
)

logger = logging.getLogger("redoma.playwright")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Stealth — Script injetado em toda página
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

STEALTH_JS = """
() => {
    // navigator.webdriver = undefined (Chrome real não tem)
    Object.defineProperty(navigator, 'webdriver', { get: () => undefined });

    // Plugins reais (headless tem 0, Chrome normal tem 3+)
    Object.defineProperty(navigator, 'plugins', {
        get: () => [
            { name: 'Chrome PDF Plugin', filename: 'internal-pdf-viewer' },
            { name: 'Chrome PDF Viewer', filename: 'mhjfbmdgcfjbbpaeojofohoefgiehjai' },
            { name: 'Native Client', filename: 'internal-nacl-plugin' },
        ],
    });

    // Languages pt-BR (coerente com locale/timezone)
    Object.defineProperty(navigator, 'languages', {
        get: () => ['pt-BR', 'pt', 'en-US', 'en'],
    });

    // window.chrome (sites checam isso)
    if (!window.chrome) {
        window.chrome = { runtime: {}, loadTimes: () => {}, csi: () => {} };
    }

    // Permissions API — bloqueia detecção via notification query
    const origQuery = window.navigator.permissions.query;
    window.navigator.permissions.query = (params) =>
        params.name === 'notifications'
            ? Promise.resolve({ state: Notification.permission })
            : origQuery(params);

    // WebGL vendor/renderer (fingerprint mais comum)
    const getParam = WebGLRenderingContext.prototype.getParameter;
    WebGLRenderingContext.prototype.getParameter = function (p) {
        if (p === 37445) return 'Intel Inc.';
        if (p === 37446) return 'Intel Iris OpenGL Engine';
        return getParam.call(this, p);
    };

    // Esconde automação no prototype do navigator
    const descriptor = Object.getOwnPropertyDescriptor(Navigator.prototype, 'webdriver');
    if (descriptor) {
        Object.defineProperty(Navigator.prototype, 'webdriver', {
            get: () => undefined,
        });
    }

    // Fake connection info (headless pode não ter)
    if (!navigator.connection) {
        Object.defineProperty(navigator, 'connection', {
            get: () => ({
                effectiveType: '4g',
                rtt: 50,
                downlink: 10,
                saveData: false,
            }),
        });
    }

    // DeviceMemory (headless costuma retornar 0)
    Object.defineProperty(navigator, 'deviceMemory', { get: () => 8 });

    // HardwareConcurrency realista
    Object.defineProperty(navigator, 'hardwareConcurrency', { get: () => 8 });
}
"""


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Detecção do perfil do Chrome instalado
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def get_chrome_profile_path(profile: str = "Default") -> str:
    """
    Retorna o caminho do User Data Dir do Chrome instalado.

    Detecta automaticamente por SO:
      - Windows: %LOCALAPPDATA%/Google/Chrome/User Data
      - macOS:   ~/Library/Application Support/Google/Chrome
      - Linux:   ~/.config/google-chrome

    O argumento `profile` é o nome da pasta do perfil
    (Default, Profile 1, Profile 2, etc).
    """
    sistema = platform.system()

    if sistema == "Windows":
        base = os.path.join(os.environ.get("LOCALAPPDATA", ""), "Google", "Chrome", "User Data")
    elif sistema == "Darwin":
        base = os.path.expanduser("~/Library/Application Support/Google/Chrome")
    else:
        base = os.path.expanduser("~/.config/google-chrome")

    if not os.path.exists(base):
        raise FileNotFoundError(
            f"Perfil do Chrome não encontrado em {base}. "
            f"Verifique se o Chrome está instalado."
        )

    return base


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Setup do browser (Chrome real, perfil pessoal)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def create_stealth_browser(
    cdp_url: str = "http://localhost:9222",
) -> tuple[Playwright, BrowserContext, Page]:

    pw = await async_playwright().start()

    # Conecta no Chrome que já está rodando
    browser = await pw.chromium.connect_over_cdp(cdp_url)

    ctx = browser.contexts[0]  # Pega o contexto existente (perfil logado)
    await ctx.add_init_script(STEALTH_JS)

    pages = ctx.pages
    page = pages[0] if pages else await ctx.new_page()

    logger.info("Conectado ao Chrome via CDP.")
    return pw, ctx, page


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Delays humanizados
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def human_delay(min_ms: int = 300, max_ms: int = 900) -> None:
    """Pausa aleatória entre ações. Simula hesitação humana."""
    ms = random.randint(min_ms, max_ms)
    await asyncio.sleep(ms / 1000)


async def human_long_pause() -> None:
    """Pausa longa (1.5–4s). Simula leitura de página ou distração."""
    await asyncio.sleep(random.uniform(1.5, 4.0))


async def human_short_pause() -> None:
    """Pausa curta (100–400ms). Simula transição entre ações."""
    await asyncio.sleep(random.randint(100, 400) / 1000)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Digitação humanizada
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def human_type(page: Page, selector: str, text: str) -> None:
    """
    Digita texto caractere por caractere com timing humano.

    - 35–130ms entre teclas (ritmo natural)
    - ~8% de chance de pausa longa por caractere (olhou pro teclado)
    - Click no campo antes de digitar
    """
    locator = page.locator(selector).first
    await locator.wait_for(state="visible", timeout=5000)
    await locator.click()
    await human_short_pause()

    for char in text:
        await locator.type(char, delay=0)

        key_delay = random.randint(35, 130)
        if random.random() < 0.08:
            key_delay += random.randint(200, 500)

        await asyncio.sleep(key_delay / 1000)


async def human_fill(page: Page, selector: str, text: str) -> None:
    """
    Limpa o campo e digita com timing humano.
    Faz Ctrl+A → Backspace antes de digitar (mais natural que .clear()).
    """
    locator = page.locator(selector).first
    await locator.wait_for(state="visible", timeout=5000)
    await locator.click()
    await human_short_pause()

    await page.keyboard.press("Control+a")
    await human_short_pause()
    await page.keyboard.press("Backspace")
    await human_delay(200, 500)

    for char in text:
        await locator.type(char, delay=0)

        key_delay = random.randint(35, 130)
        if random.random() < 0.08:
            key_delay += random.randint(200, 500)

        await asyncio.sleep(key_delay / 1000)

    await human_short_pause()


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Click humanizado
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def human_click(page: Page, selector: str, timeout: int = 5000) -> None:
    """
    Clica num elemento com comportamento humano:
    hover → pausa curta → click.
    """
    locator = page.locator(selector).first
    await locator.wait_for(state="visible", timeout=timeout)
    await locator.hover()
    await human_delay(80, 300)
    await locator.click()
    await human_short_pause()


async def human_click_locator(locator: Locator) -> None:
    """
    Mesma coisa que human_click, mas recebe um Locator direto.
    Útil quando você já encontrou o elemento via find_element.
    """
    await locator.hover()
    await human_delay(80, 300)
    await locator.click()
    await human_short_pause()


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Busca de elementos (com fallback de seletores)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def find_element(
    page: Page,
    selectors: list[str],
    timeout: int = 3000,
) -> Locator | None:
    """
    Tenta localizar um elemento visível usando uma lista de seletores.
    Retorna o primeiro que encontrar, ou None.

    Uso:
        btn = await find_element(page, [
            "button:has-text('Gerar link')",
            "button:has-text('Gerar')",
            "button[type='submit']",
        ])
        if btn:
            await human_click_locator(btn)
    """
    for selector in selectors:
        try:
            locator = page.locator(selector).first
            await locator.wait_for(state="visible", timeout=timeout)
            return locator
        except PlaywrightTimeout:
            continue

    return None


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Navegação
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def navigate(page: Page, url: str, wait_until: str = "domcontentloaded") -> None:
    """Navega pra URL e espera com pausa humana depois."""
    await page.goto(url, wait_until=wait_until)
    await human_delay(1500, 3500)


async def wait_for_url_contains(page: Page, fragment: str, timeout: int = 15000) -> bool:
    """Espera a URL conter um fragmento. Retorna True se encontrou."""
    try:
        await page.wait_for_url(f"**/*{fragment}*", timeout=timeout)
        return True
    except PlaywrightTimeout:
        return False


async def is_on_page(page: Page, *fragments: str) -> bool:
    """Checa se a URL atual contém algum dos fragmentos."""
    url = page.url.lower()
    return any(f.lower() in url for f in fragments)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Extração de dados
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def extract_text(page: Page, selector: str, timeout: int = 3000) -> str | None:
    """Extrai o texto visível de um elemento."""
    try:
        locator = page.locator(selector).first
        await locator.wait_for(state="visible", timeout=timeout)
        return (await locator.inner_text()).strip()
    except (PlaywrightTimeout, Exception):
        return None


async def extract_value(page: Page, selector: str, timeout: int = 3000) -> str | None:
    """Extrai o value de um input/textarea."""
    try:
        locator = page.locator(selector).first
        await locator.wait_for(state="visible", timeout=timeout)
        val = await locator.evaluate("el => el.value || el.innerText || el.textContent")
        return val.strip() if val else None
    except (PlaywrightTimeout, Exception):
        return None


async def extract_all_text(page: Page) -> str:
    """Extrai todo o texto visível do body. Útil pra fallback com regex."""
    try:
        return await page.locator("body").inner_text()
    except Exception:
        return ""


async def extract_clipboard(page: Page) -> str | None:
    """Lê o conteúdo do clipboard. Precisa da permission clipboard-read."""
    try:
        clip = await page.evaluate("navigator.clipboard.readText()")
        return clip.strip() if clip else None
    except Exception:
        return None


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Select / Dropdown
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def select_option(page: Page, selector: str, label: str) -> bool:
    """
    Seleciona opção num <select> ou dropdown customizado.
    Tenta <select> nativo primeiro, depois clica e procura o texto.
    """
    try:
        locator = page.locator(selector).first
        await locator.wait_for(state="visible", timeout=3000)

        tag = await locator.evaluate("el => el.tagName.toLowerCase()")

        if tag == "select":
            await locator.select_option(label=label)
        else:
            await human_click_locator(locator)
            await human_delay(200, 500)
            option = page.locator(f"text='{label}'").first
            await human_click_locator(option)

        await human_short_pause()
        return True

    except Exception:
        return False


async def select_meli_tag(page, tag: str):
    await human_click(page, "[data-andes-dropdown-value='true']")
    await human_delay(300, 600)
    await human_click(page, f"text='{tag}'")


async def select_amazon_trackid(page, tag: str):
    await human_click(page, "span.a-dropdown-prompt")
    await human_delay(300, 600)
    await human_click(page, f"a.a-dropdown-link:has-text('{tag}')")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Scroll humanizado
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def human_scroll(page: Page, direction: str = "down", intensity: int = 3) -> None:
    """
    Scroll com comportamento humano — vários steps pequenos com
    pausas entre eles, em vez de um salto único.

    direction: 'down' ou 'up'
    intensity: 1 (suave) a 5 (agressivo)
    """
    steps = random.randint(intensity, intensity + 3)
    for _ in range(steps):
        delta = random.randint(80, 250)
        if direction == "up":
            delta = -delta
        await page.mouse.wheel(0, delta)
        await asyncio.sleep(random.uniform(0.1, 0.35))

    await human_short_pause()


async def scroll_to_element(page: Page, selector: str) -> None:
    """Scrolla até um elemento ficar visível."""
    try:
        locator = page.locator(selector).first
        await locator.scroll_into_view_if_needed()
        await human_short_pause()
    except Exception:
        pass


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Debug
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def take_screenshot(page: Page, path: str = "debug_screenshot.png") -> str:
    """Tira screenshot da página. Retorna o caminho do arquivo."""
    await page.screenshot(path=path, full_page=False)
    logger.info(f"Screenshot salvo: {path}")
    return path


async def log_current_state(page: Page) -> None:
    """Loga URL e título atual — útil pra debug."""
    url = page.url
    title = await page.title()
    logger.info(f"URL: {url}")
    logger.info(f"Title: {title}")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Ciclo de vida — Standby / Trabalho / Shutdown
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class BrowserSession:
    """
    Gerencia o ciclo de vida do browser:

      1. start()    → abre o Chrome com perfil pessoal
      2. standby    → browser aberto, sem fazer nada
      3. get_page() → retorna a page quando precisar trabalhar
      4. stop()     → fecha tudo

    O browser abre UMA VEZ e fica em standby.
    Quando chega mensagem pra processar, pega a page e navega.
    Quando termina, volta pro standby (browser continua aberto).

    Uso:
        session = BrowserSession()
        await session.start()

        # Quando tiver trabalho:
        page = session.get_page()
        await navigate(page, "https://...")
        # ... scraping ...

        # Quando quiser encerrar de vez:
        await session.stop()
    """

    def __init__(self, user_data_dir: str | None = None, headless: bool = False):
        self._user_data_dir = user_data_dir
        self._headless = headless
        self._pw: Playwright | None = None
        self._ctx: BrowserContext | None = None
        self._page: Page | None = None
        self._running = False

    async def start(self) -> None:
        """Abre o Chrome e deixa em standby."""
        if self._running:
            logger.info("Browser já está rodando.")
            return

        self._pw, self._ctx, self._page = await create_stealth_browser()
        self._running = True
        logger.info("Browser em standby — aguardando trabalho.")

    def get_page(self) -> Page:
        """Retorna a page ativa. Levanta erro se o browser não estiver aberto."""
        if not self._running or not self._page:
            raise RuntimeError("Browser não está rodando. Chame start() primeiro.")
        return self._page

    @property
    def is_running(self) -> bool:
        return self._running

    async def ensure_alive(self) -> bool:
        """
        Verifica se o browser ainda está responsivo.
        Se caiu, tenta reabrir automaticamente.
        Retorna True se está vivo.
        """
        if not self._running or not self._page:
            await self.start()
            return self._running

        try:
            _ = self._page.url
            return True
        except Exception:
            logger.warning("Browser caiu. Reabrindo...")
            await self._cleanup()
            await self.start()
            return self._running

    async def stop(self) -> None:
        """Fecha o browser e libera recursos."""
        logger.info("Encerrando browser...")
        await self._cleanup()

    async def _cleanup(self) -> None:
        self._running = False
        if self._ctx:
            try:
                await self._ctx.close()
            except Exception:
                pass
            self._ctx = None
        if self._pw:
            try:
                await self._pw.stop()
            except Exception:
                pass
            self._pw = None
        self._page = None
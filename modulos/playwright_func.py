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
    await session.start()                            # abre Chrome, fica em standby
    page = await session.get_page_for("mercadolivre") # pega/cria aba do marketplace
    await navigate(page, url)                        # navega
    await session.stop()                             # encerra
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
) -> tuple[Playwright, BrowserContext]:

    pw = await async_playwright().start()
    browser = await pw.chromium.connect_over_cdp(cdp_url)
    ctx = browser.contexts[0]
    await ctx.add_init_script(STEALTH_JS)

    logger.info("Conectado ao Chrome via CDP.")
    return pw, ctx


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Delays humanizados
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def human_delay(min_ms: int = 300, max_ms: int = 900) -> None:
    ms = random.randint(min_ms, max_ms)
    await asyncio.sleep(ms / 1000)


async def human_long_pause() -> None:
    await asyncio.sleep(random.uniform(1.5, 4.0))


async def human_short_pause() -> None:
    await asyncio.sleep(random.randint(100, 400) / 1000)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Digitação humanizada
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def human_type(page: Page, selector: str, text: str) -> None:
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
    locator = page.locator(selector).first
    await locator.wait_for(state="visible", timeout=timeout)
    await locator.hover()
    await human_delay(80, 300)
    await locator.click()
    await human_short_pause()


async def human_click_locator(locator: Locator) -> None:
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
    await page.goto(url, wait_until=wait_until)
    await human_delay(1500, 3500)


async def wait_for_url_contains(page: Page, fragment: str, timeout: int = 15000) -> bool:
    try:
        await page.wait_for_url(f"**/*{fragment}*", timeout=timeout)
        return True
    except PlaywrightTimeout:
        return False


async def is_on_page(page: Page, *fragments: str) -> bool:
    url = page.url.lower()
    return any(f.lower() in url for f in fragments)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Extração de dados
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def extract_text(page: Page, selector: str, timeout: int = 3000) -> str | None:
    try:
        locator = page.locator(selector).first
        await locator.wait_for(state="visible", timeout=timeout)
        return (await locator.inner_text()).strip()
    except (PlaywrightTimeout, Exception):
        return None


async def extract_value(page: Page, selector: str, timeout: int = 3000) -> str | None:
    try:
        locator = page.locator(selector).first
        await locator.wait_for(state="visible", timeout=timeout)
        val = await locator.evaluate("el => el.value || el.innerText || el.textContent")
        return val.strip() if val else None
    except (PlaywrightTimeout, Exception):
        return None


async def extract_all_text(page: Page) -> str:
    try:
        return await page.locator("body").inner_text()
    except Exception:
        return ""


async def extract_clipboard(page: Page) -> str | None:
    try:
        clip = await page.evaluate("navigator.clipboard.readText()")
        return clip.strip() if clip else None
    except Exception:
        return None


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Select / Dropdown
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def select_option(page: Page, selector: str, label: str) -> bool:
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
    steps = random.randint(intensity, intensity + 3)
    for _ in range(steps):
        delta = random.randint(80, 250)
        if direction == "up":
            delta = -delta
        await page.mouse.wheel(0, delta)
        await asyncio.sleep(random.uniform(0.1, 0.35))
    await human_short_pause()


async def scroll_to_element(page: Page, selector: str) -> None:
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
    await page.screenshot(path=path, full_page=False)
    logger.info(f"Screenshot salvo: {path}")
    return path


async def log_current_state(page: Page) -> None:
    url = page.url
    title = await page.title()
    logger.info(f"URL: {url}")
    logger.info(f"Title: {title}")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Ciclo de vida — Uma aba por marketplace
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class BrowserSession:
    """
    Gerencia o ciclo de vida do browser com uma aba fixa por marketplace.

    Problema resolvido: antes havia uma única page compartilhada — se chegasse
    um link do ML e logo depois um da Shopee, o bot navegava por cima do ML
    e derrubava o processamento em andamento.

    Solução: cada marketplace tem sua própria aba (Page) e seu próprio Lock.
    - A aba é criada na primeira requisição e reutilizada nas seguintes.
    - O lock garante que duas requisições do mesmo marketplace não se sobreponham.
    - Marketplaces diferentes rodam em paralelo sem se atrapalhar.

    Uso:
        session = BrowserSession()
        await session.start()

        # No endpoint:
        async with session.get_lock_for("mercadolivre"):
            page = await session.get_page_for("mercadolivre")
            # ... gera o link ...

        await session.stop()
    """

    def __init__(self):
        self._pw: Playwright | None = None
        self._ctx: BrowserContext | None = None
        self._pages: dict[str, Page] = {}   # marketplace → aba dedicada
        self._locks: dict[str, asyncio.Lock] = {}  # marketplace → lock
        self._running = False

    async def start(self) -> None:
        """Conecta ao Chrome e deixa em standby."""
        if self._running:
            logger.info("Browser já está rodando.")
            return

        self._pw, self._ctx = await create_stealth_browser()
        self._running = True
        logger.info("Browser em standby — aguardando trabalho.")

    async def get_page_for(self, marketplace: str) -> Page:
        """
        Retorna a aba dedicada ao marketplace.
        Se ainda não existe ou foi fechada, abre uma nova.
        """
        if not self._running or not self._ctx:
            raise RuntimeError("Browser não está rodando. Chame start() primeiro.")

        page = self._pages.get(marketplace)

        if page is None or page.is_closed():
            logger.info(f"Abrindo aba para [{marketplace}]...")
            page = await self._ctx.new_page()
            self._pages[marketplace] = page
            logger.info(f"Aba [{marketplace}] pronta.")

        return page

    def get_lock_for(self, marketplace: str) -> asyncio.Lock:
        """
        Retorna o lock exclusivo do marketplace.
        Garante que apenas uma requisição por vez use cada aba.
        """
        if marketplace not in self._locks:
            self._locks[marketplace] = asyncio.Lock()
        return self._locks[marketplace]

    @property
    def is_running(self) -> bool:
        return self._running

    async def ensure_alive(self) -> bool:
        """
        Verifica se o browser ainda está responsivo.
        Se caiu, reabre e limpa as abas (serão recriadas sob demanda).
        """
        if not self._running or not self._ctx:
            await self.start()
            return self._running

        try:
            # Testa qualquer aba existente; se não houver, testa abrindo uma
            if self._pages:
                page = next(iter(self._pages.values()))
                _ = page.url
            return True
        except Exception:
            logger.warning("Browser caiu. Reabrindo...")
            await self._cleanup()
            await self.start()
            return self._running

    async def stop(self) -> None:
        """Fecha todas as abas e encerra o browser."""
        logger.info("Encerrando browser...")
        await self._cleanup()

    async def _cleanup(self) -> None:
        self._running = False
        self._pages.clear()

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
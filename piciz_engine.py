"""
Motor de automatización PICIZ.

Adaptado del script original del usuario para correr en modo
headless (sin ventana visible), usando credenciales fijas que
se leen de forma segura desde st.secrets (Streamlit) en vez de
ser escritas a mano por cada persona.

Este archivo NO se ejecuta solo: app.py lo importa y consume
el generador `ejecutar_piciz()`, que va entregando (yield)
eventos de progreso para poder mostrarlos en vivo en la interfaz.
"""

import re
import unicodedata

from playwright.sync_api import (
    sync_playwright,
    TimeoutError as PlaywrightTimeoutError,
)

URL_PICIZ = "https://piciz.grupozfb.com/PicizLogin/app/#/home"

ZONA_FRANCA = "Zona Franca PE Conjunto Parque Sur"
EMPRESA = "CLARIOS DEL PACIFICO S.A.S."


def sin_tildes(texto):
    texto = unicodedata.normalize("NFD", texto)
    return "".join(
        letra for letra in texto
        if unicodedata.category(letra) != "Mn"
    ).lower()


class ProcesoPiciz:
    """
    Encapsula el estado que antes vivía en el diccionario global
    `control` del script original, para que cada ejecución sea
    independiente (importante al correr dentro de un servidor
    que puede recibir varias solicitudes).
    """

    def __init__(self):
        self.numero = None
        self.confirmacion = False
        self.exito = False
        self.error = None

    def atender_aviso(self, dialogo):
        mensaje = dialogo.message
        texto = sin_tildes(mensaje)

        if "documentos proximos a vencer" in texto:
            dialogo.accept()
            return

        if "desea realmente tramitar el formulario" in texto:
            encontrado = re.search(r"No:\s*(\d+)", mensaje, re.IGNORECASE)
            numero_aviso = encontrado.group(1) if encontrado else None

            if numero_aviso != self.numero:
                self.error = (
                    f"El aviso indica {numero_aviso}; "
                    f"el FMM seleccionado es {self.numero}."
                )
                dialogo.dismiss()
                return

            self.confirmacion = True
            dialogo.accept()
            return

        if "el formulario ha sido tramitado" in texto:
            self.exito = True
            dialogo.accept()
            return

        self.error = f"Aviso inesperado: {mensaje}"
        dialogo.dismiss()


def _buscar_primer_fmm(pagina, numero_anterior=None):
    pagina.get_by_role("button", name="Buscar", exact=True).click()

    tabla = pagina.locator("table").filter(
        has=pagina.locator("th", has_text="Formulario")
    )

    for _ in range(15):
        fila = tabla.locator("tbody tr").first
        celdas = fila.locator("td")

        if celdas.count() >= 2:
            numero = celdas.nth(1).inner_text().strip()

            if re.fullmatch(r"991\d+", numero):
                if numero == numero_anterior:
                    raise RuntimeError(
                        f"El FMM {numero} sigue en la lista "
                        "después de tramitarlo."
                    )

                estado_fila = celdas.nth(5).inner_text().strip()
                if estado_fila != "DEFINITIVO":
                    raise RuntimeError(
                        f"El FMM {numero} muestra estado "
                        f"{estado_fila!r}."
                    )

                return numero, fila

        pagina.wait_for_timeout(1000)

    return None, None


def ejecutar_piciz(usuario, contrasena, headless=True):
    """
    Generador que ejecuta todo el flujo de PICIZ y va entregando
    eventos de progreso, por ejemplo:

        {"tipo": "log", "mensaje": "..."}
        {"tipo": "tramitado", "numero": "9910001", "total": 3}
        {"tipo": "error", "mensaje": "..."}
        {"tipo": "fin", "tramitados": [...]}

    NOTA IMPORTANTE (léela antes de desplegar):
    Los selectores del campo de contraseña y del botón de login
    ("Password" / "INGRESAR") son una suposición razonable basada
    en el patrón del campo "Username" del script original, pero
    NO fueron confirmados contra la página real, porque el script
    original esperaba a que la persona los llenara a mano. Es muy
    probable que haya que ajustar estas dos líneas la primera vez
    que se pruebe, inspeccionando el HTML real del login de PICIZ.
    """
    tramitados = []
    vistos = set()
    ultimo_numero = None

    with sync_playwright() as playwright:
        navegador = playwright.chromium.launch(headless=headless)
        pagina = navegador.new_page()

        proceso = ProcesoPiciz()
        pagina.on("dialog", proceso.atender_aviso)

        try:
            yield {"tipo": "log", "mensaje": "Abriendo PICIZ..."}
            pagina.goto(URL_PICIZ)

            pagina.locator("select").nth(0).select_option(label=ZONA_FRANCA)
            pagina.locator("select").nth(1).select_option(label=EMPRESA)
            pagina.get_by_placeholder("Username").fill(usuario)

            # --- Inicio de sección a verificar (ver nota arriba) ---
            pagina.get_by_placeholder("Password").fill(contrasena)
            pagina.get_by_role("button", name=re.compile("INGRESAR", re.I)).click()
            # --- Fin de sección a verificar ---

            yield {"tipo": "log", "mensaje": "Iniciando sesión..."}
            pagina.wait_for_url("**/PicizWeb/app/**", timeout=120000)

            regresar = pagina.get_by_text("Regresar", exact=True)
            try:
                regresar.wait_for(state="visible", timeout=10000)
                regresar.click()
            except PlaywrightTimeoutError:
                pass

            pagina.get_by_text("MODULO MOVIMIENTOS", exact=True).click()
            pagina.get_by_text("FORMULARIOS", exact=True).click()

            estado = pagina.locator("select").filter(
                has=pagina.locator("option", has_text="DEFINITIVO")
            )
            estado.select_option(label="DEFINITIVO")

            yield {"tipo": "log", "mensaje": "Buscando FMM en estado DEFINITIVO..."}

            while True:
                numero, fila = _buscar_primer_fmm(pagina, ultimo_numero)

                if numero is None:
                    numero, fila = _buscar_primer_fmm(pagina, ultimo_numero)

                if numero is None:
                    tabla = pagina.locator("table").filter(
                        has=pagina.locator("th", has_text="Formulario")
                    )
                    texto_tabla = sin_tildes(tabla.inner_text())

                    if "ningun dato disponible" not in texto_tabla:
                        raise RuntimeError(
                            "La tabla no cargó registros ni mostró "
                            "el mensaje de lista vacía."
                        )

                    yield {"tipo": "log", "mensaje": "No quedan FMM pendientes."}
                    break

                if numero in vistos:
                    raise RuntimeError(
                        f"El FMM {numero} volvió a aparecer. "
                        "Se detuvo para evitar repetirlo."
                    )
                vistos.add(numero)

                proceso.numero = numero
                proceso.confirmacion = False
                proceso.exito = False
                proceso.error = None

                yield {"tipo": "log", "mensaje": f"Abriendo FMM {numero}..."}
                fila.locator("td").first.locator("a, button").first.click()

                pagina.wait_for_url("**/formularioFlow/**")
                pagina.get_by_text(
                    "FORMULARIO EN DEFINITIVO", exact=True
                ).wait_for(state="visible")

                tabla_detalle = pagina.locator("table").filter(
                    has=pagina.locator("th", has_text="Formulario")
                ).first
                texto_detalle = tabla_detalle.locator("tbody tr").first.inner_text()

                if numero not in texto_detalle:
                    raise RuntimeError(f"El detalle no corresponde al FMM {numero}.")

                tramitar = pagina.locator(
                    '[title*="Tramitar Formulario"], '
                    '[data-original-title*="Tramitar Formulario"]'
                ).first

                if tramitar.count() == 0:
                    raise RuntimeError("No se encontró el botón Tramitar Formulario.")

                yield {"tipo": "log", "mensaje": f"Tramitando FMM {numero}..."}
                tramitar.click()

                pagina.wait_for_url("**/formulario/**", timeout=30000)

                if proceso.error:
                    raise RuntimeError(proceso.error)

                if not proceso.confirmacion or not proceso.exito:
                    raise RuntimeError(
                        f"No se confirmaron los dos avisos del FMM {numero}."
                    )

                tramitados.append(numero)
                ultimo_numero = numero

                yield {
                    "tipo": "tramitado",
                    "numero": numero,
                    "total": len(tramitados),
                }

            yield {"tipo": "fin", "tramitados": tramitados}

        except Exception as error:
            yield {
                "tipo": "error",
                "mensaje": str(error),
                "tramitados": tramitados,
            }

        finally:
            navegador.close()

import os
import subprocess
import threading
import time

import streamlit as st

# Streamlit Cloud instala las dependencias de requirements.txt,
# pero NO descarga el navegador Chromium que Playwright necesita.
# Este bloque lo descarga una sola vez, la primera vez que arranca
# el contenedor (se apoya en un archivo "bandera" para no repetirlo
# en cada recarga de página).
_FLAG = "/tmp/.playwright_chromium_instalado"
if not os.path.exists(_FLAG):
    with st.spinner("Preparando el navegador (solo la primera vez)..."):
        subprocess.run(
            ["playwright", "install", "chromium"],
            check=False,
        )
        open(_FLAG, "w").close()

from piciz_engine import ejecutar_piciz

# -----------------------------
# CONFIGURACIÓN DE LA PÁGINA
# -----------------------------
st.set_page_config(
    page_title="Descarga FMM 450 — PICIZ",
    page_icon="📄",
    layout="wide"
)

# Candado global: evita que dos personas disparen el navegador
# automatizado al mismo tiempo (el servidor gratuito tiene poca
# memoria y no aguantaría dos Chromium headless a la vez).
# Al ser una variable de módulo, se comparte entre todas las
# sesiones que atiende este mismo proceso de Streamlit.
_LOCK = threading.Lock()

# -----------------------------
# ENCABEZADO
# -----------------------------
st.title("📄 Descarga FMM 450 — PICIZ")
st.caption("CLARIOS DEL PACIFICO S.A.S.")

st.divider()

# -----------------------------
# CREDENCIALES
# -----------------------------
try:
    USUARIO = st.secrets["piciz"]["usuario"]
    CONTRASENA = st.secrets["piciz"]["contrasena"]
    credenciales_ok = True
except Exception:
    credenciales_ok = False

if not credenciales_ok:
    st.error(
        "No se encontraron las credenciales de PICIZ configuradas en "
        "st.secrets. Un administrador debe agregarlas en "
        "**Settings → Secrets** de Streamlit Cloud (ver README)."
    )
    st.stop()

# -----------------------------
# ESTADO
# -----------------------------
if "corriendo" not in st.session_state:
    st.session_state.corriendo = False
if "logs" not in st.session_state:
    st.session_state.logs = []
if "tramitados" not in st.session_state:
    st.session_state.tramitados = []
if "errores" not in st.session_state:
    st.session_state.errores = 0

# -----------------------------
# BOTÓN DE ACCIÓN
# -----------------------------
st.subheader("Ejecutar")

col_boton, _ = st.columns([1, 3])
with col_boton:
    iniciar = st.button(
        "🔎 Buscar y tramitar FMM",
        use_container_width=True,
        disabled=st.session_state.corriendo,
    )

st.divider()

# -----------------------------
# PROGRESO
# -----------------------------
st.subheader("Progreso de ejecución")

col1, col2, col3 = st.columns(3)
metric_tramitados = col1.empty()
metric_errores = col2.empty()
metric_tiempo = col3.empty()

barra = st.progress(0)
caja_log = st.empty()


def pintar_estado(tiempo_transcurrido=0.0):
    metric_tramitados.metric("Tramitados", len(st.session_state.tramitados))
    metric_errores.metric("Errores", st.session_state.errores)
    metric_tiempo.metric("Tiempo", f"{tiempo_transcurrido:.1f} s")
    caja_log.code("\n".join(st.session_state.logs[-15:]) or "Sin actividad todavía.")


pintar_estado()

st.divider()
st.subheader("Resultados")
tabla_resultados = st.empty()


def pintar_resultados():
    if st.session_state.tramitados:
        tabla_resultados.table(
            {"FMM tramitados": st.session_state.tramitados}
        )
    else:
        tabla_resultados.info("Todavía no se ha tramitado ningún FMM.")


pintar_resultados()

# -----------------------------
# EJECUCIÓN
# -----------------------------
if iniciar:
    if not _LOCK.acquire(blocking=False):
        st.warning(
            "Ya hay un proceso en curso (posiblemente de otra persona). "
            "Intenta de nuevo en unos minutos."
        )
    else:
        try:
            st.session_state.corriendo = True
            st.session_state.logs = []
            st.session_state.tramitados = []
            st.session_state.errores = 0

            inicio = time.time()

            for evento in ejecutar_piciz(USUARIO, CONTRASENA, headless=True):
                tipo = evento.get("tipo")

                if tipo == "log":
                    st.session_state.logs.append(evento["mensaje"])

                elif tipo == "tramitado":
                    st.session_state.tramitados.append(evento["numero"])
                    st.session_state.logs.append(
                        f"✅ FMM {evento['numero']} tramitado."
                    )
                    pintar_resultados()

                elif tipo == "error":
                    st.session_state.errores += 1
                    st.session_state.logs.append(f"❌ {evento['mensaje']}")

                elif tipo == "fin":
                    st.session_state.logs.append("Proceso terminado.")

                pintar_estado(time.time() - inicio)

        finally:
            st.session_state.corriendo = False
            _LOCK.release()
            st.rerun()

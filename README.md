# Descarga FMM 450 — PICIZ

App Streamlit que busca y tramita automáticamente los FMM en estado
DEFINITIVO de CLARIOS DEL PACIFICO S.A.S. en PICIZ.

## ⚠️ Antes de usarla en producción — verificar esto

El script original pedía que la persona escribiera la contraseña
a mano en una ventana de Edge visible. Para poder correr sin
intervención humana en un servidor (headless), tuve que **suponer**
cómo se llaman el campo de contraseña y el botón de login de PICIZ:

```python
pagina.get_by_placeholder("Password").fill(contrasena)
pagina.get_by_role("button", name=re.compile("INGRESAR", re.I)).click()
```

en `piciz_engine.py`. Esto **no fue verificado contra la página real**
y es muy probable que haya que ajustarlo la primera vez que se
pruebe (por ejemplo si el campo no tiene placeholder "Password", o
el botón no se llama exactamente "INGRESAR"). Si falla ahí, avísame
el HTML real de esa pantalla y lo corrijo.

## Pasos para publicarla con link

### 1. Sube esta carpeta a un repositorio de GitHub
Sube todo el contenido de esta carpeta **excepto**
`.streamlit/secrets.toml.example` tal cual (ese es solo un ejemplo,
no debe contener la contraseña real ni subirse con datos reales).

### 2. Crea la app en Streamlit Community Cloud
1. Entra a https://share.streamlit.io con tu cuenta.
2. "New app" → selecciona el repositorio y la rama.
3. Archivo principal: `app.py`.

### 3. Configura la contraseña de forma segura (Secrets)
**No pongas la contraseña en el código ni en GitHub.** En vez de eso:
1. Dentro de tu app en Streamlit Cloud, ve a **Settings → Secrets**.
2. Pega esto (con la contraseña real):

```toml
[piciz]
usuario = "WILDUS003"
contrasena = "LA_CONTRASENA_REAL_AQUI"
```

3. Guarda. La app la lee automáticamente vía `st.secrets`; nadie que
   use la app la ve ni la escribe.

### 4. Primer arranque
La primera vez que la app arranca, descarga el navegador Chromium
(puede tardar 1–2 minutos). Las siguientes veces es inmediato.

## Limitaciones conocidas del plan gratuito

- **Memoria limitada (~1 GB):** un navegador Chromium headless
  consume bastante. La app ya bloquea que dos personas corran el
  proceso al mismo tiempo, pero ejecuciones muy largas o con muchos
  FMM pendientes podrían agotar memoria o tiempo de espera.
- **La app "duerme"** tras un rato de inactividad; el primer acceso
  del día puede tardar unos segundos extra en despertar.
- Si esto se vuelve una herramienta crítica de uso diario, lo ideal
  a mediano plazo es moverla a un servidor propio con más recursos.

## Estructura del proyecto

```
app.py                          # Interfaz Streamlit
piciz_engine.py                 # Lógica de automatización (Playwright)
requirements.txt                # Dependencias Python
packages.txt                    # Librerías de sistema para Chromium
.streamlit/secrets.toml.example # Plantilla de credenciales (no subir con datos reales)
```

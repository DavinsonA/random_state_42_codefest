# A.R.P.I.A. — Despliegue en Coolify: requisitos y decisiones por tomar

> **Documento de discusión.** Recoge lo que exige la Especificación Técnica de ADL para
> desplegar, cómo está hoy el `Dockerfile`, y las decisiones que el equipo aún no ha
> tomado. Cuando se decida algo, se anota en §6 (*Registro de decisiones*) y se actualiza
> el resto del documento. La implementación general está en [`API.md`](API.md) y lo que
> exige ADL en [`../RETO.md`](../RETO.md).
>
> Estado: **análisis hecho, nada modificado todavía** (ni `Dockerfile` ni `compose`).
> Fecha de corte: `main` @ `1c1466e`, 19 de septiembre de 2026.

---

## 1. Qué exige la Especificación de ADL (Anexo A, §2.1, §2.2, §3.1)

| Requisito | Detalle |
|---|---|
| **Tipo de recurso** | *Applications → Private Git Repository (with Deploy Key)*. Llave SSH ED25519 generada en Coolify (*Root Team → Keys & Tokens → Private Keys*) y su llave pública registrada en GitHub |
| **Repositorio** | **Privado en todo momento.** ADL y los evaluadores entran como colaboradores invitados |
| **Build pack** | **`Dockerfile`** (no menciona Docker Compose en ninguna parte). Coolify construye la imagen desde el `Dockerfile` del repo |
| **Imagen** | *Autosuficiente*: librerías, **modelos** y credenciales declarados en el repo o inyectados como variables de entorno |
| **Puertos** | "El contenedor debe exponer **un único puerto o endpoint HTTP**". Reto 1: un endpoint (`POST /chat`). Reto 2: un puerto que sirva la interfaz web |
| **Dominios** | Se agregan en *Domains → + Add Domain* **de cada recurso**: `agent.`, `frontagent.` y `dashboard.<equipo>.codefest2026.augusta.avaldigitallabs.com`. El de `coolify.` lo entrega ADL y no se toca |
| **Cada dominio** | El campo **Port** debe coincidir con el puerto interno del contenedor, y *www redirect* en **No redirect** |
| **Endpoint de la card** | El `endpoint` de la agent card debe ser el subdominio `agent.` |
| **Variables de entorno** | En el panel (*Environment Variables → + Add*), marcadas *Build*, *Runtime* o ambas; nunca en el código ni en la imagen. Permite rotar credenciales sin reconstruir |
| **Healthcheck** | Recomendado ("simple, que verifique que el contenedor está activo") |
| **Ventana Reto 1** | Endpoint accesible de **08:00 a 12:30** del sábado 19. **No se redespliega en ese lapso** |
| **Reto 2** | Se entrega a las **12:30**; el dashboard debe seguir accesible hasta que los expertos terminen |

Lo que **no** dice el PDF: que sean varios contenedores, que se use Compose, ni que cada
subdominio deba ser un servicio distinto. Tampoco dice cómo llevar datos grandes (el índice)
al contenedor.

---

## 2. Estado actual (lo que hay en `arpia/`)

- **Un solo servicio, un solo puerto (8000).** Uvicorn con `--workers 1`; `routing.py` decide
  por `Host` qué HTML servir (`dashboard.*` → tablero, cualquier otro → chat). Los tres
  dominios apuntarían al mismo contenedor.
- `Dockerfile`: `python:3.11-slim`, instala `requirements.txt`, `COPY . .`, `EXPOSE 8000`,
  `HEALTHCHECK` contra `/health`. La frontera de qué entra la define `.dockerignore`.
- `docker-compose.yml`: **solo para desarrollo local.** Coolify con build pack `Dockerfile` lo
  ignora. Sus volúmenes (`hf-cache`, `estado`, `./data`) hay que recrearlos en la pestaña
  *Storages* de Coolify.
- El chat y el tablero son **HTML estático** servido por la API. Streamlit (8501) ya no se
  despliega. (`static/` aún no existe: `routing.py` muestra un aviso legible mientras tanto.)

---

## 3. Problemas encontrados (por verificar y arreglar)

Ordenados por gravedad. **Ninguno está corregido todavía.**

| # | Problema | Por qué importa | Arreglo propuesto |
|---|---|---|---|
| 1 | **El índice no llega al contenedor.** `.dockerignore` excluye `data/`, `*.faiss` y `*.jsonl`; y no puede ir en git (`index.faiss` pesa 1,3 GB y GitHub limita a 100 MB por archivo) | Sin índice, `/chat` cae siempre a `error_grafo` | *Storage* persistente en `/app/data` + algo que lo llene (ver decisión D2) |
| 2 | **La ruta del índice no coincide.** El código busca `data/encoder_bge_m3`; la carpeta local es `data/base_vectorial/encoder_bge_m3` | Aunque se monte el volumen, no lo encuentra | Fijar `VECTOR_INDEX_PATH` explícito y montar el volumen para que la ruta exista |
| 3 | **Sin encoder no hay recuperación.** Los pesos de `bge-m3` (~2,2 GB) se descargan de Hugging Face al arrancar | Si el servidor de ADL no llega a `huggingface.co`, fallan la búsqueda vectorial **y** el caché semántico. El PDF pide imagen autosuficiente en *modelos* | Incluir el modelo en la imagen al construirla (decisión D3) |
| 4 | **`requirements.txt` instala CUDA que no se usa.** Trae 15 paquetes `nvidia-*` y `triton`, porque `uv export` resuelve el `torch` de GPU en Linux. El encoder corre con `device="cpu"` | Builds lentos y pesados, más disco, riesgo de *timeout* al construir. *Tamaño exacto: **no medido** (estimado en varios GB)* | Instalar `torch` desde el índice CPU de PyTorch y excluir `nvidia-*`/`triton`. **Medir construyendo la imagen localmente** |
| 5 | **`/health` carga el índice en su primera llamada** (1,3 GB) y puede exceder los 5 s del healthcheck | Un healthcheck fallido durante el arranque puede marcar el despliegue como fallido | Precalentar el índice en `lifespan`, junto al encoder |
| 6 | **Docs contradictorios.** `deploy-test/README.md` dice que el repo será *público*; el skill `coolify-deploy` habla de Streamlit en 8501 | El PDF exige repo **privado**; con deploy key, Coolify a veces no persiste el *Base Directory* y hay que volver a fijarlo en *Build settings* | Corregirlos y borrar `deploy-test/` antes de la entrega (su propio README lo pide) |
| 7 | **Auto Deploy.** Por defecto Coolify redespliega en cada `push` a la rama configurada | Un `push` entre 08:00 y 12:30 tumba el endpoint que se está evaluando | Apagar *Auto Deploy* desde las 08:00, o desplegar desde una rama `release` que solo se toque al congelar |

**Dato medido por el equipo** (comentario del `Dockerfile`): índice + encoder ≈ **3,8 GB de
RAM por proceso**. Con 8 GB de contenedor, dos workers rozan el límite.

---

## 4. Configuración propuesta del recurso en Coolify (borrador)

| Campo | Valor |
|---|---|
| Source | Private Git Repository (with Deploy Key) |
| Repository / Branch | URL del repo privado / `main` (o `release`, ver #7) |
| Build Pack | `Dockerfile` |
| Base Directory | `/arpia` (verificar que se **guardó**, ver #6) |
| Ports Exposes | `8000` |
| Domains | `agent.random-state-42…`, `frontagent.…`, `dashboard.…` — cada uno con **Port `8000`** y *www redirect: No redirect* |
| Env vars (*Runtime*) | `ARPIA_MODE=live`, `LLM_BASE_URL`, `LLM_API_KEY`, `VECTOR_INDEX_PATH`, `CHECKPOINT_PATH`, `HF_HOME`; opcional `MODEL_ALIASES` |
| Storages | `/app/data` (índice, solo lectura), `/app/state` (SQLite de memoria), `/app/.cache/huggingface` (si el encoder no va en la imagen) |
| Health check | El del `Dockerfile` (`GET /health`) |
| Auto Deploy | **Apagado desde las 08:00** |

> El nombre de equipo `random-state-42` sale de la agent card. **Confirmarlo con el dominio
> que asigne ADL** el día del evento.

---

## 5. Decisiones por tomar

Estado de todas: **⏳ pendiente**. La columna *Recomendación* es la de quien redactó este
documento, no una decisión del equipo.

### D1 — ¿Un contenedor o varios?

| Opción | A favor | En contra |
|---|---|---|
| **A. Un recurso con los 3 dominios** (actual) | Menos piezas que puedan caerse; mitad de RAM (≈3,8 GB, no 7,6 GB) | Redesplegar el tablero reinicia también `/chat` |
| B. Dos recursos: `agent`+`frontagent` y `dashboard` | Se despliegan por separado | Doble RAM y doble configuración |
| C. Tres recursos | Aislamiento total | Triple RAM, sin beneficio real |

- **Recomendación: A.** El "único puerto" del PDF es por contenedor, y nada prohíbe varios
  dominios sobre un recurso. El riesgo del contenedor único (redesplegar `/chat` al tocar el
  tablero) se maneja con disciplina: congelar a las 08:00 y apagar *Auto Deploy* (#7).
- **Dato que falta:** cuánta **RAM y disco** tiene el servidor de Coolify (panel → *Servers*).
  Si no alcanza para ≈4 GB + margen, la decisión cambia.

### D2 — ¿Cómo llega el índice (1,6 GB) al servidor?

`data/base_vectorial/encoder_bge_m3/` = `index.faiss` (1,3 GB) + `metadata.jsonl` (344 MB) +
`manifest.json`.

| Opción | A favor | En contra |
|---|---|---|
| **A. Script de arranque que lo descarga de una URL si falta** (`DATA_URL` como variable) | Reproducible; sobrevive si se pierde el volumen; no requiere acceso al servidor | Hay que alojar el archivo en algún lado; el primer arranque tarda |
| B. Subirlo a mano al volumen (terminal de Coolify / `scp`) | Sin infraestructura extra | Manual, frágil, no reproducible; requiere acceso al host |
| C. Meterlo en la imagen | Autosuficiente | No cabe en git; la imagen crece 1,6 GB; el *build* necesitaría los archivos |

- **Recomendación: A.**
- **Falta decidir dónde se aloja:** Google Drive, Hugging Face (repo privado) u otro.

### D3 — ¿Dónde vive el encoder `bge-m3` (~2,2 GB)?

| Opción | A favor | En contra |
|---|---|---|
| **A. Dentro de la imagen** (descarga en el *build*) | Sin dependencia de internet en ejecución; cumple "imagen autosuficiente" | Imagen +2,2 GB |
| B. Volumen persistente (`HF_HOME`), se baja al primer arranque | Imagen más liviana | Si el servidor no llega a Hugging Face, **no hay recuperación** |

- **Recomendación: A.** El *build* ya necesita internet para `pip`; si llega a PyPI, es muy
  probable que llegue a Hugging Face, pero **no está verificado**.

### D4 — ¿`torch` de CPU y sin paquetes CUDA?

- **Recomendación: sí.** Ahorra tiempo y disco de build. Pendiente **medir** el tamaño real de
  la imagen antes y después (hay Docker 29.7 instalado en la máquina de desarrollo, así que
  se puede hacer sin gastar presupuesto de tokens).

### D5 — ¿Rama de despliegue?

| Opción | Nota |
|---|---|
| `main` con *Auto Deploy* apagado a las 08:00 | Simple; depende de acordarse |
| Rama `release` que solo se actualiza al congelar | Más seguro: un `push` accidental a `main` no toca producción |

- **Recomendación: `release`**, dado que el costo de un redespliegue accidental en la ventana
  de evaluación es perder el Reto 1.

### D6 — ¿Qué se hace con `docker-compose.yml`?

- **Recomendación:** conservarlo **solo** para reproducir el build en local, con un
  comentario que diga que Coolify no lo usa y que sus volúmenes se recrean en *Storages*.

### D7 — Hora de congelamiento

- El PDF fija la ventana de 08:00 a 12:30. **Propuesta:** congelar el código y desplegar
  antes de las 08:00, con margen para verificar `/health`, `/agent-card` y una pregunta real.
  Hay que fijar la hora exacta y quién ejecuta el despliegue final.

---

## 6. Registro de decisiones

| ID | Decisión | Fecha | Quién decidió | Notas |
|---|---|---|---|---|
| D1 | | | | |
| D2 | | | | |
| D3 | | | | |
| D4 | | | | |
| D5 | | | | |
| D6 | | | | |
| D7 | | | | |

---

## 7. Lista de verificación antes de las 08:00 del sábado

- [ ] Repo **privado**; ADL y evaluadores invitados como colaboradores.
- [ ] Llave de despliegue creada en Coolify y registrada en GitHub.
- [ ] Recurso creado con *Base Directory* `/arpia` **guardado** (revisar *Build settings*).
- [ ] Los 3 dominios con Port `8000` y *No redirect*.
- [ ] Variables como *Runtime*, con `ARPIA_MODE=live`.
- [ ] *Storages* creados y el índice cargado; `GET /health` con `index_loaded: true`.
- [ ] `GET /agent-card` devuelve la ficha y su `endpoint` es el subdominio `agent.`.
- [ ] Una pregunta real por `POST /chat` con `mode: "live"` y `estado: "ok"`.
- [ ] *Auto Deploy* apagado. Nadie hace `push` a la rama desplegada hasta las 12:30.
- [ ] `deploy-test/` eliminado del repo.

## 8. Qué no se ha verificado

Para que nadie lo dé por sabido:

- RAM y disco del servidor de Coolify.
- Si ese servidor tiene salida a `huggingface.co` y a `download.pytorch.org`.
- El tamaño real de la imagen (con y sin CUDA).
- El nombre de equipo definitivo en los dominios.
- Cuánto tarda el primer arranque con el índice y el encoder reales.
- Que Coolify acepte los tres dominios sobre un mismo recurso con el mismo puerto (es lo
  esperable por la documentación de ADL, pero no se ha probado en su panel).

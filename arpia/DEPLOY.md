# A.R.P.I.A. — Despliegue en Coolify: requisitos y decisiones por tomar

> **Documento de discusión.** Recoge lo que exige la Especificación Técnica de ADL para
> desplegar, cómo está hoy el `Dockerfile`, y las decisiones que el equipo aún no ha
> tomado. Cuando se decida algo, se anota en §6 (*Registro de decisiones*) y se actualiza
> el resto del documento. La implementación general está en [`API.md`](API.md) y lo que
> exige ADL en [`../RETO.md`](../RETO.md).
>
> Estado: **análisis hecho, nada modificado todavía** (ni `Dockerfile` ni `compose`).
> Fecha de corte: `main` @ `c92029b`, 19 de septiembre de 2026.

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
- El chat y el tablero son **HTML estático** que sirve la propia API desde `src/ui/static/`; ese
  directorio entra a la imagen con `COPY . .`. Existen `chat.html` y `dashboard.html`, ninguno
  con referencias externas: Chart.js va vendorizado en `vendor/` y las fuentes se sirven
  localmente, así que la interfaz no depende de ningún CDN. No hay ninguna otra interfaz: el
  Streamlit que hubo (`src/ui/app.py`) se eliminó el 19 de septiembre.
- La API expone además los endpoints del tablero (`/api/components`, `/api/aggregate`,
  `/api/timeline`, `/api/geo`, `/api/evidence/{chunk_id}`, `/api/trace/{trace_id}`). Salen por el
  mismo puerto 8000 y por los tres dominios, incluido `agent.*`.

---

## 3. Problemas encontrados (por verificar y arreglar)

Ordenados por gravedad. **Ninguno está corregido todavía.**

| # | Problema | Por qué importa | Arreglo propuesto |
|---|---|---|---|
| 1 | **El índice no llega al contenedor.** `.dockerignore` excluye `data/`, `*.faiss` y `*.jsonl`; y no puede ir en git (`index.faiss` pesa 1,3 GB y GitHub limita a 100 MB por archivo) | Sin índice, `/chat` cae siempre a `error_grafo` | *Storage* persistente en `/app/data` + algo que lo llene (ver decisión D2) |
| 2 | **La ruta del índice no coincide.** El código busca `data/encoder_bge_m3`; la carpeta local es `data/base_vectorial/encoder_bge_m3` | Aunque se monte el volumen, no lo encuentra | Fijar `VECTOR_INDEX_PATH` explícito y montar el volumen para que la ruta exista |
| 3 | **Sin encoder no hay recuperación.** Los pesos de `bge-m3` (~2,2 GB) se descargan de Hugging Face al arrancar | Si el servidor de ADL no llega a `huggingface.co`, fallan la búsqueda vectorial **y** el caché semántico. El PDF pide imagen autosuficiente en *modelos* | Incluir el modelo en la imagen al construirla (decisión D3) |
| 4 | **`requirements.txt` instala CUDA que no se usa.** Trae 15 paquetes `nvidia-*` y `triton`, porque `uv export` resuelve el `torch` de GPU en Linux. El encoder corre con `device="cpu"` | Builds lentos y pesados, más disco, riesgo de *timeout* al construir. *Tamaño exacto: **no medido** (estimado en varios GB)* | Instalar `torch` desde el índice CPU de PyTorch y excluir `nvidia-*`/`triton`. **Medir construyendo la imagen localmente** |
| 5 | ✅ **Resuelto en `adea37f`.** El arranque precalienta índice, tabla y encoder, así que `/health` ya no carga 1,3 GB en su primera llamada | Antes podía exceder los 5 s del healthcheck y marcar como fallido un despliegue que solo estaba cargando | Queda verificar el tiempo de arranque **en el servidor de ADL** (§8) |
| 6 | ✅ **RESUELTO.** `deploy-test/` se borró y el skill `coolify-deploy` ya no habla de Streamlit en 8501 | El PDF exige repo **privado**; con deploy key, Coolify a veces no persiste el *Base Directory* y hay que volver a fijarlo en *Build settings* | Hecho. Lo del *Base Directory* sigue siendo una trampa del panel: verificarlo tras cada cambio de credenciales |
| 7 | **Auto Deploy.** Por defecto Coolify redespliega en cada `push` a la rama configurada | Un `push` entre 08:00 y 12:30 tumba el endpoint que se está evaluando | Apagar *Auto Deploy* desde las 08:00, o desplegar desde una rama `release` que solo se toque al congelar |
| 8 | ✅ **RESUELTO.** `dashboard.html` y `vendor/` existen; el tablero abre con datos reales del corpus y sin datos de ejemplo | El Reto 2 ya se puede desplegar y evaluar (55% ejecución dinámica, 40% propuesta de diseño) | Hecho. Sigue valiendo la advertencia: el HTML entra en la imagen, así que **cualquier ajuste posterior exige reconstruirla** |
| 9 | ✅ **Cacheo corregido en `adea37f`**: la tabla del tablero ya no se guarda vacía; los endpoints responden `disponible: false` si el índice no está. El orden de arranque sigue importando | Si el índice llega tarde, el tablero muestra "no disponible" en vez de quedar en blanco hasta reiniciar | El script de descarga (D2) debe terminar de dejar el índice **antes** de iniciar `uvicorn` |
| 10 | ✅ **RESUELTO (19-sep).** La imagen ya no instala dependencias de UI. `streamlit`, `plotly` y `pandas` salieron de `pyproject.toml` junto con los módulos que los usaban (`src/ui/app.py`, `src/theme/streamlit_theme.py`, `src/theme/plotly_theme.py`) | La interfaz es `src/ui/static/` —HTML plano y Chart.js vendorizado— y no necesita ninguno de los tres. `pandas` no lo importaba nadie | Hecho: `requirements.txt` regenerado con `uv export`. *Reducción de tamaño: **no medida*** |
| 11 | **Endpoints `/api/*` públicos y de solo lectura en los tres dominios**, incluido `agent.*`. `/api/trace` (que exponía preguntas y salidas del modelo) **se cerró en `86e8244`**: solo responde con `ARPIA_DEBUG_TRACE` | Que `ARPIA_DEBUG_TRACE` quede encendido por error en Coolify | Dejarla **vacía** en el despliegue evaluado (`/health` advierte si `debug_trace` está activo) |

**Dato medido por el equipo** (comentario del `Dockerfile`): índice + encoder ≈ **3,8 GB de
RAM por proceso**. Con 8 GB de contenedor, dos workers rozan el límite.

---

### 3.1 Medido en una prueba local completa (19 de septiembre)

Con el índice de la Etapa 1 y `bge-m3` en CPU, en una máquina de desarrollo:

- **Carga del índice:** 4 s medidos en la primera llamada a `/health` (límite del healthcheck: 5 s). Desde `adea37f`
  el arranque lo precalienta, así que ese tiempo se paga al arrancar; en el servidor de ADL, con otro disco, puede
  ser mayor y es lo que hay que esperar antes de dar el contenedor por listo.
- **Encoder:** la primera carga (descarga incluida) tardó **473 s**. Después, segundos.
- **Pesos duplicados:** el snapshot de `BAAI/bge-m3` trae `model.safetensors` **y** `pytorch_model.bin`
  (2,12 GB cada uno), y Hugging Face guarda además un caché de fragmentos: **8,6 GB en disco** para un modelo
  que solo necesita una copia. Para la imagen (D3) hay que descargar solo `model.safetensors` y los archivos de
  tokenizador y configuración (`allow_patterns`), y limpiar el caché de fragmentos.
- **`torch`:** en Windows resolvió `2.14.0+cpu`; el `requirements.txt` generado para Linux arrastra 15 paquetes
  `nvidia-*` (problema #4). Confirma que el encoder no necesita CUDA.
- **Flujo real de punta a punta funcionando** contra LiteLLM (ver `API.md` §11).

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
>
> Las rutas `/api/*` del tablero salen por el mismo puerto 8000: los tres dominios con Port
> `8000` las cubren, sin configuración adicional.

---

## 5. Decisiones por tomar

Estado de todas: **⏳ pendiente**. La columna *Recomendación* es la de quien redactó este
documento, no una decisión del equipo.

### D1 — ¿Un contenedor o varios?

| Opción | A favor | En contra |
|---|---|---|
| **A. Un recurso con los 3 dominios** (actual) | Menos piezas que puedan caerse; mitad de RAM (≈3,8 GB, no 7,6 GB) | Redesplegar el tablero reinicia también `/chat`. Y como el HTML entra en la imagen (`COPY . .`), **cualquier ajuste del frontend implica reconstruir y redesplegar** |
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
- **Orden de arranque (importa):** el script debe **terminar** de dejar el índice en `/app/data`
  *antes* de iniciar `uvicorn`. Si el servidor arranca primero y el índice llega después, la
  tabla del tablero queda cacheada vacía hasta reiniciar (problema #9). No solo falla `/chat`:
  también `/api/aggregate`, `/api/timeline`, `/api/evidence` y `/api/components`.

### D3 — ¿Dónde vive el encoder `bge-m3` (~2,2 GB)?

| Opción | A favor | En contra |
|---|---|---|
| **A. Dentro de la imagen** (descarga en el *build*) | Sin dependencia de internet en ejecución; cumple "imagen autosuficiente" | Imagen +2,2 GB |
| B. Volumen persistente (`HF_HOME`), se baja al primer arranque | Imagen más liviana | Si el servidor no llega a Hugging Face, **no hay recuperación** |

- **Medido:** el snapshot completo pesa 8,6 GB por tener los pesos duplicados (§3.1); con una sola copia son ~2,1 GB.
- **Recomendación: A.** El *build* ya necesita internet para `pip`; si llega a PyPI, es muy
  probable que llegue a Hugging Face, pero **no está verificado**.

### D4 — ¿`torch` de CPU, sin paquetes CUDA y sin dependencias de UI?

- **Recomendación: sí.** Ahorra tiempo y disco de build. Pendiente **medir** el tamaño real de
  la imagen antes y después (hay Docker 29.7 instalado en la máquina de desarrollo, así que
  se puede hacer sin gastar presupuesto de tokens).
- **Las dependencias de UI ya no están** (problema #10, cerrado el 19-sep): `streamlit`,
  `plotly` y `pandas` se eliminaron junto con los módulos que las importaban. Lo que queda por
  decidir aquí es solo el `torch` de CPU y los paquetes `nvidia-*`.

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
| D1 | **A** — un recurso con los tres dominios | 2026-09-19 | equipo | 8 GB de servidor; 3,8 GB medidos de pico con 4 peticiones concurrentes |
| D2 | **A modificada** — descarga al arrancar, en **segundo plano** | 2026-09-19 | equipo | Ver §6.1: el orden de arranque que este documento exigía ya no aplica |
| D3 | **B** — volumen `HF_HOME`, el encoder se baja al primer arranque | 2026-09-19 | verificado en el despliegue | El riesgo de D3 era "si el servidor no llega a Hugging Face". **Llega**: `encoder_listo: true` en el primer despliegue real |
| D4 | Pendiente | — | — | Los 16 paquetes `nvidia-*` + `triton` siguen en la imagen (~2,5 GB). `torch` **no** se puede quitar: `sentence-transformers` lo necesita |
| D5 | `main` | 2026-09-19 | equipo | Con *Auto Deploy* **apagado**; el congelamiento se hace por disciplina, no por rama |
| D6 | `docker-compose.yml` se queda, solo para desarrollo local | 2026-09-19 | equipo | Coolify construye desde el `Dockerfile`; el compose no participa del despliegue |
| D7 | 08:00 del sábado | 2026-09-19 | `RETO.md` | Entre 08:00 y 12:30 no se toca el endpoint |

### 6.1 Por qué D2 cambió de forma, y por qué el orden de arranque ya no aplica

La versión original de D2 en este documento decía que el script debía **terminar** de dejar
el índice antes de iniciar `uvicorn`, porque la tabla de agregación cacheaba el fallo y
quedaba vacía hasta reiniciar (problema #9). **Ese problema está corregido**: la tabla ya no
cachea el fallo y recoge el índice en la siguiente petición.

Eso permite invertir la prioridad, y la inversión importa. Si el arranque se bloquea durante
1,6 GB de descarga, el contenedor no responde durante minutos justo en la ventana en que
Traefik decide si enrutarlo; los tres dominios contestan `503 no available server` y la
ventana de evaluación se pierde entera. Con la descarga en segundo plano el servicio responde
desde el primer segundo, `/health` declara `index_loaded: false` mientras tanto —que es la
verdad, no un disfraz— y el índice se incorpora solo.

**Esto hay que verificarlo en cada despliegue, no darlo por hecho**: cuando `/health` pase a
`index_loaded: true`, comprobar que `GET /api/aggregate?group_by=fenomeno` devuelve `filas`
no vacías. Si vinieran vacías, el problema #9 habría vuelto y la solución es reiniciar el
contenedor una vez terminada la descarga.

### 6.2 Procedimiento real del despliegue (2026-09-19)

Se hizo **por la API de Coolify** (v4.3.23), no por el panel. Equivale al Anexo A de la
Especificación, con dos diferencias que conviene conocer si alguien revisa la UI:

1. **La llave SSH se generó fuera de Coolify** (`ssh-keygen`) y se subió por
   `POST /api/v1/security/keys`. El Anexo A.1 la genera desde el panel; el resultado es el
   mismo par ED25519 registrado como *Deploy Key* de solo lectura en GitHub.
2. **Los bind mounts NO están en la sección *Storages*** sino en *Advanced → Custom Docker
   Options*. La API de esta versión solo acepta volúmenes con nombre (`type: persistent`), y
   hacían falta bind mounts a rutas del host. La línea es:

   ```
   -v /data/arpia/corpus:/app/data -v /data/arpia/state:/app/state -v /data/arpia/hf:/app/.cache/huggingface
   ```

   `/app/data` **no** va en solo lectura: el entrypoint escribe ahí el índice que descarga.

Identificadores del recurso, por si hay que operarlo por API:

| Elemento | UUID |
|---|---|
| Proyecto `arpia` | `cd9ktfnmo03k0ndfk5kh5trr` |
| Aplicación `arpia` | `ubkeuntj3e9vvtzdqixfvyqt` |
| Servidor `localhost` | `1gsc6lsc1zmrkjxspggiwszh` |
| Deploy key | `dfmc6dxlkvkcb9ihungxsago` |

### 6.3 De dónde sale el índice

`DATA_FILES` apunta a la entrega de la Etapa 1 del equipo en Google Drive, que además del
índice contiene el encoder `bge-m3` completo (`modelos/bge_m3/`) por si Hugging Face fallara:

```
index.faiss     1gI0NOmoXAQhSrqfOucPGXcreZ40pAtxJ
metadata.jsonl  1d_ENaXJGDbDgw3ldlsTq1E0Ha1eLnFa2
manifest.json   18e6_O6kE7hENMa00kqyfNajVKjI9AI4l
```

Formato de la variable: `nombre=url` separados por espacios. Se descargan con `curl` sobre
`drive.usercontent.google.com/download?export=download&confirm=t&id=<id>`, que sirve archivos
grandes sin autenticación y admite rangos (por eso el entrypoint puede reanudar). El
entrypoint descarta cualquier `.faiss` o `.jsonl` de menos de 100 MB: cuando Drive excede
cuota responde `200` con una página HTML, y sin esa comprobación el fallo sería silencioso.

---

## 7. Lista de verificación antes de las 08:00 del sábado

- [ ] Repo **privado**; ADL y evaluadores invitados como colaboradores.
- [ ] Llave de despliegue creada en Coolify y registrada en GitHub.
- [ ] Recurso creado con *Base Directory* `/arpia` **guardado** (revisar *Build settings*).
- [ ] Los 3 dominios con Port `8000` y *No redirect*.
- [ ] Variables como *Runtime*, con `ARPIA_MODE=live`.
- [ ] *Storages* creados y el índice cargado; `GET /health` con `index_loaded: true`.
- [ ] `GET /agent-card` devuelve la ficha y su `endpoint` es el subdominio `agent.`.
- [ ] `frontagent.` abre `chat.html` y `dashboard.` abre el **tablero** (no el aviso "la interfaz
      … no está incluida en esta imagen").
- [ ] `GET /api/aggregate?group_by=fenomeno` devuelve `filas` **no vacías** (prueba de que la
      tabla se construyó con el índice ya montado). Si vino vacía, reiniciar el contenedor.
- [ ] `GET /api/evidence/<chunk_id de una cita real>` devuelve el fragmento.
- [ ] Una pregunta real por `POST /chat` con `mode: "live"` y `estado: "ok"`.
- [ ] *Auto Deploy* apagado. Nadie hace `push` a la rama desplegada hasta las 12:30.
- [x] `deploy-test/` eliminado del repo.

## 8. Qué no se ha verificado

Para que nadie lo dé por sabido:

- RAM y disco del servidor de Coolify.
- Si ese servidor tiene salida a `huggingface.co` y a `download.pytorch.org`.
- El tamaño real de la imagen (con y sin CUDA).
- El nombre de equipo definitivo en los dominios.
- Cuánto tarda el primer arranque **en el servidor de ADL** (en la máquina de desarrollo: 473 s con descarga; carga posterior, segundos).
- Cuánto se redujo la imagen al sacar `streamlit`, `plotly` y `pandas` (19-sep). No se midió antes ni después.
- Que Coolify acepte los tres dominios sobre un mismo recurso con el mismo puerto (es lo
  esperable por la documentación de ADL, pero no se ha probado en su panel).

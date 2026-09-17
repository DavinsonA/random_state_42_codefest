---
name: coolify-deploy
description: Empaquetar y desplegar la aplicacion en Coolify. Usar al preparar el despliegue, escribir o corregir el Dockerfile, configurar variables de entorno, o cuando un despliegue falla o la app no responde tras el push.
---

# Despliegue en Coolify

## Flujo
1. Generar una llave SSH desde Coolify y cargarla en el repositorio de GitHub.
2. Hacer push a la rama configurada, con `Dockerfile` en la raiz.
3. En Coolify: apuntar a la rama, elegir build por Dockerfile, desplegar.
4. Coolify aprovisiona, construye y expone una URL publica.

Coolify tambien tiene catalogo de un clic para bases de datos (Postgres, Redis,
vectoriales). Usalo antes de dockerizar una base a mano.

## Antes de cada push — obligatorio
```bash
uv run python scripts/preflight.py   # secretos, licencias, tokens, contrato
docker compose up --build            # reproducir el build localmente
```
Un build que falla en Coolify y no en local casi siempre es una dependencia del
sistema ausente en la imagen slim, o una variable de entorno sin configurar.

## Variables de entorno
**Nunca** quemar credenciales en el codigo: se configuran en el panel de
Coolify. Esto es criterio de calificacion explicito, no solo buena practica.
Lista de variables requeridas: `.env.example`.

## API y UI en la misma imagen
El `Dockerfile` arranca la API por defecto. Para la UI, sobrescribir el comando
en el panel de Coolify:
```
streamlit run src/ui/app.py --server.port 8501 --server.address 0.0.0.0
```

## Depuracion
- Lee los logs de build **y** de runtime en el panel; el fallo suele estar en
  build, no en la app.
- Ante fallo: **reiniciar** el contenedor primero. Borrar y recrear es el
  ultimo recurso, no el primero.
- `/health` expone estado, tools registradas y si el gateway esta configurado.

## Fallos frecuentes
| Sintoma | Causa |
|---|---|
| Build falla, local funciona | falta libreria del sistema en la imagen slim |
| App arranca y muere | variable de entorno obligatoria sin configurar |
| 502 desde la URL publica | puerto expuesto no coincide con el del panel |
| Indice vectorial no encontrado | `data/` no montado: es volumen, no va en la imagen |

# deploy-test

App dummy cuyo único propósito es verificar que la cadena
**GitHub → Coolify → URL pública** funciona, aislada de cualquier fallo del
aplicativo real (`arpia/`). No tiene base de datos, modelo, índice ni
variables de entorno obligatorias — arranca en cualquier parte. Si esto no
despliega, el problema es Coolify o su configuración, no la aplicación.

Verificado localmente: `docker build` y `docker run` funcionan, `/` y
`/health` responden `200` con y sin `COMMIT_SHA` seteada.

**Bórrala del repo una vez validada la cadena de despliegue.** Si sigue aquí
el día de la entrega, un revisor que ve una carpeta llamada "test de
despliegue" en el entregable final se pregunta qué más quedó sin limpiar.

```bash
git rm -r deploy-test
```

## Configuración exacta en el panel de Coolify — `deploy-test`

1. **New Resource** → **Application** → **Public Repository** (o
   **Private Repository (with GitHub App)** si aplica) → pega la URL del
   repo `random_state_42_codefest` y la rama `main`.
2. **Build Pack**: `Dockerfile`.
3. **Base Directory**: `/deploy-test`.
4. **Watch Paths**: `deploy-test/**` (así un cambio en `arpia/` no dispara
   un redeploy de esta app dummy, y viceversa).
5. **Ports Exposes**: `8000`.
6. Deploy. Cuando termine, verificar:
   - `GET https://<dominio-asignado>/` → `{"status":"ok","service":"deploy-test","commit":"..."}`
   - `GET https://<dominio-asignado>/health` → `{"status":"ok"}`
7. Si algo falla aquí, el problema es de infraestructura (build pack, base
   directory, puerto, red) — no de código, porque esta app no tiene nada que
   pueda fallar por sí misma.

## Configuración para el aplicativo real — `arpia/`

Misma mecánica, otra carpeta:

- **Base Directory**: `/arpia`
- **Watch Paths**: `arpia/**`
- **Build Pack**: `Dockerfile`
- **Ports Exposes**: `8000` (API — lo que evalúa el jurado). Para exponer
  también la UI, ver `../arpia-bundle/.claude/skills/coolify-deploy/SKILL.md`.
- Variables de entorno: copiar `arpia/.env.example` al panel de Coolify.
  Sin ellas, `ARPIA_MODE` cae a `stub` y la app arranca igual.

## Nota conocida

En repositorios **privados** con deploy key, Coolify a veces no persiste el
`Base Directory` fijado durante el asistente inicial de creación del
recurso, y hay que volver a fijarlo manualmente en **Build settings**
después de crear la aplicación. Como este repositorio será **público**, es
poco probable que ocurra — pero si el primer deploy construye desde la raíz
del monorepo en vez de `/deploy-test` o `/arpia`, esto es lo primero a
revisar.

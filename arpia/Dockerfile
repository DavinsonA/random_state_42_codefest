# Imagen unica: sirve la API y las interfaces estaticas. Coolify construye
# desde este archivo con Base Directory = /arpia.
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
# El encoder bge-m3 (~2,2 GB) se descarga aqui. Montar esta ruta como
# volumen persistente: sin eso, cada despliegue la vuelve a bajar.
ENV HF_HOME=/app/.cache/huggingface
WORKDIR /app

# requirements.txt (generado con `uv export`) en vez de pyproject.toml: capa
# cacheable, sin resolver dependencias en cada build. Va primero y solo, para
# que un cambio de codigo no invalide la instalacion de dependencias.
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copia unica del contexto. La frontera de que entra y que no la define
# `.dockerignore`, no una lista de COPY en este archivo: durante el evento se
# anaden archivos (agent_card.json, static/, el tablero) y una lista explicita
# se olvida de actualizar justo la noche de la entrega.
COPY . .

EXPOSE 8000

# Coolify usa esto para saber si el despliegue quedo sano. httpx ya es
# dependencia del proyecto, no agrega nada nuevo a la imagen.
# Nota: /health responde 503 solo si NADA funciona; un `degraded` sigue siendo
# un despliegue util y no debe marcar el contenedor como unhealthy.
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
  CMD python -c "import httpx; httpx.get('http://localhost:8000/health').raise_for_status()"

CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000"]

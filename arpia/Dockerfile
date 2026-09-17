# Imagen unica que sirve API y UI. Coolify construye desde este archivo.
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
WORKDIR /app

# requirements.txt (generado con `uv export`) en vez de pyproject.toml:
# capa cacheable, sin resolver dependencias en cada build.
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ ./src/
COPY docs/design/ ./docs/design/

EXPOSE 8000 8501

# Coolify usa esto para saber si el despliegue quedo sano. httpx ya es
# dependencia del proyecto, no agrega nada nuevo a la imagen.
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
  CMD python -c "import httpx; httpx.get('http://localhost:8000/health').raise_for_status()"

# Por defecto arranca la API. Para la UI, sobrescribir el comando en Coolify:
#   streamlit run src/ui/app.py --server.port 8501 --server.address 0.0.0.0
CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000"]

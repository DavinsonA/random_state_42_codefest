#!/bin/sh
# Arranque del contenedor: sirve de inmediato y trae el indice si falta.
#
# **Por que existe.** El Anexo A.4 de la Especificacion exige una imagen
# autosuficiente: lo que la solucion necesita —librerias, modelos, datos— se
# declara en el repositorio o entra por variables de entorno, no lo copia
# alguien a mano en el servidor por SSH. El indice son 1,6 GB: hornearlo en la
# imagen la lleva a ~6 GB y hace que cada build vuelva a moverlos, asi que
# entra por `DATA_FILES` en el primer arranque y se queda en el volumen.
#
# **Por que en segundo plano.** El servicio responde desde el primer segundo y
# la descarga avanza detras. `/health` reporta `index_loaded: false` mientras
# tanto —que es la verdad— y el indice se incorpora solo cuando aterriza, sin
# reiniciar nada. Bloquear el arranque durante 1,6 GB de descarga dejaria el
# contenedor sin responder justo cuando Traefik decide si enrutarlo, que es
# como se pierde la ventana de evaluacion entera.
#
# La descarga vive en `descargar_indice.py` y no aqui: esta imagen no trae
# `curl` ni `wget` —`python:3.11-slim` no los incluye— y el intento con `curl`
# fallo en el despliegue real por exactamente eso.

if [ -f "${VECTOR_INDEX_PATH:-data/encoder_bge_m3}/index.faiss" ]; then
    echo "[arranque] indice presente"
elif [ -n "$DATA_FILES" ]; then
    python /app/descargar_indice.py &
else
    echo "[arranque] sin indice y sin DATA_FILES: el servicio arranca degradado" >&2
fi

exec "$@"

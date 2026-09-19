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
# reiniciar nada: la tabla de agregacion no cachea el fallo. Bloquear el
# arranque durante la descarga dejaria el contenedor sin responder justo
# cuando Traefik decide si enrutarlo, que es como se pierde la ventana de
# evaluacion entera.
#
# `DATA_FILES` es una lista de `nombre=url` separados por espacios. Generica a
# proposito: si el origen cambia, se edita una variable en Coolify y no se
# reconstruye la imagen.
set -e

DESTINO="${VECTOR_INDEX_PATH:-data/encoder_bge_m3}"

#: Por debajo de esto, lo que bajo no es un indice: es la pagina de error de
#: Google Drive cuando excede cuota, que llega con codigo 200 y cuerpo HTML.
#: Sin esta comprobacion el fallo es silencioso y solo se nota al preguntar.
MINIMO_FAISS=104857600   # 100 MB

descargar_uno() {
    nombre="$1"
    url="$2"
    salida="$DESTINO/$nombre"

    if [ -f "$salida" ]; then
        echo "[arranque] $nombre ya presente"
        return 0
    fi

    echo "[arranque] descargando $nombre"
    # --continue-at permite reanudar si el contenedor se reinicio a media
    # descarga; el origen soporta rangos (comprobado).
    if ! curl -fsSL --retry 3 --retry-delay 5 --continue-at - "$url" -o "$salida.parcial"; then
        echo "[arranque] FALLO la descarga de $nombre" >&2
        return 1
    fi

    tam=$(wc -c < "$salida.parcial")
    case "$nombre" in
        *.faiss|*.jsonl)
            if [ "$tam" -lt "$MINIMO_FAISS" ]; then
                echo "[arranque] $nombre pesa $tam B: no es el archivo, es un error del origen" >&2
                rm -f "$salida.parcial"
                return 1
            fi
            ;;
    esac

    # Renombrar al final: mientras se descarga, el archivo NO tiene su nombre
    # definitivo. Asi el proceso de la API nunca abre un indice a medio bajar,
    # que es un fallo mucho peor que no tener indice.
    mv "$salida.parcial" "$salida"
    echo "[arranque] $nombre listo ($tam B)"
}

traer_indice() {
    mkdir -p "$DESTINO"
    fallos=0
    for entrada in $DATA_FILES; do
        nombre=$(printf '%s' "$entrada" | cut -d= -f1)
        url=$(printf '%s' "$entrada" | cut -d= -f2-)
        descargar_uno "$nombre" "$url" || fallos=$((fallos + 1))
    done
    if [ "$fallos" -eq 0 ]; then
        echo "[arranque] indice completo en $DESTINO"
    else
        # Nunca mata el contenedor: sin indice el sistema sigue respondiendo y
        # lo declara en /health. Un arranque fallido, en cambio, deja los tres
        # dominios en 503 durante toda la ventana de evaluacion.
        echo "[arranque] $fallos archivo(s) no se pudieron traer; el servicio sigue sin ellos" >&2
    fi
}

if [ -f "$DESTINO/index.faiss" ]; then
    echo "[arranque] indice presente en $DESTINO"
elif [ -n "$DATA_FILES" ]; then
    traer_indice &
else
    echo "[arranque] sin indice y sin DATA_FILES: el servicio arranca degradado" >&2
fi

exec "$@"

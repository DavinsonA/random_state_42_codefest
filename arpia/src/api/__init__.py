"""La capa HTTP: lo que ADL consume y lo que el navegador carga.

`main.py` enruta, `chat.py` ejecuta el turno, `contracts.py` define la forma de
todo lo que entra y sale. La frontera con el grafo esta escrita en
`CONTRATO_GRAFO.md`: este paquete no conoce nodos ni prompts.

Invariante del paquete entero: **ningun endpoint devuelve 500 ni 422**. Un fallo
se reporta dentro de un 200, en `metadata.estado` o en `disponible: false`.
"""

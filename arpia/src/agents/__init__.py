"""Los agentes y el grafo que los coordina.

Entrada: `graph.build_graph()`. El turno va `begin -> planificar -> ejecutar ->
componer -> verificar`, con una sola replanificacion como maximo; el coste en
llamadas al modelo esta acotado por construccion (ver `graph.py`).

Tres piezas cuestan CERO tokens y por eso van antes que el modelo: `guardian`
(rechaza inyeccion y fuera de dominio), `memory` (cache semantico) y `verifier`
(solo paga una llamada si la respuesta no cuadra con su evidencia).
"""

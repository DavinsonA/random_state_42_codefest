"""Recuperacion sobre el corpus: indice FAISS, encoder local y agregaciones.

Todo corre en la CPU del contenedor y **no gasta tokens del presupuesto**. Es la
asimetria que define al sistema: buscar y contar es gratis, solo se paga cuando
hay que redactar.

`encoder.py` es el unico que instancia el modelo de embeddings (~2,3 GB: dos
instancias matan el contenedor). `enrich.py` explica que campos son derivados
—`organizacion` y `anio`— y hasta donde llegan: solo el 34% de los documentos
declara ano, y esa cobertura se reporta siempre, nunca se disimula.
"""

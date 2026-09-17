---
name: geo-temporal-enrichment
description: Extraer y normalizar fecha y lugar de documentos o chunks para habilitar mapas y lineas de tiempo. Usar cuando haga falta georreferenciar o fechar contenido textual, o cuando una visualizacion espacial o temporal no tenga los campos que necesita.
---

# Enriquecimiento geo-temporal

## Por que existe este skill
Un indice vectorial construido para recuperacion semantica tipicamente guarda
`doc_id`, `chunk_id`, fuente, formato y texto — **pero no fecha ni lugar**.
Sin esos dos campos no hay mapa ni linea de tiempo posibles, por buena que sea
la recuperacion. Este es el hueco mas caro de tapar a media competencia.

## Regla de oro
El enriquecimiento **no reindexa**: anade campos a la metadata existente,
conservando `chunk_id` como llave. Reconstruir embeddings cuesta horas; anadir
una columna cuesta minutos.

```python
{"chunk_id": "...", "doc_id": "...",   # llaves existentes, NO se tocan
 "fecha": "2024-03-15",                 # ISO 8601, anadido
 "fecha_confianza": "alta",             # alta | media | inferida
 "lugar": "Guaviare, Colombia",
 "lat": 2.57, "lon": -72.64,
 "lugar_granularidad": "departamento"}  # pais | departamento | municipio | punto
```

## Fechas
Los formatos varian por pais de origen: `DD/MM/AAAA` (Colombia), `DD.MM.AAAA`
(Suiza), `MM/DD/AAAA` (EE.UU.). Una fecha mal parseada es peor que ninguna.

- `dateparser` resuelve la mayoria; pasa `languages=["es","en","pt"]` y
  `DATE_ORDER` segun la fuente cuando se conozca.
- Distingue **fecha del documento** (publicacion) de **fecha del evento**
  (mencionada en el texto). No son lo mismo y confundirlas rompe la cronologia.
- Marca la confianza. Una fecha inferida del nombre del archivo no vale lo
  mismo que una extraida del encabezado.

## Lugares
- La granularidad de la coordenada debe corresponder a la escala del analisis:
  para vista por pais basta un centroide nacional; para vista municipal hacen
  falta coordenadas por municipio.
- Resuelve contra un gazetteer **local** (GeoNames, DIVIPOLA para Colombia)
  antes de pensar en un servicio externo: sin red, sin rate limit, reproducible.
- Ambiguedad: hay muchos toponimos repetidos. Desambigua con el pais o la
  region del documento antes de aceptar una coordenada.
- Guarda siempre el texto original del toponimo junto a la coordenada, para
  poder auditar el error.

## Verificacion
Antes de dar por bueno el enriquecimiento:
1. % de chunks con fecha y con lugar (cobertura).
2. Muestreo manual de 20 casos: ¿la fecha y el lugar son los correctos?
3. Histograma de fechas: picos absurdos (todo en 1970, o en el ano actual)
   delatan un parseo roto.

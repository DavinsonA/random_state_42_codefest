---
name: data-viz-plotly
description: Crear visualizaciones y preparar datos para graficos. Usar al construir charts, series temporales, mapas o dashboards; al elegir tipo de grafico; o al dar formato a un DataFrame para visualizar.
---

# Visualizacion de datos

## Primero la tarea, despues el grafico
Identifica que pregunta responde la vista antes de elegir el tipo. El error
comun es usar el grafico que uno ya sabe hacer, no el que la tarea pide.

| Tarea | Grafico |
|---|---|
| Comparacion | barras, tabla |
| Relacion | dispersion, red, matriz |
| Distribucion | histograma, cajas |
| Composicion | apilado, treemap |
| **Tendencia** | linea, area, Gantt |
| **Espacial** | mapa de puntos / coropletico / de calor |

## Mapas: cual usar
- **Puntos**: importa *donde* ocurre algo. La ubicacion es el canal; el tamano
  codifica magnitud si hace falta.
- **Coropletico**: comparar magnitudes **entre regiones** delimitadas.
- **Calor**: densidad continua; el fenomeno no respeta limites administrativos.

## Trampa frecuente en series temporales
Unir con lineas rectas observaciones espaciadas sugiere una tendencia continua
que los datos no sustentan. Si las mediciones son escasas, usa puntos o curvas
y declara la granularidad de agregacion en el titulo. Si el titulo dice "por
mes", **toda** la serie va agregada por mes.

## Colores
El template `arpia` ya esta registrado por `apply()`. No pases colores a mano
salvo para mapear fenomenos:
```python
color_discrete_map=tokens.phenomenon_map()
```
Escala secuencial para magnitud. Divergente **solo** si hay negativo, neutro y
positivo con significado. Nunca asignes colores arbitrarios a valores
cuantitativos.

## Accesibilidad
- El color no puede ser el unico portador de significado: anade etiqueta,
  icono, posicion o forma.
- Verifica contraste entre colores adyacentes de una escala.
- Leyendas fuera del area de datos: nunca tapando informacion.

## Preparacion de datos
- Normaliza fechas a ISO antes de graficar; el formato varia por pais de origen.
- Declara la unidad en el titulo del eje.
- Agrega en el DataFrame (`pandas`), no dentro del codigo del grafico.

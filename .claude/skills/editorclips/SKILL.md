---
name: editorclips
description: Cuando el usuario suba varios clips de vídeo y pida montar una variante o varias, indicando cuál debe ir primero (el "clip principal"). Genera montajes con ffmpeg recortando los clips secundarios y produce varias variantes con distinto orden y punto de corte.
---

# Skill: editor-clips

## Cuándo usar esta skill
Cuando el usuario suba varios clips de vídeo y pida montar una variante o varias, indicando cuál debe ir primero.

## Instrucciones

1. Pide (o toma del mensaje del usuario) cuál es el "clip principal" — ese va siempre en primer lugar del montaje.
2. Para el resto de clips (secundarios):
   - Recorta como máximo los primeros 2 segundos y los últimos 2 segundos de cada uno (ajustable).
   - Si un clip dura más de 8 segundos, recórtalo a un tramo de 8 segundos tomado del centro.
3. Duración máxima total del montaje: 25 segundos (ajustable). Si al unir todos los clips se supera ese límite, recorta proporcionalmente los clips secundarios (nunca el principal) hasta encajar.
4. Genera 5 variantes distintas, cada una cambiando alguno de estos parámetros:
   - Orden de los clips secundarios (el principal siempre primero).
   - Punto de corte dentro de cada clip secundario (inicio / centro / final).
5. Usa `ffmpeg` para los recortes y concatenación. Exporta cada variante como `variante_1.mp4`, `variante_2.mp4`, etc.
6. Al terminar, resume qué contiene cada variante (orden y duración de cada clip).

## Notas
- No hay análisis de contenido visual: los recortes son por tiempo, no por "mejor momento" del clip, salvo que se indique lo contrario.
- Si el usuario dice "prioriza que se vea tal cosa", pide que aclare en qué segundo aproximado ocurre, ya que no se analiza el vídeo automáticamente.

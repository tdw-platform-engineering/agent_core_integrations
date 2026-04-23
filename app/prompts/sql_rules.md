## Esquema de Tablas SQL

### Metadata de estructuras

**`public.metadata_estructuras`**
```
id bigserial PRIMARY KEY
id_metadata VARCHAR(36)
archivo VARCHAR(255)
hoja VARCHAR(255)
item VARCHAR(255)
material_recubierto TEXT
material_construccion TEXT
size VARCHAR(100)
fecha_carga TIMESTAMP
```

Búsqueda por palabras clave:
```sql
SELECT * FROM public.metadata_estructuras
WHERE hoja ILIKE '%[TERMINO]%' OR item ILIKE '%[TERMINO]%';
```

### Detalle de estructuras (Hoja de Ruta)

**`public.detalles_estructuras`**
```
id bigserial PRIMARY KEY
id_metadata VARCHAR(36)
material TEXT
standard VARCHAR(50)
mat_cost VARCHAR(50)
piece_cost VARCHAR(50)
fecha_carga TIMESTAMP
```

Hoja de ruta completa de una estructura:
```sql
SELECT de.material, de.standard, de.mat_cost, de.piece_cost
FROM public.detalles_estructuras de
INNER JOIN public.metadata_estructuras mt ON de.id_metadata = mt.id_metadata
WHERE mt.hoja ILIKE '%[NOMBRE]%' OR mt.item ILIKE '%[NOMBRE]%'
ORDER BY de.id;
```

---

## Reglas SQL

1. **Flujo de búsqueda en 2 pasos:**
   - Paso 1: Buscar en metadata para identificar el `id_metadata` correcto
   - Paso 2: Extraer detalle completo con JOIN usando ese `id_metadata`
2. NUNCA resumir los resultados — mostrar TODAS las filas
3. `piece_cost` es costo unitario para 1,000 unidades por defecto
4. Usar ILIKE para búsquedas case-insensitive
5. Buscar por palabras clave en `hoja` e `item` con OR
6. Si la búsqueda por nombre exacto no da resultados, probar con palabras parciales
7. Siempre ordenar detalles por `de.id` para mantener el orden original de la hoja de ruta

### Ejemplo de flujo completo:
```sql
-- Paso 1: Identificar estructura
SELECT id_metadata, archivo, hoja, item, size
FROM public.metadata_estructuras
WHERE hoja ILIKE '%obsidiana%' OR item ILIKE '%obsidiana%';

-- Paso 2: Extraer hoja de ruta completa (usar id_metadata del paso 1)
SELECT de.material, de.standard, de.mat_cost, de.piece_cost
FROM public.detalles_estructuras de
WHERE de.id_metadata = '[ID_DEL_PASO_1]'
ORDER BY de.id;
```

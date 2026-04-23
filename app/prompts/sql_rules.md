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

1. Buscar metadata primero para identificar el `id_metadata` correcto
2. Luego extraer el detalle completo con JOIN
3. NUNCA resumir los resultados — mostrar todas las filas
4. `piece_cost` es costo unitario para 1,000 unidades por defecto
5. Usar ILIKE para búsquedas case-insensitive
6. Buscar por palabras clave en `hoja` e `item` con OR

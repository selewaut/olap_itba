-- ============================================================================
-- Carga del DW. Corre sobre las tablas de sql/tablas_fondos.sql:
--
--   createdb fci_dw
--   psql -d fci_dw -v ON_ERROR_STOP=1 -f sql/tablas_fondos.sql
--   psql -d fci_dw -v ON_ERROR_STOP=1 -f sql/dw_load.sql
--
-- Los CSV se dejan intactos. Cada uno se vuelca en una tabla
-- TEMP con el mismo header y despues se proyecta a la tabla final, que es la
-- unica que lleva las claves surrogadas.
-- ============================================================================

\set ON_ERROR_STOP on

-- Rango de las dimensiones de tiempo. Los facts van de 2010-03 a 2026-09.
\set fecha_desde '2010-03-01'
\set fecha_hasta '2026-12-31'


-- ---------------------------------------------------------------------------
-- 1. dim_mes y dim_time: no vienen de CSV, se generan.
-- ---------------------------------------------------------------------------

INSERT INTO dim_mes (mes_anio, nombre_mes)
SELECT EXTRACT(YEAR FROM d)::INT * 100 + EXTRACT(MONTH FROM d)::INT,
       TO_CHAR(d, 'Month')
FROM generate_series(DATE :'fecha_desde', DATE :'fecha_hasta', '1 month') AS d;

INSERT INTO dim_time (date_key, mes_anio, anio, trimestre, semana_anio, es_dia_habil)
SELECT d,
       EXTRACT(YEAR FROM d)::INT * 100 + EXTRACT(MONTH FROM d)::INT,
       EXTRACT(YEAR FROM d)::SMALLINT,
       EXTRACT(QUARTER FROM d)::SMALLINT,
       EXTRACT(WEEK FROM d)::SMALLINT,
       EXTRACT(ISODOW FROM d) <= 5
FROM generate_series(DATE :'fecha_desde', DATE :'fecha_hasta', '1 day') AS d;


-- ---------------------------------------------------------------------------
-- 2. Indice y DetalleIndice. Las claves surrogadas se ordenan por codigo para
--    que la carga sea reproducible.
-- ---------------------------------------------------------------------------

CREATE TEMP TABLE stg_indice (
codigo_indice TEXT,
    nombre_indice TEXT,
    region TEXT,
    tipo_indice TEXT,
    frecuencia TEXT
);
\copy stg_indice FROM 'data/processed/dim_indice.csv' CSV HEADER

INSERT INTO Indice (IndiceKey, CodigoIndice, NombreIndice, Region, TipoIndice, Frecuencia)
SELECT ROW_NUMBER() OVER (ORDER BY codigo_indice),
       codigo_indice, nombre_indice, region, tipo_indice, frecuencia
FROM stg_indice;

CREATE TEMP TABLE stg_detalle_indice (
indice_detalle_key TEXT,
    codigo_indice TEXT,
    nombre TEXT,
    moneda TEXT,
    unidad TEXT,
    fuente TEXT
);
\copy stg_detalle_indice FROM 'data/processed/dim_indice_detalle.csv' CSV HEADER

INSERT INTO DetalleIndice (IndiceDetalladoKey, CodigoIndiceDetalle, IndiceKey, NombreIndice, Moneda, Unidad, Fuente)
SELECT ROW_NUMBER() OVER (ORDER BY d.indice_detalle_key),
       d.indice_detalle_key, i.IndiceKey, d.nombre, d.moneda, d.unidad, d.fuente
FROM stg_detalle_indice d
JOIN Indice i ON i.CodigoIndice = d.codigo_indice;


-- ---------------------------------------------------------------------------
-- 3. DetalleFondosTotal. ObjetivoKey sale de casear el benchmark del CSV con
--    las series que ya estan cargadas. Las que no matchean quedan en NULL.
-- ---------------------------------------------------------------------------

CREATE TEMP TABLE stg_fondo (
id_fondo TEXT,
    valid_from TEXT,
    valid_to TEXT,
    is_current TEXT,
    nombre_fondo TEXT,
    region TEXT,
    tipo_fondo TEXT,
    tipo_renta TEXT,
    tipo_renta_mixta TEXT,
    moneda TEXT,
    benchmark TEXT,
    sociedad_gestora TEXT,
    cantidad_clases TEXT
);
\copy stg_fondo FROM 'data/processed/dim_fondo.csv' CSV HEADER

CREATE TEMP TABLE benchmark_indice (benchmark, codigo_indice_detalle) AS
SELECT * FROM (VALUES
    ('A3500',      'USD_OFICIAL_MINORISTA'),
    ('Badlar',     'BADLAR'),
    ('Bovespa',    'BOVESPA'),
    ('Mar',        'MERVAL_ARS'),
    ('Merval',     'MERVAL_ARS'),
    ('S&P Mar',    'MERVAL_ARS'),
    ('S&P Mer 25', 'MERVAL_ARS'),
    ('S&P Merval', 'MERVAL_ARS')
) AS t(benchmark, codigo_indice_detalle);

INSERT INTO DetalleFondosTotal (FondoKey, IdFondo, ValidoDesde, ValidoHasta, EsActual, NombreFondo,
    Region, TipoFondo, TipoRenta, TipoRentaMixta, Moneda, Benchmark, ObjetivoKey, SociedadGestora, CantidadClases)
SELECT ROW_NUMBER() OVER (ORDER BY s.id_fondo, s.valid_from),
       s.id_fondo, s.valid_from::DATE, NULLIF(s.valid_to, '')::DATE, s.is_current::BOOLEAN, s.nombre_fondo,
       s.region, s.tipo_fondo, s.tipo_renta, s.tipo_renta_mixta, s.moneda, s.benchmark,
       d.IndiceDetalladoKey, s.sociedad_gestora, s.cantidad_clases::SMALLINT
FROM stg_fondo s
LEFT JOIN benchmark_indice b ON b.benchmark = s.benchmark
LEFT JOIN DetalleIndice d ON d.CodigoIndiceDetalle = b.codigo_indice_detalle;


-- ---------------------------------------------------------------------------
-- 4. dim_detalle_fondo_clase. FondoKey se resuelve por contencion de fechas:
--    la version del fondo que cubre el periodo de la version de la clase.
-- ---------------------------------------------------------------------------

CREATE TEMP TABLE stg_clase (
id_fondo_clase_dim TEXT,
    id_fondo TEXT,
    id_codigo_fondo_clase TEXT,
    nombre_fondo_clase_origen TEXT,
    nombre_fondo TEXT,
    nombre_clase TEXT,
    valid_from TEXT,
    valid_to TEXT,
    is_current TEXT,
    calificacion TEXT,
    tipo_cliente TEXT,
    comision_ingreso TEXT,
    honorarios_adm_sg TEXT,
    honorarios_adm_sd TEXT,
    otros_gastos TEXT,
    comision_rescate TEXT,
    moneda TEXT
);
\copy stg_clase FROM 'data/processed/dim_fondo_clase.csv' CSV HEADER

INSERT INTO dim_detalle_fondo_clase (FondoClaseKey, IdFondoClaseDim, IdFondo, IdCodigoFondoClase,
    NombreFondoClaseOrigen, NombreFondo, NombreClase, ValidoDesde, ValidoHasta, EsActual,
    Calificacion, TipoCliente, ComisionIngreso, HonorariosAdmSg, HonorariosAdmSd, OtrosGastos,
    ComisionRescate, Moneda, FondoKey)
SELECT ROW_NUMBER() OVER (ORDER BY s.id_fondo_clase_dim, s.valid_from),
       s.id_fondo_clase_dim, s.id_fondo, s.id_codigo_fondo_clase, s.nombre_fondo_clase_origen,
       s.nombre_fondo, s.nombre_clase, s.valid_from::DATE, NULLIF(s.valid_to, '')::DATE,
       s.is_current::BOOLEAN, NULLIF(s.calificacion, ''), s.tipo_cliente,
       s.comision_ingreso::NUMERIC(12,4), s.honorarios_adm_sg::NUMERIC(12,4),
       s.honorarios_adm_sd::NUMERIC(12,4), s.otros_gastos::NUMERIC(12,4),
       s.comision_rescate::NUMERIC(12,4), s.moneda,
       (SELECT f.FondoKey FROM DetalleFondosTotal f
         WHERE f.IdFondo = s.id_fondo
           AND f.ValidoDesde <= s.valid_from::DATE
           AND (f.ValidoHasta >= s.valid_from::DATE OR f.ValidoHasta IS NULL
                OR f.ValidoHasta >= NULLIF(s.valid_to, '')::DATE)
         ORDER BY f.ValidoDesde LIMIT 1)
FROM stg_clase s;


-- ---------------------------------------------------------------------------
-- 5. CotizacionIndices. Las series mensuales van con MesAno y sin Fecha.
-- ---------------------------------------------------------------------------

CREATE TEMP TABLE stg_cotizacion (
fecha TEXT,
    indice_detalle_key TEXT,
    valor TEXT,
    frecuencia TEXT,
    mes_anio TEXT
);
\copy stg_cotizacion FROM 'data/processed/fact_cotizacion.csv' CSV HEADER

INSERT INTO CotizacionIndices (Fecha, MesAno, IndiceDetalladoKey, Valor, Frecuencia)
SELECT NULLIF(c.fecha, '')::DATE, NULLIF(c.mes_anio, '')::INTEGER, d.IndiceDetalladoKey,
       c.valor::NUMERIC(24,16), c.frecuencia
FROM stg_cotizacion c
JOIN DetalleIndice d ON d.CodigoIndiceDetalle = c.indice_detalle_key;


-- ---------------------------------------------------------------------------
-- 6. Los dos facts de fondos. Las 34 columnas del CSV se copian a una TEMP
--    con el mismo header (el \copy mapea por posicion) y despues se proyecta
--    solo lo que vive en la tabla. FondoClaseKey se resuelve por contencion
--    de fechas contra la version de la clase vigente en esa fecha.
-- ---------------------------------------------------------------------------

CREATE TEMP TABLE stg_fondos (
fecha TEXT,
    id_fondo_clase_dim TEXT,
    id_fondo TEXT,
    id_codigo_fondo_clase TEXT,
    nombre_fondo_clase_origen TEXT,
    nombre_fondo TEXT,
    nombre_clase TEXT,
    tipo_fondo TEXT,
    tipo_renta TEXT,
    region TEXT,
    tipo_renta_mixta TEXT,
    duracion TEXT,
    benchmark TEXT,
    moneda TEXT,
    tipo_cliente TEXT,
    vcp_actual TEXT,
    vcp_anterior TEXT,
    variacion_diaria TEXT,
    reexpresion_pesos TEXT,
    variacion_mensual TEXT,
    variacion_anual TEXT,
    cantidad_cuotaparte_actual TEXT,
    cantidad_cuotaparte_anterior TEXT,
    patrimonio_neto_actual TEXT,
    patrimonio_neto_anterior TEXT,
    flujo_neto TEXT,
    calificacion TEXT,
    sociedad_gestora TEXT,
    comision_ingreso TEXT,
    honorarios_adm_sg TEXT,
    honorarios_adm_sd TEXT,
    otros_gastos TEXT,
    comision_rescate TEXT,
    plazo_liquidacion_dias TEXT
);

\copy stg_fondos FROM 'data/processed/fact_fondos_sbs.csv' CSV HEADER

INSERT INTO fact_fondos_sbs (FondoClaseKey, IdFondoClaseDim, IdFondo, Fecha, VcpActual, VcpAnterior,
    ReexpresionPesos, VariacionDiaria, VariacionMensual, VariacionAnual, CantidadCuotaparteActual,
    CantidadCuotaparteAnterior, PatrimonioNetoActual, PatrimonioNetoAnterior, FlujoNeto)
SELECT v.FondoClaseKey, s.id_fondo_clase_dim, s.id_fondo, s.fecha::DATE,
       s.vcp_actual::NUMERIC(20,3), s.vcp_anterior::NUMERIC(20,3), s.reexpresion_pesos::NUMERIC(20,3),
       s.variacion_diaria::NUMERIC(14,3), s.variacion_mensual::NUMERIC(14,3), s.variacion_anual::NUMERIC(14,3),
       s.cantidad_cuotaparte_actual::NUMERIC(20,4), s.cantidad_cuotaparte_anterior::NUMERIC(20,4),
       s.patrimonio_neto_actual::NUMERIC(20,2), s.patrimonio_neto_anterior::NUMERIC(20,2),
       s.flujo_neto::DOUBLE PRECISION
FROM stg_fondos s
JOIN dim_detalle_fondo_clase v
  ON v.IdFondoClaseDim = s.id_fondo_clase_dim
 AND v.ValidoDesde <= s.fecha::DATE
 AND (v.ValidoHasta >= s.fecha::DATE OR v.ValidoHasta IS NULL);

TRUNCATE stg_fondos;

\copy stg_fondos FROM 'data/processed/fact_fondos_competencia.csv' CSV HEADER

INSERT INTO fact_fondos_competencia (FondoClaseKey, IdFondoClaseDim, IdFondo, MesAno, VcpActual,
    VcpAnterior, ReexpresionPesos, VariacionDiaria, VariacionMensual, VariacionAnual,
    CantidadCuotaparteActual, CantidadCuotaparteAnterior, PatrimonioNetoActual, PatrimonioNetoAnterior, FlujoNeto)
SELECT v.FondoClaseKey, s.id_fondo_clase_dim, s.id_fondo,
       EXTRACT(YEAR FROM s.fecha::DATE)::INT * 100 + EXTRACT(MONTH FROM s.fecha::DATE)::INT,
       s.vcp_actual::NUMERIC(20,3), s.vcp_anterior::NUMERIC(20,3), s.reexpresion_pesos::NUMERIC(20,3),
       s.variacion_diaria::NUMERIC(14,3), s.variacion_mensual::NUMERIC(14,3), s.variacion_anual::NUMERIC(14,3),
       s.cantidad_cuotaparte_actual::NUMERIC(20,4), s.cantidad_cuotaparte_anterior::NUMERIC(20,4),
       s.patrimonio_neto_actual::NUMERIC(20,2), s.patrimonio_neto_anterior::NUMERIC(20,2),
       s.flujo_neto::DOUBLE PRECISION
FROM stg_fondos s
JOIN dim_detalle_fondo_clase v
  ON v.IdFondoClaseDim = s.id_fondo_clase_dim
 AND v.ValidoDesde <= s.fecha::DATE
 AND (v.ValidoHasta >= s.fecha::DATE OR v.ValidoHasta IS NULL);


-- ---------------------------------------------------------------------------
-- 7. Validacion. Cada consulta debe devolver 0.
-- ---------------------------------------------------------------------------

\echo '-- facts: filas del DW contra el CSV'
SELECT 'fact_cotizacion' AS tabla, COUNT(*) AS filas FROM CotizacionIndices
UNION ALL SELECT 'fact_fondos_sbs', COUNT(*) FROM fact_fondos_sbs
UNION ALL SELECT 'fact_fondos_competencia', COUNT(*) FROM fact_fondos_competencia
UNION ALL SELECT 'dim_detalle_fondo_clase', COUNT(*) FROM dim_detalle_fondo_clase
UNION ALL SELECT 'DetalleFondosTotal', COUNT(*) FROM DetalleFondosTotal;

\echo '-- huerfanas (todas deben ser 0)'
SELECT
  (SELECT COUNT(*) FROM fact_fondos_sbs s
     WHERE NOT EXISTS (SELECT 1 FROM dim_detalle_fondo_clase v WHERE v.FondoClaseKey = s.FondoClaseKey)) AS sbs_sin_clase,
  (SELECT COUNT(*) FROM fact_fondos_sbs s
     WHERE NOT EXISTS (SELECT 1 FROM dim_time t WHERE t.date_key = s.Fecha)) AS sbs_sin_fecha,
  (SELECT COUNT(*) FROM fact_fondos_competencia s
     WHERE NOT EXISTS (SELECT 1 FROM dim_mes m WHERE m.mes_anio = s.MesAno)) AS comp_sin_mes,
  (SELECT COUNT(*) FROM dim_detalle_fondo_clase c
     WHERE c.FondoKey IS NULL) AS clase_sin_fondo,
  (SELECT COUNT(*) FROM fact_fondos_sbs s JOIN dim_detalle_fondo_clase v USING (FondoClaseKey)
     WHERE s.IdFondoClaseDim <> v.IdFondoClaseDim) AS sbs_key_incoherente,
  (SELECT COUNT(*) FROM fact_fondos_competencia s JOIN dim_detalle_fondo_clase v USING (FondoClaseKey)
     WHERE s.IdFondoClaseDim <> v.IdFondoClaseDim) AS comp_key_incoherente;

\echo '-- grano: fact de cotizacion, una fila por fecha/serie y por mes/serie'
SELECT (SELECT COUNT(*) FROM (SELECT Fecha, IndiceDetalladoKey FROM CotizacionIndices
          WHERE Fecha IS NOT NULL GROUP BY 1,2 HAVING COUNT(*) > 1) t) AS dup_diario,
       (SELECT COUNT(*) FROM (SELECT MesAno, IndiceDetalladoKey FROM CotizacionIndices
          WHERE MesAno IS NOT NULL GROUP BY 1,2 HAVING COUNT(*) > 1) t) AS dup_mensual;

-- TABLA INDICE: Contiene detalles del indice independiente de en que forma este representado (sea moneda, porcentaje, variacion, etc)
CREATE TABLE Indice (
    IndiceKey    INT PRIMARY KEY,
    CodigoIndice VARCHAR(20) NOT NULL UNIQUE,
    NombreIndice VARCHAR(60) NOT NULL,
    Region       VARCHAR(20) NOT NULL,
    TipoIndice   VARCHAR(30) NOT NULL,
    Frecuencia   CHAR(1) NOT NULL CHECK (Frecuencia IN ('D','M'))
);

-- TABLA DETALLE INDICE : Contiene detalles del indice que dependen de como esta representado, ejemplo monda, unidad
CREATE TABLE DetalleIndice (
    IndiceDetalladoKey  INT PRIMARY KEY,
    CodigoIndiceDetalle VARCHAR(60) NOT NULL UNIQUE,
    IndiceKey           INT NOT NULL,
    NombreIndice        VARCHAR(60) NOT NULL,
    Moneda              VARCHAR(10) NOT NULL,
    Unidad              VARCHAR(20) NOT NULL,
    Fuente              VARCHAR(120) NOT NULL,
    FOREIGN KEY (IndiceKey) REFERENCES Indice(IndiceKey)
);

--TABLA DETALLE FONDOS TOTAL: contiene detalles del fondo independiente de la clase. Es un SCD porque va cambiando por ejemplo calificacion, cantidad de clases, etc.
CREATE TABLE DetalleFondosTotal (
    FondoKey           INT PRIMARY KEY,
    IdFondo            VARCHAR(80) NOT NULL,
    ValidoDesde        DATE NOT NULL,
    ValidoHasta        DATE,
    EsActual           BOOLEAN NOT NULL,
    NombreFondo        VARCHAR(80) NOT NULL,
    Region             VARCHAR(20) NOT NULL,
    TipoFondo          VARCHAR(20) NOT NULL,
    TipoRenta          VARCHAR(30) NOT NULL,
    TipoRentaMixta     VARCHAR(30),
    Moneda             CHAR(3) NOT NULL,
    Benchmark          VARCHAR(20),
    ObjetivoKey        INT,
    SociedadGestora    VARCHAR(80) NOT NULL,
    CantidadClases     SMALLINT NOT NULL,
    FOREIGN KEY (ObjetivoKey) REFERENCES DetalleIndice(IndiceDetalladoKey),
    UNIQUE (IdFondo, ValidoDesde)
);

-- TABLA Calendario Mes Año
CREATE TABLE dim_mes (
    mes_anio INTEGER PRIMARY KEY,
    nombre_mes VARCHAR(20) NOT NULL
);


-- TABLA Calendario Diario con atributos adicionales como feriados, dia habil, etc.
CREATE TABLE dim_time (
    date_key     DATE PRIMARY KEY,
    mes_anio     INTEGER NOT NULL,
    anio         SMALLINT NOT NULL,
    trimestre    SMALLINT NOT NULL,
    semana_anio  SMALLINT NOT NULL,
    es_dia_habil BOOLEAN NOT NULL,

    CONSTRAINT fk_time_mes
        FOREIGN KEY (mes_anio)
        REFERENCES dim_mes(mes_anio),

    CONSTRAINT chk_semana_anio
        CHECK (semana_anio BETWEEN 1 AND 53),

    CONSTRAINT chk_trimestre
        CHECK (trimestre BETWEEN 1 AND 4)
);


-- TABLA Cotizacion de los indices, en sus diferentes variantes calculado como porcentaje, variacion, ratio, USD, ARS, etc. Puede ser nivel mensual o diario.
CREATE TABLE CotizacionIndices (
    CotizacionKey      BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    Fecha              DATE,
    MesAno             INTEGER,
    IndiceDetalladoKey INT NOT NULL,
    Valor              NUMERIC(24,16) NOT NULL,
    Frecuencia         CHAR(1) NOT NULL,

    CONSTRAINT chk_xor
        CHECK ((Fecha IS NULL) <> (MesAno IS NULL)),

    FOREIGN KEY (Fecha)             REFERENCES dim_time(date_key),
    FOREIGN KEY (MesAno)            REFERENCES dim_mes(mes_anio),
    FOREIGN KEY (IndiceDetalladoKey) REFERENCES DetalleIndice(IndiceDetalladoKey)
);

-- fact con doble granularidad (mensual para indices de precios y diaria)
CREATE UNIQUE INDEX uq_cot_diario  ON CotizacionIndices (Fecha, IndiceDetalladoKey);
CREATE UNIQUE INDEX uq_cot_mensual ON CotizacionIndices (MesAno, IndiceDetalladoKey);


-- TABLA Detalle Fondo Clase TotalÑ contiene atributos a nivel fondoxclase como honorario, tambien SCD.

CREATE TABLE dim_detalle_fondo_clase (
    FondoClaseKey          INTEGER PRIMARY KEY,
    IdFondoClaseDim        VARCHAR(100) NOT NULL,
    IdFondo                VARCHAR(80)  NOT NULL,
    IdCodigoFondoClase     VARCHAR(20)  NOT NULL,
    NombreFondoClaseOrigen VARCHAR(90)  NOT NULL,
    NombreFondo            VARCHAR(80)  NOT NULL,
    NombreClase            VARCHAR(50)  NOT NULL,
    ValidoDesde            DATE         NOT NULL,
    ValidoHasta            DATE,
    EsActual               BOOLEAN      NOT NULL,
    Calificacion           VARCHAR(20),
    TipoCliente            VARCHAR(20)  NOT NULL,
    ComisionIngreso        NUMERIC(12,4) NOT NULL,
    HonorariosAdmSg        NUMERIC(12,4) NOT NULL,
    HonorariosAdmSd        NUMERIC(12,4) NOT NULL,
    OtrosGastos            NUMERIC(12,4) NOT NULL,
    ComisionRescate        NUMERIC(12,4) NOT NULL,
    Moneda                 CHAR(3)      NOT NULL,
    FondoKey               INT,
    UNIQUE (IdFondoClaseDim, ValidoDesde),
    FOREIGN KEY (FondoKey) REFERENCES DetalleFondosTotal(FondoKey)
);


-- TABLA FONDOS SBS. Cotizacion, VCP, cantidad cuotas, PAtrimonio, flujo a nivel diario de fondos de SBS. Tiene precomputado variaciones diarias, mensuales y anuales
CREATE TABLE fact_fondos_sbs (
    FondoClaseKey   INT NOT NULL,
    IdFondoClaseDim VARCHAR(100) NOT NULL,
    IdFondo         VARCHAR(80) NOT NULL,
    Fecha           DATE NOT NULL,
    VcpActual                  NUMERIC(20,3),
    VcpAnterior                NUMERIC(20,3),
    ReexpresionPesos           NUMERIC(20,3),
    VariacionDiaria            NUMERIC(14,3),
    VariacionMensual           NUMERIC(14,3),
    VariacionAnual             NUMERIC(14,3),
    CantidadCuotaparteActual   NUMERIC(20,4),
    CantidadCuotaparteAnterior NUMERIC(20,4),
    PatrimonioNetoActual       NUMERIC(20,2),
    PatrimonioNetoAnterior     NUMERIC(20,2),
    FlujoNeto                  DOUBLE PRECISION,

    CONSTRAINT pk_fondos_sbs
        PRIMARY KEY (FondoClaseKey, Fecha),

    CONSTRAINT fk_fondos_sbs_clase
        FOREIGN KEY (FondoClaseKey)
        REFERENCES dim_detalle_fondo_clase(FondoClaseKey),

    CONSTRAINT fk_fondos_sbs_fecha
        FOREIGN KEY (Fecha)
        REFERENCES dim_time(date_key)
);


-- TABLA FONDOS MERCADO. Cotizacion, VCP, cantidad cuotas, PAtrimonio, flujo a nivel mensual de fondos mercado. Tiene precomputado variaciones mensuales y anuales


CREATE TABLE fact_fondos_competencia (
    FondoClaseKey   INT NOT NULL,
    IdFondoClaseDim VARCHAR(100) NOT NULL,
    IdFondo         VARCHAR(80) NOT NULL,
    MesAno          INTEGER NOT NULL,

    VcpActual                  NUMERIC(20,3),
    VcpAnterior                NUMERIC(20,3),
    ReexpresionPesos           NUMERIC(20,3),
    VariacionDiaria            NUMERIC(14,3),
    VariacionMensual           NUMERIC(14,3),
    VariacionAnual             NUMERIC(14,3),
    CantidadCuotaparteActual   NUMERIC(20,4),
    CantidadCuotaparteAnterior NUMERIC(20,4),
    PatrimonioNetoActual       NUMERIC(20,2),
    PatrimonioNetoAnterior     NUMERIC(20,2),
    FlujoNeto                  DOUBLE PRECISION,

    CONSTRAINT pk_fondos_competencia
        PRIMARY KEY (FondoClaseKey, MesAno),

    CONSTRAINT fk_competencia_clase
        FOREIGN KEY (FondoClaseKey)
        REFERENCES dim_detalle_fondo_clase(FondoClaseKey),

    CONSTRAINT fk_competencia_mes
        FOREIGN KEY (MesAno)
        REFERENCES dim_mes(mes_anio)
);


-- Indices

CREATE INDEX idx_time_mes
    ON dim_time(mes_anio);

CREATE INDEX idx_fondos_sbs_date
    ON fact_fondos_sbs(Fecha);

CREATE INDEX idx_fondos_sbs_clase
    ON fact_fondos_sbs(FondoClaseKey);

CREATE INDEX idx_competencia_mes
    ON fact_fondos_competencia(MesAno);

CREATE INDEX idx_competencia_clase
    ON fact_fondos_competencia(FondoClaseKey);

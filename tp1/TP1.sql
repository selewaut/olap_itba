-- Pregunta 1.1
-- SELECT measurement.*, name
-- FROM measurement, item


-- Pregunta 1.2
SELECT measurement.*, 
FROM measurement LEFT JOIN item
ON measurement.item_code = item.code
ORDER BY date DESC
---- Pregunta 1.3

SELECT measurement.*, 
FROM measurement LEFT JOIN item
ON measurement.item_code = item.code
ORDER BY date DESC
LIMIT 8


---- Pregunta 1.4
SELECT station.name as station_name, item.name as pollutant, m.date, value
FROM measurement m 
LEFT JOIN station ON m.station_code = station.code
LEFT JOIN item ON m.item_code = item.code
ORDER BY date DESC, pollutant ASC, station_name ASC 

SELECT station.name as station_name, item.name as pollutant, m.date, value
FROM (measurement m 
LEFT JOIN station ON m.station_code = station.code)
LEFT JOIN item ON m.item_code = item.code
ORDER BY date DESC, pollutant ASC, station_name ASC 

---- Pregunta 1.5
SELECT station.name as EstacionNombre, item.name as Contaminante, m.date as Instante, value
FROM measurement m 
LEFT JOIN station ON m.station_code = station.code
LEFT JOIN item ON m.item_code = item.code
ORDER BY date DESC, Contaminante ASC, EstacionNombre ASC



---- Pregunta 2.1
SELECT station.name as station_name, item.name as pollutant, m.date, value
FROM measurement m, station, item
WHERE (m.station_code = station.code) AND (m.item_code = item.code) 
ORDER BY date DESC, pollutant ASC, station_name ASC 

---- Pregunta 2.2
SELECT station.name as EstacionNombre, item.name as Contaminante, m.date as Instante, item.very_bad, value
FROM measurement m 
LEFT JOIN station ON m.station_code = station.code
LEFT JOIN item ON m.item_code = item.code
WHERE m.value > item.very_bad
ORDER BY date DESC, Contaminante ASC, EstacionNombre ASC

-- recordar que el where va antes del groupby
--- Pregunta 2.3
SELECT station.name as EstacionNombre, item.name as Contaminante, m.date as Instante,item.bad,item.very_bad,value
FROM measurement m 
LEFT JOIN station ON m.station_code = station.code
LEFT JOIN item ON m.item_code = item.code
WHERE m.value >= item.bad AND m.value < item.very_bad
ORDER BY date DESC, Contaminante ASC, EstacionNombre ASC

---- Pregunta 2.4
SELECT name FROM item
WHERE uom <> 'ppm'

---- Pregunta 2.5
SELECT name FROM ITEM
WHERE FALSE
	OR good IS NULL
	OR normal is NULL
	OR bad is NULL
	OR very_bad is NULL

---- Pregunta 2.6

SELECT item.name 
FROM item
LEFT JOIN measurement m ON item.code = m.item_code
WHERE m.item_code IS NULL

---- Pregunta 2.7
-- a
SELECT DISTINCT item.code, item.name 
FROM item
INNER JOIN measurement m ON item.code = m.item_code

-- b
SELECT item.code, item.name
FROM item
WHERE item.code in (SELECT m.item_code FROM measurement m)



---- Pregunta 2.8
SELECT DISTINCT m.item_code, item.name
FROM measurement m
LEFT JOIN item ON m.item_code = item.code
WHERE value <= item.good
ORDER BY m.item_code;


---- Pregunta 2.9
SELECT item.name, value as medido, item.good as umbralExcelente
FROM measurement m LEFT JOIN item on m.item_code = item.code
WHERE value <= item.good
ORDER BY m.item_code

---- Pregunta 2.10
SELECT s.name
FROM station s
WHERE NOT EXISTS (\
--- Nos quedamos aquellas estaciones que tienen obersvaciones malas o peores.
  SELECT 1
  FROM measurement m
  JOIN item i ON m.item_code = i.code
  WHERE m.station_code = s.code
    AND m.value >= i.bad
);

---- Pregunta 3.1
SELECT max(value) from measurement


SELECT m.value 
from measurement m
ORDER BY value DESC LIMIT 1


---- Pregunta 3.2
SELECT COUNT(DISTINCT m.item_code)
FROM measurement m
WHERE m.value is not NULL

---- Pregunta 3.3
SELECT COUNT(m.value)
FROM measurement m
LEFT JOIN station s ON m.station_code = s.code
GROUP BY m.station_code

---- Pregunta 3.4
SELECT s.name, COUNT(DISTINCT m.item_code)
FROM measurement m
LEFT JOIN station s ON m.station_code = s.code
GROUP BY s.name

---- Pregunta 3.5
SELECT name, promedio FROM
(SELECT m.item_code, AVG(m.value) as promedio FROM measurement m GROUP BY m.item_code HAVING AVG(m.value) > 10) avgs
LEFT JOIN item on avgs.item_code = item.code


---- Pregunta 3.6
SELECT s.name, m.date, COUNT(m.value) as qty
FROM measurement m
LEFT JOIN station s ON s.code = m.station_code
GROUP BY s.name, m.date
HAVING COUNT(m.value) > 1


---- Pregujnta 3.7
SELECT s.name, extract(YEAR FROM m.date) as date_part, COUNT(m.value) as qty
FROM measurement m
LEFT JOIN station s ON s.code = m.station_code
GROUP BY s.name, extract(YEAR FROM m.date)
HAVING COUNT(m.value) > 1

SELECT station.name, DATE, count( item_code) AS qty
FROM station , measurement
WHERE station.code= station_code
GROUP BY station.code, station.name, extract(year from date)
HAVING COUNT( item_code) > 1
--- THis query fails because of the groupby not matching the columns selected + aggregated.
--- Incosistencia entre select date y groupby extract year.ACCESS

---- Pregunta 3.8
SELECT item.name, COALESCE(MIN(m.value), 0), COALESCE(MAX(m.value), 0)
FROM measurement m
RIGHT JOIN item ON m.item_code = item.code
GROUP BY item.name
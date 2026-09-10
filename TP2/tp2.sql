--- Pregunta 1
select distinct p.productname 
from sales s
left join product p on s.productkey = p.productkey
left join customer c  on s.customerkey = c.customerkey
left join city c2 on c.citykey = c2.citykey
where c2.cityname = 'Madrid'

--- Pregunta 2. Cantidad total pedida por producto.
select p.productname, sum(s.quantity ) as QTY
from sales s
left join product p on s.productkey = p.productkey 
group by p.productname 
order by qty desc

--- Pregunta 3. Nombre de los clientes que ordenaron al menos 10productos.
--- Pregunta 3.
--- Cantidad productos por cliente
select c.companyname , prods_purch
from customer c
join (
select s.customerkey, count(distinct s.productkey) as prods_purch
from sales s 
group by s.customerkey
having count(distinct s.productkey) > 10
)
as prods_per_cust
on c.customerkey  = prods_per_cust.customerkey
order by prods_purch desc

--- Pregunta 4.
---  Listar los pares (cliente 1,cliente 2) tales que cliente 1 ordenó al menos un producto pedido  también por cliente 2. 

select distinct s1.customerkey , c1.companyname  as Cliente1,s2.customerkey , c2.companyname 
from sales s1
left join customer c1 on c1.customerkey  = s1.customerkey 
join sales s2
left join customer c2 on c2.customerkey  = s2.customerkey 
on  s1.productkey  = s2.productkey 
where s1.customerkey  < s2.customerkey 



--- Pregunta 5
---Listar los nombres de los productos no pedidos por ningún cliente. 
select *
from product p 
where not exists
(select 1 from sales s
where  s.productkey = p.productkey )


--- Pregunta 6
--- Listar los nombres de los empleados que no vendieron ningún producto de la categoría “Beverages”. 
-- Me fijo los que no estan en la query que me trae todas las ventas de beverages con exists hago el matcheo por employee para fijarme si estan o no.
select e.firstname , e.lastname 
from employee e 
where not exists (
select * from sales s
inner join product p on s.productkey = p.productkey 
inner join category c on p.categorykey   = c.categorykey 
where c.categoryname = 'Beverages'
and e.employeekey = s.employeekey )

--- Pregunta 7
--- Monto total vendido, agrupados por nombre de empleado y nombre de producto. 
select e.employeekey , e.firstname , e.lastname , SUM(s.salesamount ) as total_amount
from sales s 
join product p on s.productkey = p.productkey
join employee e  on s.employeekey = e.employeekey
group by e.employeekey, e.firstname , e.lastname
order by total_amount desc


--- Pregunta 8
--- Listar los clientes que pidieron todos los productos. 

-- Alternativa 1, que el dsitinct count = al distinct del catalogo.

SELECT c.customerkey, c.companyname
FROM customer c
JOIN sales s ON s.customerkey = c.customerkey
GROUP BY c.customerkey, c.companyname
HAVING COUNT(DISTINCT s.productkey) = (SELECT COUNT(*) FROM product);


--- Pregunta 9.
--- Listar los productos vendidos por todos los empleados.

SELECT p.productkey, p.productname
FROM product p
JOIN sales s ON s.productkey = p.productkey
GROUP BY p.productkey, p.productname
HAVING COUNT(DISTINCT s.employeekey) = (SELECT COUNT(*) FROM employee)
ORDER BY p.productkey;


---Alternativa 2 — doble NOT EXISTS:
SELECT p.productname
FROM product p
WHERE NOT EXISTS (
    SELECT 1 FROM employee e
    WHERE NOT EXISTS (
        SELECT 1 FROM sales s
        WHERE s.productkey = p.productkey
          AND s.employeekey = e.employeekey
    )
);
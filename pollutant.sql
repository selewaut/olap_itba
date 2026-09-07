CREATE TABLE station
(
    code integer NOT NULL,
    name VARCHAR(20) NOT NULL,
    address VARCHAR(100) NOT NULL,
    lat double precision NOT NULL,
    lon double precision NOT NULL,
    PRIMARY KEY (code),
    UNIQUE (lat, lon)
);

CREATE TABLE item
(
    code integer NOT NULL,
    name VARCHAR(5) NOT NULL,
    uom VARCHAR(15) NOT NULL,
    good FLOAT ,
    normal FLOAT ,
    bad FLOAT ,
    very_bad FLOAT ,
    PRIMARY KEY (code),
    UNIQUE (name)
);



CREATE TABLE measurement
(
    date timestamp NOT NULL,
    station_code integer NOT NULL,
    item_code integer NOT NULL,
    value float NOT NULL,
    PRIMARY KEY (date, station_code, item_code),
    FOREIGN KEY (item_code)
        REFERENCES item ON DELETE CASCADE,
    FOREIGN KEY (station_code)
        REFERENCES station ON DELETE CASCADE
);



insert into station values (101,'Jongno-gu','19 Jong-ro 35ga-gil, Jongno-gu, Seoul, Republic of Korea',37.572016399999995,127.00500749999999);
insert into station values (102,'Jung-gu','15, Deoksugung-gil, Jung-gu, Seoul, Republic of Korea',37.564262899999996,126.97467569999999);
insert into station values (103,'Yongsan-gu','136, Hannam-daero, Yongsan-gu, Seoul, Republic of Korea',37.540032700000005,127.00485);

insert into item values (1,'SO2','ppm',0.02,0.05,0.15,1.0);
insert into item values (3,'NO2','ppm',0.03,0.06,0.2,2.0);
insert into item values (5,'CO','ppm',2.0,9.0,15.0,50.0);
insert into item values (6,'O3','ppm',0.03,0.09,0.15,0.5);
insert into item values (8,'PM10','Microgram/m3',30.0,80.0,150.0,600.0);
insert into item values (9,'PM2.5','Microgram/m3',15.0,35.0,75.0,500.0);
insert into item values (11,'dummy','ppm',null,null,null, 1.2);
insert into item values (12,'bis','ppm',null, 0.3, 0.4, 0.5);

set datestyle to ymd;

insert into measurement values ('2017-01-01 00:00',101,1,0.04);
insert into measurement values ('2017-01-01 00:00',101,3,0.59000000000000004);
insert into measurement values ('2017-01-01 00:00',101,5,2.5);
insert into measurement values ('2017-01-01 00:00',101,6,0.2);
insert into measurement values ('2017-01-01 00:00',101,8,93.0);
insert into measurement values ('2017-01-01 00:00',101,9,7.0);
insert into measurement values ('2017-01-01 00:00',102,1,0.6);
insert into measurement values ('2017-01-01 00:00',102,3,0.068);
insert into measurement values ('2017-01-01 00:00',102,5,1.3);
insert into measurement values ('2017-01-01 00:00',102,6,0.002);
insert into measurement values ('2017-01-01 00:00',102,8,77.0);
insert into measurement values ('2017-01-01 00:00',102,9,63.0);
insert into measurement values ('2017-01-01 00:00',103,1,0.005);
insert into measurement values ('2017-01-01 00:00',103,3,0.039);
insert into measurement values ('2017-01-01 00:00',103,5,1.4);
insert into measurement values ('2017-01-01 00:00',103,6,0.002);
insert into measurement values ('2017-01-01 00:00',103,8,70.0);
insert into measurement values ('2017-01-01 00:00',103,9,68.0);
insert into measurement values ('2017-01-01 01:00',101,1,0.004);
insert into measurement values ('2017-01-01 01:00',101,3,0.57999999999999996);
insert into measurement values ('2017-01-01 01:00',101,5,1.2);
insert into measurement values ('2017-01-01 01:00',101,6,0.002);
insert into measurement values ('2017-01-01 01:00',101,8,71.0);
insert into measurement values ('2017-01-01 01:00',101,9,59.0);
insert into measurement values ('2017-01-01 01:00',102,1,0.006);
insert into measurement values ('2017-01-01 01:00',102,3,0.066);
insert into measurement values ('2017-01-01 01:00',102,5,1.4);
insert into measurement values ('2017-01-01 01:00',102,6,0.002);
insert into measurement values ('2017-01-01 01:00',102,8,76.0);
insert into measurement values ('2017-01-01 01:00',102,9,63.0);
insert into measurement values ('2017-01-01 01:00',103,1,0.004);
insert into measurement values ('2017-01-01 01:00',103,3,0.038);
insert into measurement values ('2017-01-01 01:00',103,5,1.4);
insert into measurement values ('2017-01-01 01:00',103,6,0.002);
insert into measurement values ('2017-01-01 01:00',103,8,73.0);
insert into measurement values ('2017-01-01 02:00',101,1,0.004);
insert into measurement values ('2017-01-01 02:00',101,3,0.055999999999999994);
insert into measurement values ('2017-01-01 02:00',101,5,1.2);
insert into measurement values ('2017-01-01 02:00',101,6,0.002);
insert into measurement values ('2017-01-01 02:00',101,8,70.0);
insert into measurement values ('2017-01-01 02:00',101,9,59.0);
insert into measurement values ('2017-01-01 02:00',102,1,0.005);
insert into measurement values ('2017-01-01 02:00',102,3,0.063);
insert into measurement values ('2017-01-01 02:00',102,5,1.2);
insert into measurement values ('2017-01-01 02:00',102,6,0.002);
insert into measurement values ('2017-01-01 02:00',102,8,73.0);
insert into measurement values ('2017-01-01 02:00',102,9,57.0);
insert into measurement values ('2017-01-01 02:00',103,1,0.005);
insert into measurement values ('2017-01-01 02:00',103,3,0.037000000000000005);
insert into measurement values ('2017-01-01 02:00',103,5,1.4);
insert into measurement values ('2017-01-01 02:00',103,6,0.002);
insert into measurement values ('2017-01-01 02:00',103,8,67.0);
insert into measurement values ('2017-01-01 02:00',103,9,65.0);

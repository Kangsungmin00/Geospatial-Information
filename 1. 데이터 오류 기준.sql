-- PostGIS 확장 설치 및 활성화
CREATE EXTENSION IF NOT EXISTS postgis;

UPDATE public.project 
SET geom_Text = ST_AsText(ST_SetSRID(ST_GeomFromWKB(wkb_geometry), 5186));
ALTER TABLE public.project ADD COLUMN jimok text;

UPDATE public.project
SET jimok = RIGHT(a5, 1);

SELECT * FROM public.project
ORDER BY ogc_fid;

-- 오류 추출
DROP TABLE IF EXISTS land_error_light;

CREATE TABLE land_error_light (
  gid integer,
  geom geometry,
  오류코드 text,
  오류종류 text
);
-- G002: 짧은선 오류
INSERT INTO land_error_light (gid, geom, 오류코드, 오류종류)
SELECT gid, geom, 'G002', '짧은선 오류'
FROM land_clean
WHERE ST_Length(geom) < 0.01;

-- G003: 자가교차 오류
INSERT INTO land_error_light (gid, geom, 오류코드, 오류종류)
SELECT gid, geom, 'G003', '자가교차 오류'
FROM land_clean
WHERE NOT ST_IsValid(geom);

-- G006: 멀티파트 오류
INSERT INTO land_error_light (gid, geom, 오류코드, 오류종류)
SELECT gid, geom, 'G006', '멀티파트 오류'
FROM land_clean
WHERE ST_NumGeometries(geom) > 1;

CREATE INDEX idx_land_error_light_geom ON land_error_light USING GIST (geom);

CREATE INDEX IF NOT EXISTS idx_land_clean_geom
ON land_clean
USING GIST (geom);

-- 오버랩 후보 추출 → 교차 계산 → 면적 필터링
DROP TABLE IF EXISTS land_overlap_errors;

CREATE TABLE land_overlap_errors AS
SELECT 
    a.gid AS gid1,
    b.gid AS gid2,
    ST_Intersection(a.geom, b.geom) AS geom,
    'G007' AS 오류코드,
    '오버랩 오류' AS 오류종류
FROM land_clean a
JOIN land_clean b
  ON a.gid < b.gid  -- 자기 자신 비교 제거 + 중복 제거
  AND a.geom && b.geom  -- bbox 조건 (인덱스 활용)
WHERE ST_Intersects(a.geom, b.geom)
  AND ST_Area(ST_Intersection(a.geom, b.geom)) > 0.00;

DROP TABLE IF EXISTS land_error_all;

CREATE TABLE land_error_all AS
SELECT * FROM land_error_light
UNION ALL
SELECT gid1 AS gid, geom, 오류코드, 오류종류
FROM land_overlap_errors;

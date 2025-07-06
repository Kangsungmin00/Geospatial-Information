# Geospatial-Information
## 📦 데이터 적재 및 추출 자동화 스크립트 (`0_데이터_적재_및_추출.cmd`)

공간정보 데이터를 PostGIS로 적재하고 다시 Shapefile로 추출하는 과정을 자동화한 **Windows CMD 스크립트**입니다.  
`ogr2ogr`와 `pgsql2shp` 명령어를 이용해 SHP ↔ DB 간 변환을 일괄 처리할 수 있습니다.

---

### 🛠 주요 기능

- Shapefile → PostgreSQL/PostGIS 테이블로 업로드
- PostGIS 테이블 → Shapefile로 추출 (에러검출 결과 등 내보내기 용도)

---

### 🗂️ 파일 경로
0_데이터_적재_및_추출.cmd

---

### ⚙️ 사용법

1. 파일 내 변수 부분을 실제 경로/이름으로 수정하세요:

```cmd
# 예시 - 데이터베이스에 shp 파일 적재
ogr2ogr -f "PostgreSQL" PG:"host=localhost user=postgres dbname=project password=asdf" "D:\data\farm_clean.shp" -nln farm_clean -nlt PROMOTE_TO_MULTI -lco GEOMETRY_NAME=geom -oo ENCODING=CP949 -a_srs EPSG:5186 -overwrite -progress

# 예시 - PostgreSQL 데이터를 Shapefile로 내보내기
pgsql2shp -f "D:\output\farm_error_result" -h localhost -u postgres -P asdf --encoding=CP949 project "SELECT * FROM public.farm_error_result"


2. QGIS가 설치된 디렉토리(ogr2ogr, pgsql2shp 포함)에서 실행하세요:
cd "C:\Program Files\QGIS 3.40.7\bin"
0_데이터_적재_및_추출.cmd

📌 참고 사항
- 인코딩 문제 방지를 위해 -oo ENCODING=CP949, --encoding=CP949를 사용합니다.
- 좌표계는 EPSG:5186(중부원점, Korea Central Belt 2010)을 기본값으로 설정하였으며, 필요시 변경 가능합니다.
- .cmd 스크립트는 한글 경로 및 파일명 사용 시 따옴표(") 처리에 주의하세요.
- QGIS 설치 경로가 다를 경우 cd 경로를 수정해야 합니다.


---

### 🔁 그 외 사항

- 공간 오류 검출, 후처리 자동화는 PostGIS 쿼리와 Python(QGIS API 또는 psycopg2)로 직접 실행 가능합니다.
- 예를 들어, 다음과 같은 방식으로 구현되어 있습니다:

```sql
-- 예시: 오버랩 오류 검출
SELECT a.gid, b.gid
FROM farm_clean a, farm_clean b
WHERE a.gid < b.gid
  AND ST_Overlaps(a.geom, b.geom)
  AND ST_Area(ST_Intersection(a.geom, b.geom)) > 0.01;

# 예시: PyQGIS로 shapefile 자동 저장
processing.run("native:savefeatures", {
    'INPUT': layer,
    'OUTPUT': output_path
})

- 오류 유형 분류, 자동 shapefile 생성, 통계 CSV 저장 등도 모두 Python + PostGIS 환경에서 구현 가능합니다.
- 복잡한 GUI 없이 배치 자동화가 필요한 경우 .cmd 또는 .py 파일로 작업 가능합니다.

# 초기 데이터베이스에 shp 파일 적재
cd C:\Program Files\QGIS 3.40.7\bin
psql -U postgres -d 데이터베이스명

# OSGeo4w Shell에서 실행
ogr2ogr -f "PostgreSQL" PG:"host=localhost user=postgres dbname=데이터베이스명 password=비밀번호" "파일 경로.shp" -nln 테이블명 -nlt PROMOTE_TO_MULTI -lco GEOMETRY_NAME=geom -oo ENCODING=CP949 -a_srs EPSG:5186 -overwrite -progress


# shp 파일로 데이터 내보내기
pgsql2shp -f "산출물 파일경로" -h localhost -u postgres -P asdf --encoding=CP949 테이블명 "SELECT * FROM public.테이블명"
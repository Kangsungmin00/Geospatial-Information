from qgis.core import (
    QgsProcessing,
    QgsProcessingAlgorithm,
    QgsProcessingParameterFile,
    QgsProcessingParameterFolderDestination,
    QgsProcessingParameterFileDestination,
    QgsVectorLayer,
    QgsProject,
    QgsProcessingException,
    QgsCategorizedSymbolRenderer,
    QgsRendererCategory,
    QgsSymbol,
    QgsField
)
from PyQt5.QtGui import QColor
from PyQt5.QtCore import QVariant
import processing
import os
import csv
from datetime import datetime

class FullGeometryQualityProcessor(QgsProcessingAlgorithm):
    INPUT_FOLDER = 'INPUT_FOLDER'
    OUTPUT_FOLDER = 'OUTPUT_FOLDER'

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterFile(
            self.INPUT_FOLDER,
            '원본 Shapefile 폴더',
            behavior=QgsProcessingParameterFile.Folder
        ))
        self.addParameter(QgsProcessingParameterFolderDestination(
            self.OUTPUT_FOLDER,
            '결과 저장 폴더'
        ))

    def processAlgorithm(self, parameters, context, feedback):
        start_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        input_folder = self.parameterAsString(parameters, self.INPUT_FOLDER, context)
        output_folder = self.parameterAsString(parameters, self.OUTPUT_FOLDER, context)

        snapped_dir = os.path.join(output_folder, 'snapped')
        errors_dir = os.path.join(output_folder, 'errors')
        os.makedirs(snapped_dir, exist_ok=True)
        os.makedirs(errors_dir, exist_ok=True)

        shapefiles = [
            os.path.join(root, f)
            for root, _, files in os.walk(input_folder)
            for f in files if f.lower().endswith('.shp')
        ]
        if not shapefiles:
            raise QgsProcessingException('Shapefile이 없습니다.')

        tagged_layers = []
        error_counts = {}
        total_features = 0

        for shp in shapefiles:
            name = os.path.splitext(os.path.basename(shp))[0]
            feedback.pushInfo(f'▶ 처리 시작: {name}')
            layer = QgsVectorLayer(shp, name, 'ogr')
            if not layer.isValid():
                feedback.pushWarning(f'❌ 레이어 로드 실패: {name}')
                continue
            total_features += layer.featureCount()

            # Step 1: Clean + Snap
            single = processing.run("native:multiparttosingleparts", {'INPUT': layer, 'OUTPUT': 'memory:single'}, context=context)['OUTPUT']
            fixed = processing.run("native:fixgeometries", {'INPUT': single, 'OUTPUT': 'memory:fixed'}, context=context)['OUTPUT']
            clean = processing.run("native:removeduplicatevertices", {'INPUT': fixed, 'OUTPUT': 'memory:clean'}, context=context)['OUTPUT']
            snapped = processing.run("native:snapgeometries", {
                'INPUT': clean,
                'REFERENCE_LAYER': clean,
                'TOLERANCE': 0.001,
                'BEHAVIOR': 0,
                'OUTPUT': 'memory:snapped'
            }, context=context)['OUTPUT']

            snapped_path = os.path.join(snapped_dir, f'{name}_snapped.shp')
            processing.run("native:savefeatures", {'INPUT': snapped, 'OUTPUT': snapped_path}, context=context)

            # Step 2: Add ID + 오버랩 검출
            with_id = processing.run("native:addautoincrementalfield", {
                'INPUT': snapped, 'FIELD_NAME': 'INPUT_ID', 'START': 1, 'OUTPUT': 'memory:with_id'
            }, context=context)['OUTPUT']
            inter = processing.run("native:intersection", {
                'INPUT': with_id, 'OVERLAY': with_id, 'OUTPUT': 'memory:intersection'
            }, context=context)['OUTPUT']
            expr = '"INPUT_ID" < "INPUT_ID_2" AND area($geometry) > 0.0001'
            overlap = processing.run("native:extractbyexpression", {
                'INPUT': inter, 'EXPRESSION': expr, 'OUTPUT': 'memory:overlap'
            }, context=context)['OUTPUT']
            cnt = overlap.featureCount()
            if cnt > 0:
                feedback.pushInfo(f'▶ {name} 오버랩 {cnt}건')
                prov = overlap.dataProvider()
                if '오류종류' not in [f.name() for f in prov.fields()]:
                    prov.addAttributes([QgsField('오류종류', QVariant.String)])
                    overlap.updateFields()
                idx = overlap.fields().indexOf('오류종류')
                overlap.startEditing()
                for f in overlap.getFeatures():
                    overlap.changeAttributeValue(f.id(), idx, '오버랩')
                overlap.commitChanges()
                tagged_layers.append(overlap)
                error_counts[('G001', '오버랩')] = error_counts.get(('G001', '오버랩'), 0) + cnt

            # Step 3: 추가 오류 검출
            checks = [
                ('length($geometry) < 0.01', '짧은선 오류', 'G002'),
                ('NOT is_valid($geometry)', '자가교차 오류', 'G003'),
                ('num_geometries($geometry) > 1', '멀티파트 오류', 'G006'),
            ]
            for expression, label, code in checks:
                sel = processing.run('native:extractbyexpression', {
                    'INPUT': layer, 'EXPRESSION': expression, 'OUTPUT': 'memory:sel'
                }, context=context)['OUTPUT']
                ecnt = sel.featureCount()
                if ecnt > 0:
                    prov = sel.dataProvider()
                    if '오류종류' not in [f.name() for f in prov.fields()]:
                        prov.addAttributes([QgsField('오류종류', QVariant.String)])
                        sel.updateFields()
                    idx = sel.fields().indexOf('오류종류')
                    sel.startEditing()
                    for feat in sel.getFeatures():
                        sel.changeAttributeValue(feat.id(), idx, label)
                    sel.commitChanges()
                    tagged_layers.append(sel)
                    error_counts[(code, label)] = error_counts.get((code, label), 0) + ecnt

        # 병합
        if not tagged_layers:
            feedback.pushInfo('✅ 오류 없음')
            return {}

        merged = processing.run("native:mergevectorlayers", {
            'LAYERS': tagged_layers, 'OUTPUT': 'memory:merged'
        }, context=context)['OUTPUT']
        out_shp = os.path.join(errors_dir, 'merged_errors.shp')
        processing.run("native:savefeatures", {
            'INPUT': merged, 'OUTPUT': out_shp
        }, context=context)
        layer_final = QgsVectorLayer(out_shp, '오류통합', 'ogr')
        QgsProject.instance().addMapLayer(layer_final)

        # 심볼 지정
        categories = []
        color_map = {
            '오버랩': 'brown',
            '짧은선 오류': 'green',
            '자가교차 오류': 'orange',
            '멀티파트 오류': 'red'
        }
        for lbl, color in color_map.items():
            sym = QgsSymbol.defaultSymbol(layer_final.geometryType())
            sym.setColor(QColor(color))
            categories.append(QgsRendererCategory(lbl, sym, lbl))
        renderer = QgsCategorizedSymbolRenderer('오류종류', categories)
        layer_final.setRenderer(renderer)
        layer_final.triggerRepaint()

        # CSV 출력
        end_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        csv_path = os.path.join(output_folder, 'errors_summary.csv')
        total_errors = sum(error_counts.values())
        with open(csv_path, 'w', newline='', encoding='cp949') as f:
            w = csv.writer(f)
            w.writerow(['오류코드', '검수개수', '전체오류수', '유형별개수', '비율', '시작시간', '종료시간'])
            for (code, label), cnt in error_counts.items():
                ratio = f"{cnt / total_errors:.1%}" if total_errors else "0%"
                w.writerow([code, total_features, total_errors, cnt, ratio, start_time, end_time])
        feedback.pushInfo(f'📄 오류 통계 저장: {csv_path}')

        return {}

    def name(self): return 'full_geometry_quality_check'
    def displayName(self): return '공간 정합성 전면 검사 및 통계'
    def group(self): return 'FarmMap 검사'
    def groupId(self): return 'farmmap_tools'
    def createInstance(self): return FullGeometryQualityProcessor()

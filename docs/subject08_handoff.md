# 교과 8 Handoff — 조각김치 이물검출 FINAL Dataset

> 생성: 2026-10-08 11:02 · `python tools/build_handoff.py`

## 1. 한눈에 보기

| 항목 | 내용 |
|---|---|
| FINAL 이미지 | 900장 (`data/final/images/`) |
| FINAL YOLO TXT | 900개 (`data/final/labels/`) |
| 전체 BBox | 4569개 |
| Empty Label (배경 이미지) | 0장 — 빈 TXT, 이물 없음으로 학습 |
| 최종 QA | 최종 판정: QA 완료 — 교과 8 학습 데이터로 사용 가능 |
| 이미지 원본 | 저장소에 올리지 않음 (데이터 보안) — 팀 공유 위치에서 전달 |

## 2. 폴더 구조

```
data/final/
├── images/      <이름>.jpg
├── labels/      <이름>.txt   (이미지와 이름 1:1)
└── final_list.csv   각 파일을 어느 검수 결과에서 가져왔는지
```

## 3. YOLO Label 형식

```
class_id x_center y_center width height
```

- 한 줄 = 객체 1개, 좌표는 이미지 크기 대비 0~1 비율 (소수 6자리)
- 박스가 없는 이미지는 **빈 TXT** (삭제하지 말 것 — 오검출을 줄이는 배경 데이터)
- 이미지 EXIF 회전이 반영된 방향 기준 좌표

## 4. Class 정보

| ID | 이름 | 사용 | FINAL BBox 수 |
|---:|---|:---:|---:|
| 0 | 나뭇잎·종이류 | ○ | 715 |
| 1 | 플라스틱류·돌·금속류 | ○ | 1905 |
| 2 | 나뭇가지류 | ○ | 928 |
| 3 | 벌레류 | ○ | 377 |
| 4 | 고무장갑 (사용 안 함) | ✕ | 0 |
| 5 | 병해·갈변 | ○ | 393 |
| 6 | 파·고추 | ○ | 251 |

- Class 4(고무장갑)는 사용하지 않지만 **ID 순서를 유지하기 위해 번호는 비워 둠** → 학습 설정에서도 nc=7 로 두는 것을 권장
  (ID 를 당겨서 바꾸면 기존 TXT 와 번호가 어긋남)
- 판단 기준: `docs/class_guide.md` · BBox 기준: `docs/bbox_guide.md` · 프로그램 설정: `configs/classes.yaml`

## 5. 원본 출처 / 기존 Split

| source_dataset | original_split | FINAL 이미지 |
|---|---|---:|
| 이물검출_학습데이터1 | train | 500 |
| 이물검출_학습데이터2 | train | 220 |
| 이물검출_학습데이터2 | validation | 180 |

- 이미지별 출처·Split·작업 이력: `manifests/dataset_manifest.csv`
- Train / Validation / Test 를 다시 나눌 때는 **같은 촬영 묶음(파일명 날짜·시각이 연속된 이미지)이 양쪽에 섞이지 않게** 나누는 것을 권장 (비슷한 장면이 섞이면 검증 점수가 부풀려짐)

## 6. 학습 설정 예시 (dataset.yaml)

```yaml
path: data/final_split      # Train/Val 로 나눈 뒤의 위치
train: images/train
val: images/val
nc: 7
names:
  0: 나뭇잎·종이류
  1: 플라스틱류·돌·금속류
  2: 나뭇가지류
  3: 벌레류
  4: 고무장갑 (사용 안 함)
  5: 병해·갈변
  6: 파·고추
```

## 7. 관련 문서

| 문서 | 위치 |
|---|---|
| QA 결과 | `reports/qa_summary.md` |
| 프로그램 시험 결과 | `reports/test_report.md` |
| Dataset Manifest | `manifests/dataset_manifest.csv` |
| Class 기준서 | `docs/class_guide.md` |
| BBox 기준서 | `docs/bbox_guide.md` |
| 팀 작업 기준 | `docs/project_baseline.md` |

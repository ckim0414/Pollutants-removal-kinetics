# Kinetic Lab v0.1

오염물질 제거 batch 실험용 Streamlit 앱. 로컬 PC에서 실행하며 업로드 데이터는 이 앱에서 외부 서비스로 전송하지 않습니다.

## 시작 (Windows / macOS)
Python 3.11 또는 3.12를 설치하고 ZIP을 풀어 해당 폴더에서 터미널을 여세요.

```bash
python -m venv .venv
```
Windows:
```bat
.venv\Scripts\activate
python -m pip install -r requirements.txt
python -m streamlit run app.py
```
macOS / Linux:
```bash
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m streamlit run app.py
```
브라우저가 열리면 예제 데이터가 자동 표시됩니다. 종료는 터미널에서 Ctrl+C.
Windows에서는 설치 시 Python을 PATH에 추가하거나 python 대신 py를 사용하세요.

## 처음 테스트할 순서
1. 예제 데이터에서 기본 PFO 그래프와 k 결과를 확인.
2. 조건별 x, label, color(HEX), marker를 수정해 전체 그래프 연동 확인.
3. 평균곡선 피팅 / 반복별 피팅을 바꾸고 SE, CI, SD의 차이를 확인.
4. 조건–k 회귀를 Linear로 선택.
5. Δ농도 mol/L 변환을 켜고 입력 단위와 분자량을 지정.
6. Figure Builder에서 panel 선택 순서와 열 수를 지정하고 TIFF/PDF 저장.
7. 실제 데이터 CSV/Excel을 업로드하고 열 역할 지정.

## 데이터 입력
example_long.csv 참고. 한 행은 condition + replicate + time의 고유 조합입니다.
- condition: 실험조건 이름. 그래프 사이에서 같은 색과 마커를 공유.
- replicate: 독립 batch 반복실험 ID. 기기 반복주입을 독립 batch로 취급하지 마세요.
- time: 0을 포함하는 실제 반응시간. 시간 원점 이동은 수행하지 않습니다.
- pollutant: 농도. 외부표준 환산과 희석배수 보정은 미리 수행.
- oxidant: 선택. 같은 행의 pollutant와 같은 시간/동일 batch에 대응해야 함. 측정하지 않은 값은 빈칸으로 두세요.
- rpm 등: 선택 숫자 metadata. 조건당 하나의 값이어야 합니다.

필수 열의 결측·비수치·음수·중복은 오류로 표시합니다. 검출한계 미만 값을 자동으로 0으로 바꾸지 않습니다.
Wide에서는 시간열과 여러 농도열을 선택하고 각 농도열에 condition과 replicate를 매핑합니다. 산화제를 같이 다루려면 Long을 권장합니다.

## 피팅과 불확실성
- 비가중 최소제곱, k≥0, A≥0. PFO는 원농도 또는 C/C0 공간에서 비선형 피팅하며 ln 변환을 하지 않음.
- PFO: C=A exp(-kt). A는 기본적으로 자유 파라미터. C/C0일 때 A=1 고정 선택 가능.
- Second-order: C=A/(1+A k t). 흡착 용량 기반 PSO 식이 아닌 농도 감소 2차식.
- Zero-order: C=A-k t. 음수 예측을 잘라내지 않으므로 적용 시간 구간을 확인.
- 평균 시간곡선: 시간별 산술평균을 한 번 피팅. CI/SE는 그 피팅의 공분산 기반 값이며 독립 반복실험의 변동 SD가 아님.
- 반복별: 각 batch를 따로 피팅한 k의 평균, SD, SD/sqrt(n)의 SE, t(n-1) 95% CI. 1개 반복은 반복 CI/SD가 정의되지 않음.
- CI는 근사 대칭 구간. 하한이 음수가 되어도 임의로 0으로 잘라내지 않음. 경계 k≈0, 비선형성이 강한 자료는 profile likelihood/bootstrap과 결과가 다를 수 있음.
- C0로 정규화한 자료는 공통 기준값의 오차를 공유. 현재 피팅은 이 오차 상관을 모델링하지 않음.
- 실패한 반복은 경고와 함께 제외. 성공한 반복 수를 반드시 확인.
- R2는 1-SSE/SST이며 비선형 모델 비교만을 위한 충분한 근거는 아님. 잔차도 함께 확인.
- CI에서 SD를 자동 역산하지 않음. 앞서 대화의 CI→SD 변환 제안은 SE와 SD를 구분해야 정확함.

## 조건 회귀 / 산화제 이용
조건–k는 조건별 k 점에 대한 비가중 Linear/Quadratic OLS입니다. k 추정 오차를 가중치로 반영하지 않습니다.
Δ농도는 각 반복의 t=0을 기준으로 계산하고 시간별 평균으로 Δoxidant–Δpollutant 회귀합니다. 기본은 절편 자유, 원점 통과는 사용자 선택입니다.
회귀표 x^1 값이 slope입니다. mol/L 변환 시 단위는 mol pollutant/mol oxidant. 원농도 사용 시 입력 단위 비율.
산화제는 실제 보고 농도에 대응하는 분자량을 입력해야 하며 PMS 혼합염 제품 전체 분자량을 활성 PMS 분자량으로 혼동하지 마세요.
Δ의 공유 C0, x축 측정오차, 시간점의 비독립성은 현재 OLS CI에 반영되지 않습니다. 탐색적 지표로 해석하세요.

## Figure / 기록
Muted, Pastel, Colorblind 팔레트. 개별 HEX와 Matplotlib marker(o,s,^,D,v,P,X 등) 수정 가능.
폰트, 축/눈금/legend 크기, 선, marker, panel 크기, 축 범위와 간격, panel 순서 조정.
Arial/Times New Roman은 PC에 설치되어 있어야 하며 없으면 대체 폰트가 사용됩니다.
TIFF/PNG 300/600/1200 dpi, PDF/SVG vector. 지나치게 밝은 pastel은 작은 점/인쇄에서 구분을 확인하세요.
분석 기록 ZIP에는 canonical 입력, k 결과, 개별 피팅, 잔차, Δ농도, 설정 JSON을 저장합니다. 설정 JSON 재업로드 복원은 이 버전에서 지원하지 않습니다.
웹 세션 재시작 전 필요한 결과를 다운로드하세요.

## 포함 기능과 향후 확장
이 버전은 연구실 시험용입니다. custom equation, weighted fit, bootstrap/profile CI, ODR, 외부표준 농도 환산, project 설정 자동 복원은 포함하지 않습니다.
실제 연구 데이터 한 세트를 Prism과 같은 식/A 고정/시간범위/가중치로 비교한 후 연구실 배포를 권장합니다.

## 검증
```bash
python -m unittest test_analysis -v
```
알려진 PFO k 복원, 선형 slope, C0 pairing, 중복/기준점 누락 오류를 검증합니다.
Streamlit AppTest로 기본 흐름과 반복별 피팅/조건 Linear 회귀/mol 변환/Second-order UI 흐름을 확인했습니다.

## 참고
SciPy curve_fit: https://docs.scipy.org/doc/scipy/reference/generated/scipy.optimize.curve_fit.html
Streamlit: https://docs.streamlit.io/

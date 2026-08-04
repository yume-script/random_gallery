# 랜덤 갤러리 (random_gallery)

Google Apps Script 웹앱을 프록시로 사용해 Pixabay, Pixiv, 또는 직접 운영하는
개인서버에서 이미지 주소 목록을 가져와, BookOasis 대시보드에 랜덤 갤러리로
보여주는 메타데이터 플러그인입니다.

- **버전**: 1.2.0
- **플러그인 ID**: `random_gallery`
- **표시명**: 랜덤 갤러리

## 주요 기능

- Apps Script 웹앱(`?url=사이트주소`)을 통해 이미지 목록(JSON)을 가져옵니다.
- 갤러리 사이트를 드롭다운에서 선택합니다: **Pixabay/ 개인서버**.
- 카테고리(검색어)를 등록해두면 카테고리별로 이미지를 모아서 보여줍니다.
  등록하지 않으면 검색어 없이 전체 이미지를 "전체" 카테고리 하나로 보여줍니다.
- 두 곳에 노출됩니다.
  - **플러그인 데스크** 내부의 단독 전체화면 탭 (표준 대시보드 위젯 카드 형식)
  - **카테고리 내비게이션**의 "랜덤 갤러리" 메뉴 (자체 제작한 풀페이지 UI:
    큰 이미지 그리드 + 카테고리 필터 버튼 + 새로고침 버튼)
- 문제 발생 시 원인을 바로 확인할 수 있도록 요청 URL/HTTP 상태코드/원본
  응답/오류 메시지를 서버 로그와(옵션) 응답 데이터에 함께 남깁니다.

## 설치 방법

1. 이 폴더 전체(`random_gallery/`)를 BookOasis의
   `plugins/metadata/` 아래에 복사합니다.
   ```
   plugins/metadata/random_gallery/
     ├── __init__.py
     ├── random_gallery.py
     ├── VERSION
     ├── index.html
     ├── script.js
     └── style.css
   ```
2. BookOasis(컨테이너/프로세스)를 재시작합니다.
3. 환경설정 > 플러그인 설정에서 "랜덤 갤러리"를 활성화하고 아래 설정값을
   입력합니다.

## 설정 항목

| 키 | 설명 | 기본값 |
|---|---|---|
| `APPS_SCRIPT_URL` | Apps Script 배포(웹앱) URL | (기본 제공 URL 있음) |
| `GALLERY_SOURCE` | 갤러리 사이트 선택 (`pixabay` / `pixiv` / `custom`) | `pixabay` |
| `CUSTOM_SITE_URL` | `GALLERY_SOURCE`가 `custom`(개인서버)일 때 사용할 실제 주소. `https://` 없이 입력 | (비어있음) |
| `CATEGORIES_JSON` | 카테고리 목록 JSON. 예: `[{"label":"자연","keyword":"nature"}]` | `[]` (없음) |
| `IMAGES_PER_CATEGORY` | 카테고리당 가져올 이미지 수 | `20` |
| `REQUEST_TIMEOUT_SEC` | Apps Script 요청 타임아웃(초) | `10` |
| `GALLERY_ENABLED` | 갤러리 활성화 여부 (끄면 두 화면 모두 "비활성화됨" 표시) | `True` |
| `DEBUG_MODE` | 요청/응답 진단 정보를 결과에 포함할지 여부 | `True` |

### 노출 위치를 개별로 켜고 끄는 기능에 대해

"플러그인 데스크 탭"과 "카테고리 메뉴"를 각각 따로 켜고 끄는 기능을
시도했으나, 코어가 플러그인 목록을 만들 때 `dashboard_widget`/
`category_tab`을 **인스턴스가 아닌 클래스 자체에서 읽는 것으로 보여**,
설정값에 따라 동적으로 값을 바꾸는 방식(`@property`)을 쓰면 플러그인이
목록에서 통째로 사라지는 문제가 있었습니다. 그래서 두 값은 다시 고정된
dict로 되돌렸고, 대신 `GALLERY_ENABLED`로 두 화면을 한 번에 켜고 끄는
방식만 지원합니다. 두 화면 모두 동일한 데이터 엔드포인트
(`/api/media/dashboard/widgets/random_gallery/data`)를 호출하기 때문에,
서버 쪽에서 어느 화면에서 온 요청인지 구분할 방법도 현재는 없습니다.

### 실제 요청 형태

```
APPS_SCRIPT_URL?url=<선택된 사이트 주소>[/images/search/<카테고리 키워드>/]
```

`APPS_SCRIPT_URL`과 `GALLERY_SOURCE`(또는 `CUSTOM_SITE_URL`) 두 값이 합쳐져야
Apps Script로부터 정상적인 JSON 응답을 받을 수 있습니다.

Apps Script가 반환해야 하는 정상 응답 형식:
```json
{"source": "pixabay", "images": ["https://.../g....jpg", "..."]}
```

### 카테고리 설정 예시

```json
[
  {"label": "자연", "keyword": "nature"},
  {"label": "동물", "keyword": "animals"}
]
```

> `/images/search/<키워드>/` 경로 규칙은 Pixabay 기준입니다. Pixiv나
> 개인서버처럼 URL 구조가 다른 사이트를 선택한 경우, 카테고리(검색어)
> 필터링이 기대와 다르게 동작할 수 있습니다.

## 문제 해결 (트러블슈팅)

1. **플러그인이 환경설정 > 플러그인 설정 목록에 아예 안 보임**
   - 서버 로그에서 `[MetadataFactory] Plugin load failed (random_gallery): ...`
     같은 줄이 있는지 확인하세요. 보통 `__init__.py`가 찾는 파일이 실제로
     없거나(예: `random_gallery.py` 누락), 폴더가 한 겹 더 씌워진 경우입니다.
   - `dashboard_widget`/`category_tab`은 반드시 고정된 `dict`여야 합니다.
     `@property`처럼 동적으로 계산하는 방식은 코어가 인스턴스 없이 클래스
     자체에서 값을 읽는 것으로 보여, 플러그인이 목록에서 통째로 사라지는
     원인이 될 수 있습니다(직접 겪은 회귀 버그입니다).
2. **이미지가 하나도 안 보임**
   - 서버 로그에서 `[random_gallery]` 태그로 시작하는 로그를 확인하세요.
     요청 URL, HTTP 상태코드, 응답 원문 앞부분이 그대로 남습니다.
   - `DEBUG_MODE`가 켜져 있으면 대시보드 데이터 응답(JSON)의 `error`,
     `debug` 필드에도 동일한 진단 정보가 담깁니다. 브라우저 개발자도구
     Network 탭에서 이 위젯의 데이터 요청을 열어 확인할 수 있습니다.
3. **Apps Script가 `{"error": "..."}` 를 반환함**
   - Apps Script 배포 설정의 "액세스 권한"이 "모든 사용자(Anyone)"로
     되어 있는지 확인하세요.
   - `GALLERY_SOURCE`/`CUSTOM_SITE_URL` 값에 `https://`가 섞여 있어도
     플러그인이 자동으로 제거하긴 하지만, Apps Script 쪽에서 기대하는
     주소 형식(스킴 없는 도메인)인지 다시 확인하세요.
4. **카테고리 버튼이 안 보임**
   - `CATEGORIES_JSON`에 카테고리를 2개 이상 등록해야 필터 버튼이
     나타납니다. 1개 이하(또는 미설정)면 "전체" 하나로만 동작합니다.

## 파일 구성 및 계약 요약

- `random_gallery.py`
  - `search()`, `apply()`: 필수 계약이지만 이 플러그인은 이미지 갤러리
    전용이라 빈 구현만 제공합니다.
  - `dashboard_widget` + `get_dashboard_data()`: BookOasis 가이드 문서
    "5. 대시보드 위젯 및 플러그인 데스크 계약"을 그대로 따릅니다.
    공개 메서드는 `get_dashboard_data()` 하나만 유지하고, 실제 구현은
    private helper `_fetch_items()`로 분리했습니다.
  - `category_tab`: 가이드 문서에는 없지만 `stats_dashboard` 플러그인의
    실제 소스로 확인된 계약입니다. 좌측/상단 "카테고리" 내비게이션에
    별도 메뉴 항목을 추가합니다.
- `index.html` / `script.js` / `style.css`
  - `category_tab` 클릭 시 로드되는 완전 커스텀 풀페이지 UI입니다.
    코어의 정형화된 도서 카드 렌더러를 거치지 않으므로 이미지 그리드
    크기, 카테고리 필터 버튼 등을 자유롭게 구성했습니다.
- `VERSION`
  - 플러그인 버전 정보 (`{"plugin version": "1.2.0"}`).

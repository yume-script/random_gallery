# -*- coding: utf-8 -*-
"""
Random Gallery Plugin (id: random_gallery)
--------------------------------------------
Google Apps Script 웹앱(예: ?url=pixabay.com)이 반환하는 이미지 주소 목록을
카테고리별로 가져와서 대시보드에 랜덤 갤러리로 보여주는 BookOasis 메타데이터
플러그인입니다. (표시명: 랜덤 갤러리)

가이드 문서 "5. 대시보드 위젯 및 플러그인 데스크 계약"만 그대로 따릅니다.
  - `dashboard_widget` (dict): title/subtitle/provider/icon/limit/
    all_desk_tab(선택)/supported_types(선택)
  - `get_dashboard_data(self, db_type, limit=10)`:
      성공 {'success': True, 'items': [...]}
      실패 {'success': False, 'error': '...'}
  - all_desk_tab=True  → 공통 데스크 카드가 아닌 단독 전체화면 탭으로 렌더링
    (기본값 False면 [공통 데스크] 카드 그리드에 노출, 드래그 정렬 가능)
  - 권장사항에 따라 외부 공개 메서드는 get_dashboard_data()만 유지하고,
    실제 구현은 private helper `_fetch_items()`로 분리했습니다.

주의: 코어의 대시보드 렌더러는 각 아이템을 도서 카드 형식으로 그리며,
실제로 사용하는 필드는 cover / title / author / publisher / link 입니다.
그래서 카테고리 정보는 별도 UI 없이 title에 표시합니다
(예: "자연 #1").

설정에서 아래 3개 갤러리 사이트 중 하나를 드롭다운으로 선택합니다
(모두 동일하게 Apps Script 프록시를 통해 가져옵니다: ?url=사이트주소).
  - Pixabay (pixabay.com)
  - Pixiv (pixiv.net)
  - 개인서버 (직접 입력한 주소)

실제 요청: "APPS_SCRIPT_URL?url=선택된사이트주소[/images/search/키워드/]"

Apps Script 응답 형식(확인됨):
  {"source": "pixabay", "images": ["https://.../g....jpg", ...]}

카테고리는 기본 제공 목록이 없으며, 관리자가 CATEGORIES_JSON에서 직접
등록합니다. 등록하지 않으면 검색어 없이 전체 이미지를 "전체" 카테고리
하나로 보여줍니다.

dashboard_widget/category_tab은 코어가 인스턴스가 아닌 클래스 자체에서
읽을 가능성이 있어 고정된 dict로 유지합니다(과거 @property로 만들었다가
플러그인이 목록에서 통째로 사라지는 문제가 있었습니다). 대신 설정의
GALLERY_ENABLED 체크박스를 끄면, 두 화면(플러그인 데스크 탭 / 카테고리
메뉴) 모두 동일한 데이터 엔드포인트를 쓰기 때문에 구분 없이 함께
"비활성화됨" 상태로 표시됩니다. 두 화면을 개별적으로 켜고 끄는 기능은
현재 코어 구조상 안전하게 구현하기 어렵습니다.
"""

import json
import logging
import random
import urllib.error
import urllib.parse
import urllib.request

from plugins.metadata.base import BaseMetadataProvider

logger = logging.getLogger(__name__)

# 관리자가 설정에서 값을 비워두었을 때 사용할 기본값들
DEFAULT_APPS_SCRIPT_URL = (
    "https://script.google.com/macros/s/AKfycbwRjVoo9NYwDIMHkct-OO2sbZ8Z0p9Sqi-WJRhUIwDI5Za4Ikfb9xZmyuPvpnLsAi2FrQ/exec"
)

# 갤러리 사이트 주소: Apps Script의 ?url= 파라미터로 그대로 전달됩니다.
# (Apps Script 배포 URL) + (갤러리 사이트 주소) 두 값이 합쳐져야 JSON 응답을 받을 수 있습니다.
DEFAULT_GALLERY_SITE_URL = "pixabay.com"

# 드롭다운으로 선택 가능한 갤러리 사이트 목록.
# "custom"(개인서버)만 관리자가 CUSTOM_SITE_URL에 실제 주소를 직접 입력합니다.
GALLERY_SOURCE_OPTIONS = [
    {"value": "pixabay", "label": "Pixabay (pixabay.com)"},
    {"value": "pixiv", "label": "Pixiv (pixiv.net)"},
    {"value": "custom", "label": "개인서버 (직접 입력)"},
]
GALLERY_SOURCE_DOMAIN_MAP = {
    "pixabay": "pixabay.com",
    "pixiv": "pixiv.net",
}

# 기본 제공 카테고리는 없습니다. 관리자가 플러그인 설정 화면(CATEGORIES_JSON)에서
# 직접 등록해야 합니다. 예: [{"label": "자연", "keyword": "nature"}]
DEFAULT_CATEGORIES = []

# 카테고리가 하나도 등록되지 않았을 때 사용할 대체 카테고리 (검색어 없이 전체 이미지)
FALLBACK_CATEGORY = {"label": "전체", "keyword": ""}


class RandomGalleryMetadataProvider(BaseMetadataProvider):
    id = "random_gallery"
    name = "랜덤 갤러리"
    is_searchable = False

    config_schema = [
        {
            "key": "APPS_SCRIPT_URL",
            "label": "Apps Script 배포 URL",
            "type": "text",
            "required": True,
            "default": DEFAULT_APPS_SCRIPT_URL,
        },
        {
            "key": "GALLERY_SOURCE",
            "label": "갤러리 사이트 선택",
            "type": "select",
            "options": GALLERY_SOURCE_OPTIONS,
            "required": True,
            "default": "pixabay",
        },
        {
            "key": "CUSTOM_SITE_URL",
            "label": "개인서버 주소 (갤러리 사이트 선택이 '개인서버'일 때만 사용, https:// 없이 입력)",
            "type": "text",
            "required": False,
            "default": "",
        },
        {
            "key": "CATEGORIES_JSON",
            "label": (
                "카테고리 목록 (JSON, 기본 비어있음: "
                "[{\"label\":표시명, \"keyword\":검색어}, ...])"
            ),
            "type": "text",
            "required": False,
            "default": json.dumps(DEFAULT_CATEGORIES, ensure_ascii=False),
        },
        {
            "key": "IMAGES_PER_CATEGORY",
            "label": "카테고리당 이미지 수",
            "type": "number",
            "required": False,
            "default": 20,
        },
        {
            "key": "REQUEST_TIMEOUT_SEC",
            "label": "요청 타임아웃(초)",
            "type": "number",
            "required": False,
            "default": 10,
        },
        {
            "key": "GALLERY_ENABLED",
            "label": "갤러리 활성화 (끄면 플러그인 데스크 탭/카테고리 메뉴 둘 다 '비활성화됨' 표시)",
            "type": "checkbox",
            "required": False,
            "default": True,
        },
        {
            "key": "DEBUG_MODE",
            "label": "디버그 정보 표시 (요청 URL/상태코드/원본 응답을 결과에 포함)",
            "type": "checkbox",
            "required": False,
            "default": True,
        },
    ]

    # 자동 업데이트를 사용하려면 raw_base_url을 실제 리포지토리 경로로 수정하세요.
    update_manifest = {
        "enabled": False,
        "provider": "github-raw",
        "raw_base_url": (
            "https://raw.githubusercontent.com/<org>/<repo>/<branch>/"
            "plugins/metadata/random_gallery"
        ),
        "files": ["random_gallery.py", "__init__.py", "VERSION"],
        "version_file": "VERSION",
        "version_key": "plugin version",
        "show_sample_update_button": False,
    }

    # 가이드 5번 섹션 예시와 동일한 형태의 dashboard_widget 계약.
    # all_desk_tab=True → [공통 데스크] 카드가 아닌 단독 전체화면 탭으로 렌더링.
    #
    # 주의: 한때 이 값을 @property로 바꿔 DISPLAY_MODE 설정에 따라 None을
    # 반환하도록 했었는데, 코어가 플러그인 목록을 만들 때 인스턴스가 아닌
    # 클래스 자체에서 이 값을 읽는 것으로 보여 플러그인이 통째로 목록에서
    # 사라지는 문제가 있었습니다. 그래서 다시 고정된 dict로 되돌렸습니다.
    #dashboard_widget = {
    #    "title": "랜덤 갤러리",
    #    "subtitle": "카테고리별 랜덤 이미지",
    #    "provider": "Apps Script Gallery Proxy",
    #    "icon": "fa-solid fa-images",
    #    "limit": 30,
    #    "all_desk_tab": True,
    #}

    # 코어 좌측/상단 "카테고리" 내비게이션에 별도 메뉴로 노출 + index.html/
    # script.js/style.css로 완전 커스텀 풀페이지 렌더링 (가이드 문서에는 없지만
    # stats_dashboard 실제 소스로 확인된 계약: title/icon/order)
    category_tab = {
        "title": "랜덤 갤러리",
        "icon": "fa-solid fa-images",
        "order": 91,
    }

    # ------------------------------------------------------------------
    # 필수 계약 (이 플러그인은 검색/적용 대상이 아니므로 빈 구현만 제공)
    # ------------------------------------------------------------------
    def search(self, db_type, query):
        return {"success": True, "items": []}

    def apply(self, db_type, book_id, item_data):
        return False, "이 플러그인은 대시보드 전용(이미지 갤러리)입니다."

    # ------------------------------------------------------------------
    # 대시보드 공통 계약 (가이드 권장사항: 공개 메서드는 이것만 유지)
    # ------------------------------------------------------------------
    def get_dashboard_data(self, db_type, limit=10):
        return self._fetch_items(db_type, limit=limit)

    # ------------------------------------------------------------------
    # 설정값 헬퍼
    # ------------------------------------------------------------------
    def _get_config(self, db_type):
        return self.get_plugin_config(db_type, default={}) or {}

    def _is_enabled(self, cfg):
        val = cfg.get("GALLERY_ENABLED")
        if val is None:
            return True
        return bool(val) and str(val).lower() not in ("false", "0", "")

    def _get_apps_script_url(self, cfg):
        return (cfg.get("APPS_SCRIPT_URL") or DEFAULT_APPS_SCRIPT_URL).strip()

    def _get_gallery_site_url(self, cfg):
        source = (cfg.get("GALLERY_SOURCE") or "pixabay").strip()
        if source == "custom":
            val = (cfg.get("CUSTOM_SITE_URL") or "").strip()
            if not val:
                logger.warning(
                    "[random_gallery] '개인서버'를 선택했지만 CUSTOM_SITE_URL이 "
                    "비어 있어 기본값(%s)을 사용합니다.", DEFAULT_GALLERY_SITE_URL
                )
                val = DEFAULT_GALLERY_SITE_URL
        else:
            val = GALLERY_SOURCE_DOMAIN_MAP.get(source, DEFAULT_GALLERY_SITE_URL)

        # Apps Script는 스킴 없는 도메인(예: pixabay.com)을 기대하므로,
        # 관리자가 실수로 https://를 붙여도 자동으로 제거합니다.
        for prefix in ("https://", "http://"):
            if val.lower().startswith(prefix):
                val = val[len(prefix):]
                break
        return val.strip("/")

    def _get_categories(self, cfg):
        """관리자가 등록한 카테고리 목록을 반환합니다. 기본 제공 카테고리는 없습니다."""
        raw = cfg.get("CATEGORIES_JSON")
        if not raw:
            return []
        try:
            parsed = json.loads(raw)
            categories = [
                {"label": str(c.get("label") or c.get("keyword")), "keyword": str(c.get("keyword", ""))}
                for c in parsed
                if isinstance(c, dict) and (c.get("keyword") or c.get("label"))
            ]
            return categories
        except (ValueError, TypeError):
            logger.warning("[random_gallery] CATEGORIES_JSON 파싱 실패, 카테고리 없음으로 처리")
            return []

    def _get_images_per_category(self, cfg):
        try:
            return max(1, int(cfg.get("IMAGES_PER_CATEGORY") or 20))
        except (ValueError, TypeError):
            return 20

    def _get_timeout(self, cfg):
        try:
            return max(3, int(cfg.get("REQUEST_TIMEOUT_SEC") or 10))
        except (ValueError, TypeError):
            return 10

    def _get_debug_mode(self, cfg):
        val = cfg.get("DEBUG_MODE")
        if val is None:
            return True
        return bool(val) and str(val).lower() not in ("false", "0", "")

    # ------------------------------------------------------------------
    # Apps Script 호출 (외부 패키지 의존성 없이 표준 라이브러리 urllib만 사용)
    # ------------------------------------------------------------------
    def _fetch_images_for_keyword(self, apps_script_url, gallery_site_url, keyword, timeout):
        """Apps Script 웹앱을 호출해서 특정 카테고리(검색어)의 images 배열을 추출.

        응답 형식(정상): {"source": "...", "images": ["https://...", ...]}

        반환값: (images, diag) 튜플. diag에는 문제 파악에 필요한 요청 URL/
        상태코드/원본 응답 일부/오류 메시지가 담깁니다. warning으로 로그를
        남기므로 서버 로그 레벨이 WARNING 이상이기만 해도 콘솔/로그 파일에서
        그대로 확인할 수 있습니다.
        """
        # 참고: "/images/search/<키워드>/" 경로는 Pixabay 기준입니다.
        # Pixiv나 개인서버처럼 URL 구조가 다른 사이트를 선택한 경우,
        # 카테고리(검색어) 필터링이 기대와 다르게 동작할 수 있습니다.
        target_url = (
            gallery_site_url
            if not keyword
            else "%s/images/search/%s/" % (gallery_site_url, keyword)
        )
        query = urllib.parse.urlencode({"url": target_url})
        full_url = "%s?%s" % (apps_script_url, query)

        diag = {
            "keyword": keyword,
            "requested_url": full_url,
            "http_status": None,
            "raw_response_snippet": None,
            "error": None,
        }

        if not apps_script_url:
            diag["error"] = "APPS_SCRIPT_URL 설정값이 비어 있습니다."
            logger.warning("[random_gallery] %s", diag["error"])
            return [], diag

        logger.warning("[random_gallery] 요청 시작: %s (timeout=%ss)", full_url, timeout)

        raw_text = None
        try:
            req = urllib.request.Request(
                full_url,
                headers={"User-Agent": "BookOasis-RandomGallery/1.0"},
            )
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                diag["http_status"] = resp.getcode()
                raw_text = resp.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as exc:
            diag["http_status"] = exc.code
            try:
                raw_text = exc.read().decode("utf-8", errors="replace")
            except Exception:
                raw_text = ""
            diag["raw_response_snippet"] = raw_text[:500]
            diag["error"] = "HTTP 오류: status=%s" % exc.code
            logger.warning(
                "[random_gallery] %s, body(앞 500자)=%s",
                diag["error"], diag["raw_response_snippet"],
            )
            return [], diag
        except urllib.error.URLError as exc:
            diag["error"] = "네트워크 오류(연결/타임아웃 등): %s" % exc.reason
            logger.warning("[random_gallery] %s", diag["error"])
            return [], diag
        except Exception as exc:  # 방어적 처리
            diag["error"] = "요청 실패: %s" % exc
            logger.warning("[random_gallery] %s", diag["error"])
            return [], diag

        diag["raw_response_snippet"] = raw_text[:500] if raw_text else ""
        logger.warning(
            "[random_gallery] 응답 수신: status=%s, body(앞 500자)=%s",
            diag["http_status"], diag["raw_response_snippet"],
        )

        try:
            data = json.loads(raw_text)
        except Exception as exc:
            diag["error"] = "JSON 파싱 실패: %s" % exc
            logger.warning("[random_gallery] %s", diag["error"])
            return [], diag

        if not isinstance(data, dict):
            diag["error"] = "응답이 JSON 객체가 아닙니다: %r" % (data,)
            logger.warning("[random_gallery] %s", diag["error"])
            return [], diag

        images = data.get("images")
        if not isinstance(images, list):
            diag["error"] = (
                "응답 JSON에 'images' 배열이 없습니다. 실제 키: %s"
                % list(data.keys())
            )
            logger.warning("[random_gallery] %s", diag["error"])
            return [], diag

        valid_images = [img for img in images if isinstance(img, str) and img.startswith("http")]
        logger.warning(
            "[random_gallery] '%s' 카테고리: 이미지 %d개 수신 (유효 URL %d개)",
            keyword or "(전체)", len(images), len(valid_images),
        )
        if not valid_images:
            diag["error"] = "images 배열은 있지만 유효한 http(s) URL이 하나도 없습니다."
            logger.warning("[random_gallery] %s", diag["error"])

        return valid_images, diag

    # ------------------------------------------------------------------
    # 내부 구현 (private helper) — 가이드 권장사항에 따라 get_dashboard_data()는
    # 이 헬퍼만 호출합니다.
    # ------------------------------------------------------------------
    def _fetch_items(self, db_type, limit=10):
        cfg = self._get_config(db_type)

        if not self._is_enabled(cfg):
            return {"success": False, "error": "갤러리가 비활성화되어 있습니다."}

        apps_script_url = self._get_apps_script_url(cfg)
        gallery_site_url = self._get_gallery_site_url(cfg)
        timeout = self._get_timeout(cfg)
        per_category = self._get_images_per_category(cfg)
        debug_mode = self._get_debug_mode(cfg)

        categories = self._get_categories(cfg)
        if not categories:
            categories = [FALLBACK_CATEGORY]

        items = []
        diagnostics = []
        try:
            for cat in categories:
                label = cat["label"]
                keyword = cat["keyword"]
                images, diag = self._fetch_images_for_keyword(
                    apps_script_url, gallery_site_url, keyword, timeout
                )
                diagnostics.append(diag)
                if not images:
                    continue

                random.shuffle(images)
                for idx, img_url in enumerate(images[:per_category]):
                    # 코어 대시보드 렌더러가 실제로 읽는 필드: cover / title /
                    # author / publisher / link. 카테고리 정보는 별도 UI가
                    # 없으므로 title에 함께 표시합니다.
                    display_title = (
                        "%s #%d" % (label, idx + 1) if label != FALLBACK_CATEGORY["label"]
                        else "이미지 #%d" % (idx + 1)
                    )
                    items.append(
                        {
                            "id": "%s-%d" % (keyword or "all", idx),
                            "category": label,
                            "category_key": keyword,
                            "cover": img_url,
                            "title": display_title,
                            "author": gallery_site_url,
                            "publisher": "",
                            "link": img_url,
                            # 다른 렌더러 대응용으로 흔히 쓰이는 키도 함께 남겨둡니다.
                            "image": img_url,
                            "image_url": img_url,
                            "url": img_url,
                            "source": gallery_site_url,
                        }
                    )
        except Exception as exc:  # 위젯 전체가 죽지 않도록 최종 방어
            logger.exception("[random_gallery] _fetch_items 처리 중 예외")
            return {"success": False, "error": "예상치 못한 오류: %s" % exc}

        if not items:
            error_msg = "이미지를 가져오지 못했습니다."
            if diagnostics and diagnostics[-1].get("error"):
                error_msg = diagnostics[-1]["error"]
            result = {"success": False, "error": error_msg}
            if debug_mode:
                result["debug"] = diagnostics
            return result

        random.shuffle(items)
        effective_limit = max(limit or 0, per_category * max(len(categories), 1))
        if effective_limit:
            items = items[:effective_limit]

        result = {
            "success": True,
            "items": items,
            # 커스텀 category_tab UI(script.js)에서 카테고리 버튼을 그릴 때 참고
            "categories": [c["label"] for c in categories],
        }
        if debug_mode:
            result["debug"] = diagnostics
        return result

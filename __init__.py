# -*- coding: utf-8 -*-
"""random_gallery 플러그인 패키지 진입점.

코어가 random_gallery.py를 직접 읽어 클래스를 찾는 방식이라면 이 파일은
비어 있어도 무방하지만, `from plugins.metadata.random_gallery import ...`
형태의 패키지 임포트에도 대응할 수 있도록 클래스를 재노출해 둡니다.
"""

from .random_gallery import RandomGalleryMetadataProvider

__all__ = ["RandomGalleryMetadataProvider"]

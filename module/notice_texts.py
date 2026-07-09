# SPDX-License-Identifier: LicenseRef-PolyForm-Noncommercial-1.0.0

# AnkiVoice notice and patch-note text resources.
#
# This module keeps the long legal notice text outside AnkiVoice.py.
# It also selects the notice variant automatically:
#
# Display, paging, input, and acceptance UI logic should remain in AnkiVoice.py.
# AnkiVoice.py should use LEGAL_NOTICE_VERSION when checking stored acceptance.

from pathlib import Path

LEGAL_NOTICE_LANGUAGE_ORDER = ["ko", "en"]

LEGAL_NOTICE_LANGUAGE_LABELS = {
    "ko": "한국어",
    "en": "English",
}

LEGAL_NOTICE_ACCEPT_TEXTS = {
    "ko": "동의합니다",
    "en": "accept",
}

LEGAL_NOTICE_VARIANT_CORE = "core"
LEGAL_NOTICE_VARIANT_MP3 = "mp3"

LEGAL_NOTICE_BASE_VERSION = "1.5.0-ko-en-official-notice-r2"
LEGAL_NOTICE_CORE_VERSION = f"{LEGAL_NOTICE_BASE_VERSION}-{LEGAL_NOTICE_VARIANT_CORE}"
LEGAL_NOTICE_MP3_VERSION = f"{LEGAL_NOTICE_BASE_VERSION}-{LEGAL_NOTICE_VARIANT_MP3}"


def _module_dir() -> Path:
    return Path(__file__).resolve().parent


def detect_legal_notice_variant() -> str:
    # Return the legal notice variant for the installed module set.
    mp3_module_path = _module_dir() / "mp3_collector.py"
    if mp3_module_path.is_file():
        return LEGAL_NOTICE_VARIANT_MP3
    return LEGAL_NOTICE_VARIANT_CORE


def _notice_lines(text: str) -> list[str]:
    return text.strip("\n").splitlines()


def _join_notice_text(base_text: str, addendum_text: str | None = None) -> str:
    if addendum_text:
        return base_text.rstrip() + "\n\n__PAGE_BREAK__\n\n" + addendum_text.strip()
    return base_text


LEGAL_NOTICE_KO_CORE_TEXT = '''
개요

본 약관은 AnkiVoice의 이용 조건, 책임 범위, 제3자 자료의 권리 관계 및 이용자의 준수 사항을 고지하기 위한 문서입니다.

AnkiVoice는 이용자의 로컬 환경에서 Anki 학습 자료 및 TXT, CSV, APKG 등 학습용 파일을 변환·추출·분류하기 위한 비공식 학습 보조 프로그램입니다.

AnkiVoice는 Anki, AnkiWeb 또는 그 밖의 제3자 서비스가 제공하거나 승인한 공식 프로그램이 아닙니다.

이용자가 본 약관을 확인한 후 AnkiVoice를 계속 사용하는 경우, 해당 약관의 내용에 동의한 것으로 간주됩니다.

__PAGE_BREAK__

1. 프로그램의 성격

AnkiVoice는 이용자 단말의 로컬 환경에서 실행되는 비공식 학습 보조 도구입니다.

본 프로그램은 Anki .apkg 파일, Anki에서 내보낸 TXT 파일, 일반 TXT 파일 및 CSV 파일을 처리하여 단어 목록, 학습 텍스트, 변환용 데이터 또는 분류용 데이터를 생성할 수 있습니다.

본 프로그램은 학습 플랫폼, 파일 변환 서비스, 데이터베이스 서비스 또는 공식 Anki 관련 서비스를 대체하지 않습니다.

제3자 서비스의 제공 여부, 접근 가능성, 자료 형식, 응답 구조 및 향후 호환성은 보장되지 않습니다.

__PAGE_BREAK__

2. 이용 목적

AnkiVoice는 개인적·비상업적 언어 학습을 보조하기 위한 목적으로 배포됩니다.

이용자는 본 프로그램을 본인이 보유하거나 적법하게 사용할 수 있는 학습 자료의 정리, 변환, 추출, 분류 및 개인 학습용 데이터 관리에 한하여 사용할 수 있습니다.

본 프로그램을 통해 생성되는 CSV, TXT, 로그, 설정 파일 및 기타 작업 결과물은 이용자의 책임 아래 보관·관리되어야 합니다.

이용자는 프로그램 사용 전에 관련 법령, 제3자 서비스 약관, 라이선스 조건 및 사용 자료의 권리 관계를 직접 확인하여야 합니다.

__PAGE_BREAK__

3. 라이선스

AnkiVoice의 원본 소스코드 및 프로젝트 고유 문서는 PolyForm Noncommercial License 1.0.0에 따라 배포됩니다.

이용자는 해당 라이선스의 조건에 따라 AnkiVoice의 원본 소스코드 및 프로젝트 고유 문서를 비상업적 목적에 한하여 사용, 복사, 수정 및 재배포할 수 있습니다.

상업적 이용, 판매, 유료 제공, 수익 창출 목적의 서비스 편입 또는 영리 목적의 업무상 사용은 저작권자의 별도 서면 허가 없이는 허용되지 않습니다.

본 라이선스는 AnkiVoice의 원본 코드와 프로젝트 고유 문서에 한정되며, 제3자 자료 또는 외부 서비스에서 제공되는 콘텐츠에는 적용되지 않습니다.

__PAGE_BREAK__

4. 제3자 자료 및 권리 관계

AnkiVoice의 라이선스는 제3자가 보유한 저작권, 상표권, 데이터베이스권, 서비스 운영권 또는 기타 권리를 포함하지 않습니다.

다음 자료는 AnkiVoice 라이선스의 적용 대상이 아닙니다.

- Anki, AnkiWeb 및 기타 제3자의 상표, 로고, 서비스명
- 이용자가 제공한 APKG, TXT, CSV 및 개인 학습 자료
- 외부 웹사이트, API, 라이브러리, 데이터베이스 및 관련 자료
- 제3자가 보유한 저작물, 메타데이터, 서비스 응답, 미디어 자산 및 기타 보호 대상 자료

본 프로그램의 사용으로 위 자료에 관한 권리가 이용자에게 이전되거나 부여되지 않습니다.

__PAGE_BREAK__

5. 금지 행위

이용자는 AnkiVoice를 불법적 목적 또는 권한 없는 목적으로 사용하여서는 안 됩니다.

다음 행위는 금지됩니다.

- 저작권 또는 기타 지식재산권 침해
- 제3자 자료의 무단 복제, 재배포, 판매 또는 유료 제공
- 접근 제한, 인증 절차 또는 기술적 보호조치의 우회
- 외부 자료의 무단 데이터베이스화, 크롤링 또는 상업적 활용
- 서비스 약관, 라이선스 조건, API 정책 또는 관련 법령 위반
- 그 밖에 제3자 권리 또는 서비스 운영을 침해할 수 있는 행위

__PAGE_BREAK__

6. 이용자의 책임

프로그램 설치, 실행, 설정, 입력 파일 선택, 변환 결과의 사용 및 외부 자료 접근에 관한 책임은 이용자에게 있습니다.

이용자는 대한민국 법령, 거주지 또는 서비스 이용 지역의 법령, Anki 및 AnkiWeb의 약관, 제3자 라이브러리의 라이선스 및 외부 서비스 정책을 직접 확인하고 준수하여야 합니다.

개발자는 이용자의 사용 방식, 입력 자료, 변환 결과, 재배포 행위 또는 제3자 서비스 이용 행위에 관여하지 않습니다.

__PAGE_BREAK__

7. 보증의 부인

AnkiVoice는 있는 그대로 배포됩니다.

개발자는 본 프로그램의 정확성, 완전성, 안정성, 보안성, 호환성, 지속적 작동, 특정 목적 적합성 또는 제3자 서비스와의 계속적 연동을 보증하지 않습니다.

외부 서비스의 구조, 응답 형식, 접근 정책 또는 API 정책은 사전 고지 없이 변경될 수 있으며, 그 결과 본 프로그램의 일부 기능이 제한되거나 작동하지 않을 수 있습니다.

개발자는 본 프로그램이 모든 실행 환경에서 동일하게 작동하거나 모든 APKG, TXT, CSV 파일을 정상적으로 처리할 수 있음을 보장하지 않습니다.

__PAGE_BREAK__

8. 책임 제한

개발자는 본 프로그램의 사용, 수정, 배포, 오용 또는 제3자 서비스 이용으로 인하여 발생하는 직접적·간접적 손해에 대하여 책임을 부담하지 않습니다.

책임 제한의 대상에는 다음 사항이 포함됩니다.

- 데이터 손실, 파일 손상 또는 작업 결과의 오류
- 계정 제한, 서비스 차단, API 제한 또는 접근 거부
- 저작권 분쟁, 약관 위반, 권리 침해 주장 또는 법적 분쟁
- 무단 재배포, 상업적 오용 또는 외부 자료의 부적절한 사용
- 프로그램 오류, 호환성 문제, 보안상 결함 또는 이용 환경 문제
- 그 밖에 본 프로그램 또는 관련 자료의 사용으로 발생하는 불이익

이용자는 본 프로그램을 사용하기 전에 필요한 파일을 직접 백업하여야 합니다.

__PAGE_BREAK__

9. AI 활용 고지

AnkiVoice는 Lutte Laurent가 개발하였습니다.

개발 과정에서 ChatGPT가 코드 작성, 리팩터링, 디버깅, 문서 초안 작성 및 문구 정리에 보조적으로 활용되었습니다.

ChatGPT와 OpenAI는 본 프로젝트의 저자, 유지관리자, 후원자, 공식 배포자, 법률 대리인 또는 제3자 서비스 제공자가 아닙니다.

__PAGE_BREAK__

10. 약관 확인

이용자는 본 약관의 내용을 확인한 후 프로그램 사용 여부를 스스로 결정하여야 합니다.

본 약관에 동의하지 않는 경우 프로그램 사용을 중단하여야 합니다.

약관 동의 기록은 프로그램 설정 파일에 저장될 수 있으며, 약관 내용 또는 고지 버전이 변경되는 경우 재확인을 요구할 수 있습니다.

본 약관은 프로그램의 이용 조건을 설명하기 위한 고지 문서이며, 전문적인 법률 자문을 대체하지 않습니다.
'''

LEGAL_NOTICE_KO_MP3_ADDENDUM_TEXT = '''
추가 조항: MP3 수집 모듈

본 조항은 AnkiVoice에 MP3 수집 모듈이 포함되어 있거나 이용자가 해당 모듈을 별도로 설치하여 사용하는 경우에 적용됩니다.

MP3 수집 모듈은 이용자가 입력한 단어, 검색어 또는 학습 자료를 기준으로 외부 서비스에서 제공될 수 있는 미디어 URL, 서비스 응답, 메타데이터 또는 관련 자료를 확인하고, 개인 학습 목적의 작업 폴더로 정리하기 위한 기능입니다.

본 모듈은 외부 서비스, 미디어 제공자, 데이터베이스 제공자 또는 API 제공자를 대체하지 않습니다.

외부 서비스의 제공 여부, 접근 가능성, 응답 형식, 미디어 제공 방식 및 계속적 호환성은 보장되지 않습니다.

__PAGE_BREAK__

이용자는 본 모듈을 개인적·비상업적 언어 학습 목적에 한하여 사용할 수 있습니다.

본 모듈을 통해 접근, 확인, 정리 또는 저장할 수 있는 제3자 자료는 상업적 서비스, 유료 콘텐츠, 데이터베이스 구축, 대량 수집, 재배포, 미러링, 자동화된 대량 다운로드 또는 수익 창출 활동에 사용할 수 없습니다.

이용자는 외부 서비스에 과도한 요청을 전송하거나, 접근 제한·인증 절차·기술적 보호조치를 우회하거나, 제3자 서비스의 정상 운영을 방해할 수 있는 방식으로 본 모듈을 사용하여서는 안 됩니다.

__PAGE_BREAK__

본 모듈의 사용으로 제3자 자료에 관한 권리가 이용자에게 이전되거나 부여되지 않습니다.

이용자는 외부 서비스의 약관, API 정책, robots.txt, 호출 제한, 저작권 제한 및 관련 법령을 직접 확인하고 준수하여야 합니다.

개발자는 이용자의 검색어, 요청 방식, 다운로드 자료, 저장 자료, 재배포 행위 또는 외부 서비스 이용 방식에 관여하지 않습니다.

그로 인하여 발생하는 계정 제한, 접근 거부, 서비스 차단, 법적 분쟁 또는 기타 불이익에 대하여 개발자는 책임을 부담하지 않습니다.
'''

LEGAL_NOTICE_EN_CORE_TEXT = '''
Overview

These Terms set forth the conditions of use, scope of responsibility, third-party rights, and user obligations applicable to AnkiVoice.

AnkiVoice is an unofficial utility designed to help users organize Anki study materials and process TXT, CSV, APKG, and other study-related files in the user's local environment.

AnkiVoice is not an official program of Anki, AnkiWeb, or any other third-party service.

By continuing to use this program after reviewing these Terms, the user is deemed to have accepted them.

__PAGE_BREAK__

1. Nature of the program

AnkiVoice is an unofficial study utility that runs in the user's local environment.

The program may process Anki .apkg files, TXT files exported from Anki, plain TXT files, and CSV files in order to extract, convert, or organize word lists, study text, or related learning data.

The program does not replace any learning platform, file conversion service, database service, or official Anki-related service.

The program does not guarantee the availability, accessibility, data format, or future compatibility of any third-party service.

__PAGE_BREAK__

2. Purpose of use

AnkiVoice is provided for personal, non-commercial language-learning workflows.

The user may use the program to organize personal study materials, convert Anki decks or text files, or classify learning data for personal study purposes.

CSV files, TXT files, logs, settings, and other output files generated by the program are managed at the user's own responsibility.

Before using the program, the user must review applicable laws, third-party terms of service, and the rights status of any materials used.

__PAGE_BREAK__

3. License

The original AnkiVoice source code and project-specific documentation are provided under the PolyForm Noncommercial License 1.0.0.

The user may use, copy, modify, and redistribute the original AnkiVoice source code and project-specific documentation for non-commercial purposes in accordance with that license.

Commercial use, sale, paid provision, inclusion in revenue-generating services, or business use for profit is not permitted without separate written permission from the copyright holder.

This license applies only to the original AnkiVoice source code and project-specific documentation. It does not apply to third-party materials or content provided by external services.

__PAGE_BREAK__

4. Third-party materials and rights

The AnkiVoice license does not include copyrights, trademarks, database rights, service operation rights, or any other rights owned by third parties.

The following materials are not covered by the AnkiVoice license.

- Trademarks, logos, and service names of Anki, AnkiWeb, or other third parties
- APKG, TXT, CSV, and study materials provided by the user
- External websites, APIs, libraries, databases, and related materials
- Copyrighted works, metadata, service responses, media assets, and other protected materials owned by third parties

Use of this program does not transfer or grant any rights in those materials to the user.

__PAGE_BREAK__

5. Prohibited conduct

The user must not use AnkiVoice for illegal or unauthorized purposes.

The following conduct is prohibited.

- Infringement of copyright or other intellectual property rights
- Unauthorized copying, redistribution, sale, or paid provision of third-party materials
- Circumvention of access restrictions, authentication procedures, or technical protection measures
- Unauthorized database construction, crawling, or commercial use of external materials
- Violation of terms of service, license conditions, API policies, or applicable laws
- Any other conduct that may infringe third-party rights or interfere with service operation

__PAGE_BREAK__

6. User responsibility

The user is solely responsible for installing, executing, configuring, selecting input files, using converted results, and accessing external materials through the program.

The user must review and comply with applicable laws, the terms of Anki and AnkiWeb, and the licenses of third-party libraries.

The developer does not control the user's method of use, input materials, output results, redistribution, or use of third-party services.

__PAGE_BREAK__

7. Disclaimer of warranty

AnkiVoice is provided as is.

The developer makes no warranty regarding the accuracy, completeness, stability, security, compatibility, continuous operation, fitness for a particular purpose, or continued compatibility with any third-party service.

External services may change their structure, response format, access policy, or API policy without prior notice, and such changes may limit or disable certain program functions.

The developer does not guarantee that the program will work identically in every environment or process every APKG, TXT, or CSV file.

__PAGE_BREAK__

8. Limitation of liability

The developer is not liable for any direct or indirect damages arising from the use, modification, distribution, misuse, or third-party service usage of this program.

This limitation includes, but is not limited to, the following matters.

- Data loss, file corruption, or errors in output results
- Account restrictions, service blocks, API limitations, or access denial
- Copyright disputes, terms-of-service violations, infringement claims, or legal disputes
- Unauthorized redistribution, commercial misuse, or improper use of external materials
- Program errors, compatibility issues, security defects, or user-environment issues
- Any other disadvantage arising from the use of this program or related materials

The user should back up necessary files before using this program.

__PAGE_BREAK__

9. AI assistance notice

AnkiVoice was developed by Lutte Laurent.

ChatGPT was used as an assistant for coding, refactoring, debugging, drafting documentation, and revising text.

AI-generated output was reviewed and modified by the human developer before being included in the project.

ChatGPT and OpenAI are not authors, maintainers, sponsors, official distributors, legal representatives, or third-party service providers of this project.

__PAGE_BREAK__

10. Review of these Terms

The user must review these Terms and decide whether to use the program.

If the user does not agree to these Terms, the user must stop using the program.

A record of acceptance may be stored in the program settings file, and the user may be required to review the Terms again if the content or notice version changes.

These Terms are provided to describe the conditions of use and do not constitute professional legal advice.
'''

LEGAL_NOTICE_EN_MP3_ADDENDUM_TEXT = '''
Additional Terms: MP3 Collection Module

This section applies only when the MP3 collection module is included in AnkiVoice or separately installed and used by the user.

The MP3 collection module may check media URLs, service responses, metadata, or related materials that may be made available through external services, based on words, search terms, or study materials entered by the user.

This module does not replace any external service, media provider, database provider, or API provider, and does not guarantee the availability, accessibility, response format, media delivery method, or continued compatibility of any external service.

__PAGE_BREAK__

The user may use this module only for personal, non-commercial language-learning purposes.

Third-party materials that may be accessed, checked, organized, or stored through this module must not be used for commercial services, paid content, database construction, large-scale aggregation, redistribution, mirroring, automated bulk downloading, or any revenue-generating activity.

The user must not use this module in a manner that sends excessive requests to external services, circumvents access restrictions, authentication procedures, or technical protection measures, or interferes with the operation of third-party services.

__PAGE_BREAK__

Use of this module does not transfer or grant any rights in third-party materials to the user.

The user must independently review and comply with external service terms, API policies, robots.txt directives, rate limits, copyright restrictions, and applicable laws.

The developer does not control the user's search terms, request methods, downloaded materials, stored materials, redistribution, or use of external services, and shall not be liable for account restrictions, access denial, service blocking, legal disputes, or any other disadvantage arising from such use.
'''

LEGAL_NOTICE_TEXTS_CORE = {
    "ko": _notice_lines(LEGAL_NOTICE_KO_CORE_TEXT),
    "en": _notice_lines(LEGAL_NOTICE_EN_CORE_TEXT),
}

LEGAL_NOTICE_TEXTS_MP3 = {
    "ko": _notice_lines(_join_notice_text(LEGAL_NOTICE_KO_CORE_TEXT, LEGAL_NOTICE_KO_MP3_ADDENDUM_TEXT)),
    "en": _notice_lines(_join_notice_text(LEGAL_NOTICE_EN_CORE_TEXT, LEGAL_NOTICE_EN_MP3_ADDENDUM_TEXT)),
}

LEGAL_NOTICE_TEXTS_BY_VARIANT = {
    LEGAL_NOTICE_VARIANT_CORE: LEGAL_NOTICE_TEXTS_CORE,
    LEGAL_NOTICE_VARIANT_MP3: LEGAL_NOTICE_TEXTS_MP3,
}

LEGAL_NOTICE_VERSION_BY_VARIANT = {
    LEGAL_NOTICE_VARIANT_CORE: LEGAL_NOTICE_CORE_VERSION,
    LEGAL_NOTICE_VARIANT_MP3: LEGAL_NOTICE_MP3_VERSION,
}

LEGAL_NOTICE_VARIANT = detect_legal_notice_variant()

LEGAL_NOTICE_TEXTS = LEGAL_NOTICE_TEXTS_BY_VARIANT.get(
    LEGAL_NOTICE_VARIANT,
    LEGAL_NOTICE_TEXTS_CORE,
)

LEGAL_NOTICE_VERSION = LEGAL_NOTICE_VERSION_BY_VARIANT.get(
    LEGAL_NOTICE_VARIANT,
    LEGAL_NOTICE_CORE_VERSION,
)


def get_legal_notice_variant() -> str:
    return LEGAL_NOTICE_VARIANT


def get_legal_notice_version() -> str:
    return LEGAL_NOTICE_VERSION


def get_legal_notice_texts(variant: str | None = None) -> dict[str, list[str]]:
    selected_variant = variant or LEGAL_NOTICE_VARIANT
    return LEGAL_NOTICE_TEXTS_BY_VARIANT.get(selected_variant, LEGAL_NOTICE_TEXTS_CORE)


def get_legal_notice_version_for_variant(variant: str | None = None) -> str:
    selected_variant = variant or LEGAL_NOTICE_VARIANT
    return LEGAL_NOTICE_VERSION_BY_VARIANT.get(selected_variant, LEGAL_NOTICE_CORE_VERSION)


PATCH_NOTE_KO_TEXT = '''
AnkiVoice v1.5.0 배포 안내

주요 개정 사항

v1.5.0은 APKG 분석 리포트, 음성 파일 관리, 파일 형식 변경 및 관련 화면 안내를 전반적으로 정비한 배포판입니다.

본 버전에서는 학습 분석 결과의 가독성을 개선하고, Audio File Manager의 파일 정리 기능과 FFmpeg 기반 형식 변환 기능을 추가하였습니다.

__PAGE_BREAK__

1. APKG 분석 리포트 정비

APKG 내부의 복습 이력 및 FSRS 지표를 기반으로 생성되는 분석 리포트의 표시 형식과 안내 문구를 정리하였습니다.

- 리포트 문구 전반 정비
- 수치 요약, 분류 기준, 단어 예시의 표시 간격 조정
- 우선 검토 대상, 반복 오답, 장기 기억 형성 미흡 등 주요 분류 설명 정리
- 분석 완료 후 화면에 리포트 본문을 재출력하지 않고 저장 위치만 표시하도록 변경

__PAGE_BREAK__

2. Audio File Manager 기능 보강

Audio File Manager의 파일 정리 및 이동 기능을 보강하였습니다.

- audio 폴더의 MP3 파일을 Anki collection.media로 이동하는 메뉴 추가
- 저장된 collection.media 경로 사용 지원
- collection.media 이동 후 기존 audio 폴더 파일 삭제 여부 선택 기능 추가
- 파일명 언더바를 반각 공백으로 변경하는 메뉴 추가
- 확장자 추가, 제거, 변경 메뉴 정리

__PAGE_BREAK__

3. 파일 형식 변경 기능 추가

FFmpeg를 이용한 음성 파일 형식 변경 기능을 추가하였습니다.

해당 기능을 사용하려면 사용자의 PC에 FFmpeg가 별도로 설치되어 있어야 합니다. AnkiVoice에는 FFmpeg가 포함되어 있지 않으므로, 필요한 경우 사용자가 직접 설치하여야 합니다.

- 지원 가능한 음성 파일 형식 변경
- 확장자 정리 기능과의 연계 사용 지원
- 변환 대상 파일 확인 절차 보강

__PAGE_BREAK__

4. APKG 단어 퀴즈 기능

APKG 단어 퀴즈 기능을 사용할 수 있습니다.

- APKG 파일 선택
- 문제에 표시할 단어 필드 선택
- 뜻 필드 선택
- 5지선다 10문항 출제
- 퀴즈 결과 확인

__PAGE_BREAK__

5. 메인 화면 및 메뉴 구성 정비

메인 화면과 메뉴 구성을 정리하였습니다.

- ANV 사용 경과 일수 표시
- 일일 명언 표시 기능 추가
- 사용 기록 자동 저장
- 설정 및 정보 메뉴 위치 조정
- 일부 메뉴 문구 정비

__PAGE_BREAK__

6. 기타 조정 사항

사용 과정에서 확인된 일부 불편 사항을 함께 조정하였습니다.

- 안내 문구 일부 수정
- 결과 저장 안내 개선
- 파일 처리 과정의 확인 문구 정리
- 일부 화면 가독성 개선
- 불필요한 출력 감소

__PAGE_BREAK__

유의 사항

v1.5.0은 기능 추가와 화면 정비가 함께 반영된 배포판입니다.

FFmpeg가 필요한 기능은 이용자의 PC 환경 및 FFmpeg 설치 상태에 따라 동작 여부가 달라질 수 있습니다. 파일 변환 또는 파일 이동 작업을 수행하기 전에는 필요한 자료를 사전에 백업하는 것을 권장합니다.
'''

PATCH_NOTE_EN_TEXT = '''
AnkiVoice v1.5.0 Release Patch Notes

Main Changes

v1.5.0 improves the APKG analysis report, audio file management, and file type conversion workflow.

The difficulty analysis report has been cleaned up for better readability, and Audio File Manager now provides more options for organizing filenames, extensions, and audio file formats.

__PAGE_BREAK__

1. APKG Analysis Report Improvements

Improved the report generated from APKG review history and FSRS indicators.

- Revised report wording and layout
- Improved spacing for numeric summaries, classification criteria, and word examples
- Cleaned up explanations for priority review targets, repeated mistakes, and weak long-term retention
- After analysis, the program now shows only the saved report location instead of printing the report contents on screen

__PAGE_BREAK__

2. Audio File Manager Improvements

Improved file cleanup features in Audio File Manager.

- Added a menu for moving MP3 files from the audio folder to Anki collection.media
- Supports the saved collection.media path
- Added an option to delete remaining audio folder files after moving them to collection.media
- Added a menu for replacing underscores (_) in filenames with half-width spaces
- Cleaned up menus for adding, removing, and changing file extensions

__PAGE_BREAK__

3. File Type Conversion

Added audio file type conversion using FFmpeg.

FFmpeg must be installed on the user's PC to use this feature. FFmpeg is not included with AnkiVoice, so users must install it manually if needed.

- Converts supported audio file types
- Works together with extension cleanup features
- Improved confirmation steps before conversion

__PAGE_BREAK__

4. APKG Word Quiz

The APKG Word Quiz feature is available.

- Select an APKG file
- Select the word field shown in the quiz
- Select the meaning field
- Run a 10-question, five-choice quiz
- Check quiz results

__PAGE_BREAK__

5. Main Screen and Menu Cleanup

Cleaned up the main screen and menu structure.

- Shows how many days you have been using ANV
- Adds a daily quote that changes once per day
- Saves usage records automatically
- Adjusted the Settings / Information menu position
- Revised some menu text

__PAGE_BREAK__

6. Other Changes

Several smaller usability issues were also adjusted.

- Revised some guide messages
- Improved saved-file notices
- Cleaned up confirmation messages during file processing
- Improved readability on several screens
- Reduced unnecessary output

__PAGE_BREAK__

Note

v1.5.0 is both a feature update and a readability cleanup release.

Features that require FFmpeg may behave differently depending on the user's PC environment. Backing up important files is recommended before converting or moving files.
'''

CREATOR_NOTE_KO_TEXT = '''
제작자 고지

AnkiVoice는 단어장 제작 및 학습 자료 정리 과정에서 발생하는 반복 작업을 줄이기 위하여 제작된 보조 도구입니다.

본 프로그램은 개인 학습 환경에서 APKG, TXT, CSV 및 음성 파일 관련 작업을 보다 신속하게 처리할 수 있도록 구성되었습니다.

__PAGE_BREAK__

본 프로그램의 개발 과정에서는 실제 사용 중 확인된 불편 사항을 중심으로 기능 추가와 화면 정비를 계속 반영하고 있습니다.

향후에도 학습 자료 정리, 파일 변환, 복습 기록 분석 등 개인 학습 절차에 도움이 되는 기능을 순차적으로 보완할 예정입니다.

Developed by 7th OBS Labs
'''


CREATOR_NOTE_JA_TEXT = '''
開発者より

AnkiVoiceは単語帳作りを少しでも楽にできたらと思って作ったツールです。

単語を一つ覚える前から余計なことで時間を取られるのがもったいないと思っていました。

まあ面倒な作業が一つ減るだけでも結構楽ですね。半分くらいはバイブコーディングですが……

__PAGE_BREAK__

最近は韓国の物流倉庫で働いています。めちゃくちゃしんどいです。

それでも体は疲れていても頭を使うくらいの余力はあるので、休みの日には少しずつ何か作っています。

昔みたいに一日中開発に張り付く時間はなかなか取れませんが、思いついたときに少しずつ直したり機能を足したりしていたらここまで来ました。

これからも時間を見つけて少しずつ手を入れていくつもりです。勉強の役に立ちそうな機能を思いついたら一つずつ追加していこうと思います。

Developed by 7th OBS Labs
'''




CREATOR_NOTE_LANGUAGE_ORDER = ["ko", "ja"]

CREATOR_NOTE_LANGUAGE_LABELS = {
    "ko": "한국어",
    "ja": "日本語",
}

CREATOR_NOTE_TEXTS = {
    "ko": _notice_lines(CREATOR_NOTE_KO_TEXT),
    "ja": _notice_lines(CREATOR_NOTE_JA_TEXT),
}

PATCH_NOTE_TEXTS = {
    "ko": _notice_lines(PATCH_NOTE_KO_TEXT),
    "en": _notice_lines(PATCH_NOTE_EN_TEXT),
}

__all__ = [
    "LEGAL_NOTICE_LANGUAGE_ORDER",
    "LEGAL_NOTICE_LANGUAGE_LABELS",
    "LEGAL_NOTICE_ACCEPT_TEXTS",
    "LEGAL_NOTICE_VARIANT_CORE",
    "LEGAL_NOTICE_VARIANT_MP3",
    "LEGAL_NOTICE_BASE_VERSION",
    "LEGAL_NOTICE_CORE_VERSION",
    "LEGAL_NOTICE_MP3_VERSION",
    "LEGAL_NOTICE_VARIANT",
    "LEGAL_NOTICE_VERSION",
    "LEGAL_NOTICE_TEXTS",
    "LEGAL_NOTICE_TEXTS_CORE",
    "LEGAL_NOTICE_TEXTS_MP3",
    "LEGAL_NOTICE_TEXTS_BY_VARIANT",
    "LEGAL_NOTICE_VERSION_BY_VARIANT",
    "detect_legal_notice_variant",
    "get_legal_notice_variant",
    "get_legal_notice_version",
    "get_legal_notice_texts",
    "get_legal_notice_version_for_variant",
    "PATCH_NOTE_TEXTS",
    "CREATOR_NOTE_KO_TEXT",
    "CREATOR_NOTE_JA_TEXT",
    "CREATOR_NOTE_LANGUAGE_ORDER",
    "CREATOR_NOTE_LANGUAGE_LABELS",
    "CREATOR_NOTE_TEXTS",
]

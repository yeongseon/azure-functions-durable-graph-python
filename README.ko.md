# Azure Functions Durable Graph

[![PyPI](https://img.shields.io/pypi/v/azure-functions-durable-graph.svg)](https://pypi.org/project/azure-functions-durable-graph/)
[![Python Version](https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12%20%7C%203.13%20%7C%203.14-blue)](https://pypi.org/project/azure-functions-durable-graph/)
[![CI](https://github.com/yeongseon/azure-functions-durable-graph-python/actions/workflows/ci-test.yml/badge.svg)](https://github.com/yeongseon/azure-functions-durable-graph-python/actions/workflows/ci-test.yml)
[![Release](https://github.com/yeongseon/azure-functions-durable-graph-python/actions/workflows/publish-pypi.yml/badge.svg)](https://github.com/yeongseon/azure-functions-durable-graph-python/actions/workflows/publish-pypi.yml)
[![Security Scans](https://github.com/yeongseon/azure-functions-durable-graph-python/actions/workflows/security.yml/badge.svg)](https://github.com/yeongseon/azure-functions-durable-graph-python/actions/workflows/security.yml)
[![codecov](https://codecov.io/gh/yeongseon/azure-functions-durable-graph-python/branch/main/graph/badge.svg)](https://codecov.io/gh/yeongseon/azure-functions-durable-graph-python)
[![pre-commit](https://img.shields.io/badge/pre--commit-enabled-brightgreen?logo=pre-commit)](https://pre-commit.com/)
[![Docs](https://img.shields.io/badge/docs-gh--pages-blue)](https://yeongseon.github.io/azure-functions-durable-graph-python/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

다른 언어: [English](README.md) | [日本語](README.ja.md) | [简体中文](README.zh-CN.md)

> **Alpha 알림** — 이 패키지는 초기 개발 단계(`0.1.0a0`)입니다. 릴리스 간 API가 예고 없이 변경될 수 있습니다. 프로덕션 환경에서는 충분한 테스트 후 사용하세요.

**Azure Functions**와 **Durable Functions** 오케스트레이션을 위한 manifest 기반 그래프 런타임입니다.

---

**Azure Functions Python DX Toolkit**의 일부
→ Azure Functions에 FastAPI 수준의 개발자 경험을 제공합니다

## 왜 필요한가

Azure Functions에서 그래프 형태의 워크플로를 실행하는 것은 생각보다 어렵습니다:

- **오케스트레이터 결정론** — Durable Functions 오케스트레이터는 결정론적이어야 합니다. LLM이나 도구를 직접 호출하면 replay 안전성이 깨집니다
- **그래프-런타임 간극** — 노드/엣지 그래프 설계를 Durable Functions activity로 변환하려면 반복적인 배관 코드가 필요합니다
- **표준 런타임 부재** — 각 팀이 그래프 정의와 Durable Functions 프리미티브 간 연결을 직접 구현합니다

## 기능 소개

- **Manifest 기반 런타임** — 그래프 정의를 안정적이고 버전 관리된 manifest로 컴파일하여 오케스트레이터의 결정론을 위반하지 않습니다
- **자동 HTTP API** — `POST /api/graphs/{graph_name}/runs`, `GET /api/runs/{instance_id}`, 이벤트 주입, 취소, 헬스 엔드포인트가 자동으로 등록됩니다
- **결정론적 오케스트레이터 루프** — 모든 사용자 로직(노드 실행, 라우팅, 이벤트 처리)은 Durable Functions activity에서 실행되며, 오케스트레이터 내부에서는 실행되지 않습니다
- **조건부 라우팅 및 외부 이벤트** — `RouteDecision`을 통한 분기 워크플로와 human-in-the-loop 패턴을 지원합니다

## 범위

- Azure Functions Python **v2 프로그래밍 모델**
- `azure-functions-durable`을 통한 Durable Functions 오케스트레이션
- Pydantic v2 기반 상태 모델
- 그래프 토폴로지: 순차, 조건부, 이벤트 기반

이 패키지는 LangGraph와 독립적이며 LangGraph에 대한 의존성이 없습니다. 이름은 LangGraph의 노드/엣지 모델에서 영감을 받았습니다.

## 기능

- 그래프 노드, 라우트, 이벤트 핸들러를 선언하는 `ManifestBuilder` API
- 구성 가능한 실행 루프를 가진 결정론적 Durable Functions 오케스트레이터
- Pydantic v2 모델을 통한 타입 안전 상태 관리
- 내장 HTTP 엔드포인트: 실행 시작, 상태 조회, 이벤트 전송, 취소, 헬스, OpenAPI
- 매니페스트 파생 해시를 통한 그래프 버전 관리로 안전한 배포 지원

## 설치

```bash
pip install azure-functions-durable-graph
```

Azure Functions 앱에 다음도 포함해야 합니다:

```text
azure-functions
azure-functions-durable
azure-functions-durable-graph
```

로컬 개발용:

```bash
git clone https://github.com/yeongseon/azure-functions-durable-graph-python.git
cd azure-functions-durable-graph
pip install -e .[dev]
```

## 빠른 시작

```python
from pydantic import BaseModel

from azure_functions_durable_graph import DurableGraphApp, ManifestBuilder, RouteDecision


class MyState(BaseModel):
    message: str
    processed: bool = False


def process_message(state: MyState) -> dict:
    return {"processed": True}


def finalize(state: MyState) -> dict:
    return {"message": f"Done: {state.message}"}


builder = ManifestBuilder(graph_name="my_graph", state_model=MyState)
builder.set_entrypoint("process")
builder.add_node("process", process_message, next_node="finalize")
builder.add_node("finalize", finalize, terminal=True)

registration = builder.build()

runtime = DurableGraphApp()
runtime.register_registration(registration)
app = runtime.function_app
```

### 제공되는 것

1. `POST /api/graphs/my_graph/runs` — 새로운 그래프 실행을 시작합니다
2. `GET /api/runs/{instance_id}` — 실행 상태를 조회합니다
3. `GET /api/health` — 등록된 그래프를 나열합니다
4. `GET /api/openapi.json` — OpenAPI 문서

## 두러블 운영 모델

프로덕션 전에 알아야 할 두러블 관련 핵심 개념입니다. 자세한 내용은 [Durable Concepts](docs/durable-concepts.md)를 참고하세요.

1. **오케스트레이터 수명 주기** — 오케스트레이터는 결정적(deterministic)이며 재실행에 안전합니다. 매니페스트를 읽고 액티비티를 호출하고 이벤트를 대기할 뿐이며, `OrchestrationInput`의 `graph_hash`로 그래프 버전을 고정합니다.
2. **매니페스트 → 등록 → 런타임** — `ManifestBuilder.build()`가 검증되고 해시로 버전이 매겨진 `GraphRegistration`을 컴파일하고, `register_registration()`으로 등록한 뒤, 실행 시 현재 `graph_hash`에 대해 액티비티를 실행합니다.
3. **상태 병합 규칙** — 핸들러가 `dict`를 반환하면 **얕은 병합**(최상위 키만), `BaseModel`을 반환하면 상태를 **교체**, `None`이면 상태를 **유지**합니다. 중첩 dict는 깊은 병합이 되지 않습니다.
4. **이벤트 및 재개** — 라우트 핸들러가 `RouteDecision.wait_for_event(event_name, resume_node)`를 반환해 실행을 일시 중지할 수 있습니다. `POST /api/runs/{instance_id}/events/{event_name}`로 이벤트를 전달하면 `resume_node`에서 재개됩니다.
5. **`host.json` 필수** — Durable Functions에는 Durable Task 확장과 확장 번들이 필요합니다. [Deployment](docs/deployment.md) 가이드를 참고하세요.
6. **주요 함정** — 얕은 병합, `host.json` 누락, 환경 간 태스크 허브 재사용. [Troubleshooting](docs/troubleshooting.md) 참고.

## 사용 시점

- Azure Functions에서 그래프 형태의 LLM 워크플로가 필요한 경우
- 수동 activity 연결 없이 결정론적 Durable Functions 오케스트레이션이 필요한 경우
- Human-in-the-loop 승인 패턴(외부 이벤트)이 필요한 경우
- 토폴로지 해싱을 통한 버전 관리된 그래프 배포가 필요한 경우

## 예제

| 예제 | 패턴 | 핵심 개념 |
|------|------|-----------|
| [Data Pipeline](examples/data_pipeline/) | 순차 실행 | `next_node` 체이닝, 상태 누적 |
| [Content Classifier](examples/content_classifier/) | 조건부 라우팅 | `RouteDecision.next()`, fan-in 토폴로지 |
| [Support Agent](examples/support_agent/) | Human-in-the-loop | `wait_for_event`, 외부 이벤트, 승인 플로 |

## 문서

- 프로젝트 문서는 `docs/` 아래에 있습니다
- 테스트된 예제는 `examples/` 아래에 있습니다
- 제품 요구사항: `PRD.md`
- 설계 원칙: `DESIGN.md`

## 에코시스템

**Azure Functions Python DX Toolkit**의 일부:

| 패키지 | 역할 |
|---------|------|
| [azure-functions-validation](https://github.com/yeongseon/azure-functions-validation) | 요청 및 응답 validation |
| [azure-functions-openapi](https://github.com/yeongseon/azure-functions-openapi) | OpenAPI 스펙 및 Swagger UI |
| [azure-functions-logging](https://github.com/yeongseon/azure-functions-logging) | 구조화된 로깅 및 관측성 |
| [azure-functions-doctor](https://github.com/yeongseon/azure-functions-doctor) | 배포 전 진단 CLI |
| [azure-functions-scaffold](https://github.com/yeongseon/azure-functions-scaffold) | 프로젝트 스캐폴딩 |
| **azure-functions-durable-graph** | Durable Functions 기반 manifest 그래프 런타임 |
| [azure-functions-python-cookbook](https://github.com/yeongseon/azure-functions-python-cookbook) | 레시피 및 예제 |

## 면책 조항

이 프로젝트는 독립적인 커뮤니티 프로젝트이며, Microsoft와 제휴하거나
Microsoft의 보증 또는 유지 관리를 받지 않습니다.

Azure 및 Azure Functions는 Microsoft Corporation의 상표입니다.

## 라이선스

MIT

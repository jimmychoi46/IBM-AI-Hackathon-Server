# Watsonx 오케스트레이트 연동 (Backend)

이 파일은 백엔드 서버의 설정, 실행 및 프론트엔드 협업을 위한 통합 가이드입니다. (서버 구동부터 API 연동까지 과정 확인 가능)

---

## 1. 환경 구축 및 라이브러리 설치

프로젝트 구동을 위해서는 파이썬(Python) 환경에서 아래 의존성 패키지를 설치해야 합니다.

```bash
pip install fastapi==0.115.6 uvicorn==0.34.0 httpx==0.28.1 python-dotenv==1.0.1
```

## 2. 환경 변수 설정 (.env)

프로젝트 루트 디렉토리에 .env 파일을 생성하고, 아래 항목에 정보를 입력하세요.

※ 해당 부분은 해당 에이전트를 구축한 담당자의 정보를 입력해주시길 바랍니다.


### IBM Cloud 인증 및 인스턴스 정보

IBM_API_KEY=your_actual_api_key_here

INSTANCE_ID=your_actual_instance_id_here

### 서비스 리전 (기본값: us-south)
REGION=us-south

### Watsonx 오케스트레이트 에이전트 정보 (Supervisor Agent의 Agent ID 사용 권장)
AGENT_ID=your_actual_agent_id_here


## 3. 서버 실행 방법

서버 메인 파일명이 server.py인 경우, 아래 명령어로 서버를 시작합니다.

```python
python server.py
```

Base URL: http://localhost:8000

대화형 API 문서 (Swagger): http://localhost:8000/docs

→ 여기서 직접 테스트 가능

## 4. 프론트엔드 API 연동 명세 (API Guide)

[POST] /api/chat

사용자의 질문을 백엔드를 거쳐 Watsonx 오케스트레이트에 전달, 응답을 받아옵니다.

### Request Body (JSON)

1) JSON 필수 필드 (JSON 요청을 위함)

   - user_query (String): 챗봇에게 전달할 사용자 질문 메시지

2) JSON 요청 예시 (JSON 응답과의 통일성 유지를 위해 마찬가지로 OpenTripPlanner Agent의 instruction에서 발췌 후 일부 수정) 

```json
   {
     "user_query": "현재 위치에서 태릉입구역 3번 출구까지 가는 방법 알려줘"
   }
```
### Response Body (JSON)

1) JSON 반환 필드

   - status (String): 성공 여부 ("success")

   - answer (String): 사용자에게 보여줄 챗봇의 최종 답변 텍스트

   - data (Object): Watsonx 오케스트레이트 원본 데이터

2) JSON 응답 예시 (OpenTripPlanner Agent의 instruction에서 발췌 후 일부 수정)


```json
{
    "status": "success",
    "answer": "태릉입구역 3번 출구까지 총 19.6km, 약 51분 소요되는 경로를 찾았습니다.",
    "data": {
        "trip": {
            "tripPatterns": [
                {
                    "aimedStartTime": "2026-01-11T17:34:28+09:00",
                    "distance": 19626.6,
                    "legs": [
                        { "mode": "foot", "toPlace": { "name": "태릉입구역3번출구" } }
                    ]
                }
            ]
        }
    }
}
```

## 5.상세 예외 처리 가이드

통신 중 에러 발생 시 HTTP 상태 코드와 함께 아래와 같은 상세 메시지가 반환됩니다.

- 401 Unauthorized: 인증 오류 -> IBM API Key 설정 확인 필요.

- 503 Service Unavailable: 연결 오류(IBM Cloud 서버 접속 불가) -> 네트워크 확인 필요.

- 504 Gateway Timeout: 시간 초과(Watsonx 오케스트레이트 응답 지연 (설정 시간:총 60초[접속 10초 + 데이터 전송 50초]))
 
  -> 잠시 후 재시도 권장.

- 500 Internal Server Error: Unexpected Error(백엔드 내부 로직 오류 발생)



---

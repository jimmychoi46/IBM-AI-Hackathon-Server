import traceback
import httpx
import logging
import os
import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Dict, Any, Optional

TIMEOUT_SEC = 60.0 
# 타임아웃 기준 설정(접속 10초, 데이터 전송 50초, 총 60초)
timeout = httpx.Timeout(TIMEOUT_SEC, connect=10.0, read=50.0)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("오케스트레이트-백엔드")

# .env 로드 및 검증
load_dotenv()
IBM_API_KEY = os.getenv('IBM_API_KEY', '').strip()
BASE_URL = os.getenv('BASE_URL', '').strip().rstrip('/')
INSTANCE_ID = os.getenv('INSTANCE_ID', '').strip()
AGENT_ID = os.getenv("AGENT_ID", "").strip()
AGENT_ENVIRONMENT_ID = os.getenv("AGENT_ENVIRONMENT_ID", "").strip()

app = FastAPI(
    title="Watsonx 오케스트레이트 연동 서버",
    description="Watsonx 오케스트레이트 데이터를 Fetch하여 프론트엔드에 전달하는 백엔드 API",
    debug=True
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ChatRequest(BaseModel):
    user_query: str

class ChatResponse(BaseModel):
    status: str
    answer: str
    data: Dict[str, Any]

async def get_ibm_token():
    if not IBM_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="환경 변수(IBM_API_KEY) 확인 필요"
        )
    url: str = "https://iam.cloud.ibm.com/identity/token"
    payload: Dict[str, str] = {
        "grant_type": "urn:ibm:params:oauth:grant-type:apikey",
        "apikey": IBM_API_KEY
    }
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(url, data=payload, timeout=5.0)
            response.raise_for_status()
            return response.json().get("access_token", "")
        except httpx.HTTPStatusError as e:
            logger.error(f"[Auth Error] 인증 실패: {e.response.text}")
            raise HTTPException(status_code=401, detail="인증 실패")

@app.post("/api/chat", response_model=ChatResponse)
async def chat_with_agent(request_data: ChatRequest):
    async with httpx.AsyncClient(timeout=timeout) as client:
        try:
            token = await get_ibm_token()

            raw_id = INSTANCE_ID
            if raw_id.startswith("crn:"):
                instance_guid = raw_id.strip(":").split(":")[-1]
            elif "_" in raw_id:
                instance_guid = raw_id.split("_")[-1]
            else:
                instance_guid = raw_id

            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
                "Accept": "application/json",
                "X-Watson-Orchestrate-Service-Instance-Id": instance_guid,
                "X-Watson-Orchestrate-Agent-Id": (AGENT_ID or "").strip(),
                "X-Watson-Orchestrate-Agent-Environment-Id": (AGENT_ENVIRONMENT_ID or "").strip(),
            }

            base_url_str = str(BASE_URL).strip().rstrip('/')
            endpoint = f"{base_url_str}/v2/chat?version=2024-03-14"

            logger.info(f"Target URL: {endpoint}")
            logger.info(f"Final GUID used: '{instance_guid}'")
            
            payload = {
                "input": {
                    "message_type": "text",
                    "text": request_data.user_query
                },
                "user": {
                    "id": "test_user_001"
                }
            }

            logger.info(f"Sending Headers: {headers}")
            logger.info(f"[Request] Watsonx Fetch 시도: {request_data.user_query}")
            
            response = await client.post(endpoint, json=payload, headers=headers)
            
            response.raise_for_status()

            result = response.json()
            
            answer_list = []
            generic_list = result.get("output", {}).get("generic", [])
            
            for item in generic_list:
                res_type = item.get("response_type")
                if res_type == "text":
                    answer_list.append(item.get("text", ""))
                elif res_type == "option":
                    answer_list.append(item.get("title", ""))
                elif res_type == "user_defined":
                    answer_list.append("[구조화된 데이터 응답 포함]")

            answer = "\n".join(filter(None, answer_list)).strip()

            if not answer:
                answer = "에이전트로부터 응답이 없습니다."

            return {"status": "success", "answer": answer, "data": result}
        
        except httpx.ConnectError:
            logger.error("[Connect Error] Watsonx 오케스트레이트 서버 연결 불가.")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="[연결 오류] IBM Cloud 서버에 접속할 수 없습니다. 네트워크를 확인해 주세요."
            )

        except httpx.TimeoutException:
            logger.error(f"[Timeout Error] 서버 응답 시간 초과 (기준: {TIMEOUT_SEC}s).")
            raise HTTPException(
                status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                detail=f"[시간 초과] 에이전트가 {int(TIMEOUT_SEC)}초 내에 응답하지 않았습니다."
            )

        except httpx.HTTPStatusError as e:
            logger.error(f"IBM API 실패: {e.response.status_code} - {e.response.text}")
            raise HTTPException(
                status_code=e.response.status_code, 
                detail=f"Watsonx API 오류: {e.response.text}"
            )

        except Exception as e:
            logger.error(f"[Unexpected Error]: {str(e)}")
            logger.error(traceback.format_exc())
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"서버 내부 오류 발생: {str(e)}"
            )

if __name__ == "__main__":
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=True)

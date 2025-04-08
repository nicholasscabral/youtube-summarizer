from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from summarize import summarize_video
from database import SessionLocal, engine, Base
from models import VideoSummary
import datetime
import asyncio
import logging
import json
from fastapi import WebSocketDisconnect
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# Get environment variables
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8000"))
DEBUG = os.getenv("DEBUG", "True").lower() == "true"

Base.metadata.create_all(bind=engine)
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

class VideoInput(BaseModel):
    url: str

async def send_progress(websocket, progress, message):
    try:
        await websocket.send_json({"progress": progress, "message": message})
        logger.info(f"Progresso enviado: {progress}% - {message}")
    except Exception as e:
        logger.error(f"Erro ao enviar progresso: {str(e)}")

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    logger.info("Nova conexão WebSocket estabelecida")
    
    try:
        while True:
            data = await websocket.receive_text()
            request = json.loads(data)
            
            if request["type"] == "summarize":
                url = request["url"]
                logger.info(f"Recebida requisição para resumir vídeo: {url}")
                
                async def progress_callback(progress, message):
                    await websocket.send_json({
                        "progress": progress,
                        "message": message
                    })
                
                try:
                    result = await summarize_video(url, progress_callback)
                    
                    # Salvar no banco de dados
                    db = SessionLocal()
                    try:
                        video = VideoSummary(
                            url=url,
                            transcript=result["transcript"],
                            summary=result["summary"],
                            video_title=result["video_info"]["title"],
                            video_thumbnail=result["video_info"]["thumbnail"],
                            video_duration=result["video_info"]["duration"],
                            video_uploader=result["video_info"]["uploader"],
                            video_upload_date=result["video_info"]["upload_date"],
                            created_at=datetime.datetime.utcnow()
                        )
                        db.add(video)
                        db.commit()
                        db.refresh(video)
                        logger.info("Dados salvos no banco de dados com sucesso")
                    except Exception as e:
                        logger.error(f"Erro ao salvar no banco de dados: {str(e)}")
                        db.rollback()
                    finally:
                        db.close()
                    
                    await websocket.send_json({
                        "summary": result["summary"],
                        "video_info": result["video_info"]
                    })
                except Exception as e:
                    logger.error(f"Erro ao processar vídeo: {str(e)}")
                    await websocket.send_json({
                        "error": str(e)
                    })
            else:
                logger.warning(f"Tipo de requisição desconhecido: {request['type']}")
                await websocket.send_json({
                    "error": "Tipo de requisição inválido"
                })
                
    except WebSocketDisconnect:
        logger.info("Cliente desconectado")
    except Exception as e:
        logger.error(f"Erro na conexão WebSocket: {str(e)}")
    finally:
        logger.info("Conexão WebSocket encerrada")

@app.get("/history")
def history():
    logger.info("Solicitação de histórico recebida")
    db = SessionLocal()
    try:
        results = db.query(VideoSummary).order_by(VideoSummary.created_at.desc()).all()
        logger.info(f"Retornando {len(results)} itens do histórico")
        return [{
            "url": r.url,
            "summary": r.summary,
            "title": r.video_title,
            "thumbnail": r.video_thumbnail,
            "duration": r.video_duration,
            "uploader": r.video_uploader,
            "upload_date": r.video_upload_date,
            "created_at": r.created_at.isoformat() if r.created_at else None
        } for r in results]
    except Exception as e:
        logger.error(f"Erro ao buscar histórico: {str(e)}")
        return []
    finally:
        db.close()

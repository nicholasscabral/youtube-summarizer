from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from summarize import summarize_video
from database import SessionLocal, engine, Base
from models import VideoSummary
import datetime
import logging
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

@app.post("/summarize")
async def summarize_endpoint(video_input: VideoInput):
    try:
        result = await summarize_video(video_input.url)
        
        # Save to database
        db = SessionLocal()
        try:
            video = VideoSummary(
                url=video_input.url,
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
            logger.info("Data saved to database successfully")
        except Exception as e:
            logger.error(f"Error saving to database: {str(e)}")
            db.rollback()
        finally:
            db.close()
        
        return {
            "summary": result["summary"],
            "video_info": result["video_info"]
        }
    except Exception as e:
        logger.error(f"Error processing video: {str(e)}")
        raise

@app.get("/history")
def history():
    logger.info("History request received")
    db = SessionLocal()
    try:
        results = db.query(VideoSummary).order_by(VideoSummary.created_at.desc()).all()
        logger.info(f"Returning {len(results)} items from history")
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
        logger.error(f"Error fetching history: {str(e)}")
        return []
    finally:
        db.close()

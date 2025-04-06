from sqlalchemy import Column, Integer, String, DateTime, Text
from database import Base

class VideoSummary(Base):
    __tablename__ = "video_summaries"
    id = Column(Integer, primary_key=True, index=True)
    url = Column(String, index=True)
    transcript = Column(Text)
    summary = Column(Text)
    video_title = Column(String)
    video_thumbnail = Column(String)
    video_duration = Column(Integer)
    video_uploader = Column(String)
    video_upload_date = Column(String)
    created_at = Column(DateTime)

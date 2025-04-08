import whisper
from yt_dlp import YoutubeDL
import os
from pydub import AudioSegment
import logging
import openai
import requests
import re
import isodate
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

openai.api_key = os.getenv("OPENAI_API_KEY")

def extract_video_id(url):
    match = re.search(r"(?:v=|\/)([0-9A-Za-z_-]{11})", url)
    if not match:
        raise ValueError("ID do vídeo não encontrado na URL")
    return match.group(1)

def get_video_info_youtube_api(video_id):
    api_key = os.getenv("YOUTUBE_API_KEY")
    url = f"https://www.googleapis.com/youtube/v3/videos?part=snippet,contentDetails&id={video_id}&key={api_key}"
    
    response = requests.get(url)
    data = response.json()

    if not data["items"]:
        raise ValueError("Vídeo não encontrado na YouTube API")

    item = data["items"][0]
    snippet = item["snippet"]
    content_details = item["contentDetails"]

    return {
        "title": snippet["title"],
        "thumbnail": snippet["thumbnails"]["high"]["url"],
        "uploader": snippet["channelTitle"],
        "upload_date": snippet["publishedAt"].split("T")[0],
        "duration": int(isodate.parse_duration(content_details["duration"]).total_seconds())
    }

def download_audio(url):
    logger.info(f"Iniciando download do áudio para URL: {url}")
    ydl_opts = {
        'format': 'bestaudio/best',
        'user_agent': 'Mozilla/5.0',
        'outtmpl': 'audio.%(ext)s',
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
        }],
        'quiet': True
    }
    with YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])
    return "audio.mp3"

def transcribe_audio(audio_path):
    logger.info("Iniciando transcrição com Whisper")
    model = whisper.load_model("base")
    result = model.transcribe(audio_path)
    logger.info(f"Transcrição concluída. Tamanho do texto: {len(result['text'])} caracteres")
    return result["text"]

def generate_summary(text):
    try:
        chunks = [text[i:i+4000] for i in range(0, len(text), 4000)]
        summaries = []

        for chunk in chunks:
            prompt = f"""
            Analise o seguinte texto e crie um resumo detalhado e estruturado:
            {chunk}
            """
            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "Você é um assistente especializado em resumos detalhados de vídeos."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=1000,
                temperature=0.7
            )
            summaries.append(response.choices[0].message.content)

        final_prompt = f"Combine os seguintes resumos parciais em um único resumo coeso:\n{' '.join(summaries)}"
        final_response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "Você é um assistente especializado em combinar e refinar resumos."},
                {"role": "user", "content": final_prompt}
            ],
            max_tokens=1500,
            temperature=0.7
        )

        return final_response.choices[0].message.content
    except Exception as e:
        logger.error(f"Erro ao gerar resumo: {str(e)}")
        raise

async def summarize_video(url, progress_callback=None):
    try:
        video_id = extract_video_id(url)
        video_info = get_video_info_youtube_api(video_id)

        if progress_callback:
            await progress_callback(20, "Convertendo áudio...")
        mp3 = download_audio(url)
        audio = AudioSegment.from_mp3(mp3)
        audio.export("audio.wav", format="wav")

        if progress_callback:
            await progress_callback(40, "Transcrevendo áudio...")
        transcript = transcribe_audio("audio.wav")

        if progress_callback:
            await progress_callback(60, "Gerando resumo...")
        summary = generate_summary(transcript)

        if progress_callback:
            await progress_callback(100, "Processo concluído!")

        os.remove("audio.mp3")
        os.remove("audio.wav")

        return {
            "transcript": transcript,
            "summary": summary,
            "video_info": video_info
        }

    except Exception as e:
        logger.error(f"Erro durante o processo de sumarização: {str(e)}")
        raise
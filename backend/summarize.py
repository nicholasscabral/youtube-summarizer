import whisper
from yt_dlp import YoutubeDL
import os
from pydub import AudioSegment
import asyncio
import logging
import torch
import openai
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

# Configure OpenAI
openai.api_key = os.getenv("OPENAI_API_KEY")

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
        info = ydl.extract_info(url, download=True)
        video_title = info.get('title', 'Título não disponível')
        video_thumbnail = info.get('thumbnail', '')
        video_duration = info.get('duration', 0)
        video_uploader = info.get('uploader', 'Desconhecido')
        video_upload_date = info.get('upload_date', '')
        
        video_info = {
            'title': video_title,
            'thumbnail': video_thumbnail,
            'duration': video_duration,
            'uploader': video_uploader,
            'upload_date': video_upload_date
        }
        
        logger.info(f"Informações do vídeo extraídas: {video_title}")
        return "audio.mp3", video_info

def transcribe_audio(audio_path):
    logger.info("Iniciando transcrição com Whisper")
    model = whisper.load_model("base")
    result = model.transcribe(audio_path)
    transcript = result['text']
    logger.info(f"Transcrição concluída. Tamanho do texto: {len(transcript)} caracteres")
    return transcript

def generate_summary(text):
    try:
        # Dividir o texto em chunks menores para processamento
        chunks = [text[i:i+4000] for i in range(0, len(text), 4000)]
        summaries = []
        
        for i, chunk in enumerate(chunks):
            prompt = f"""
            Analise o seguinte texto e crie um resumo detalhado e estruturado. 
            O resumo deve ser informativo o suficiente para que alguém não precise assistir ao vídeo original.
            
            Regras para o resumo:
            1. Use parágrafos para ideias principais e conceitos importantes
            2. Use bullet points APENAS para listar itens específicos, características ou pontos-chave que precisam ser destacados
            3. Mantenha a ordem cronológica e lógica do conteúdo
            4. Inclua exemplos e explicações quando relevante
            5. Destaque conclusões e insights importantes
            6. Seja conciso mas completo, cobrindo todos os pontos principais
            7. Use linguagem clara e direta
            8. Mantenha o contexto e as conexões entre as ideias
            
            Texto para resumir:
            {chunk}
            """
            
            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "Você é um assistente especializado em criar resumos detalhados e estruturados de vídeos. Seu objetivo é fornecer um resumo completo que permita ao leitor entender todo o conteúdo sem precisar assistir ao vídeo original."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=1000,
                temperature=0.7
            )
            
            summary = response.choices[0].message.content
            summaries.append(summary)
        
        # Combinar os resumos parciais em um resumo final
        final_prompt = f"""
        Combine os seguintes resumos parciais em um único resumo coeso e bem estruturado.
        Mantenha a mesma estrutura e formatação, usando parágrafos para ideias principais e bullet points apenas para listas específicas.
        
        Resumos parciais:
        {' '.join(summaries)}
        """
        
        final_response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "Você é um assistente especializado em combinar e refinar resumos, mantendo a estrutura e clareza do conteúdo."},
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
        if progress_callback:
            await progress_callback(20, "Convertendo áudio...")
        mp3, video_info = download_audio(url)
        audio = AudioSegment.from_mp3(mp3)
        audio.export("audio.wav", format="wav")
        logger.info("Conversão do áudio para WAV concluída")

        if progress_callback:
            await progress_callback(40, "Transcrevendo áudio...")
        transcript = transcribe_audio("audio.wav")
        logger.info("Transcrição do áudio concluída")

        if progress_callback:
            await progress_callback(60, "Gerando resumo...")
        summary = generate_summary(transcript)
        logger.info("Resumo gerado com sucesso")

        if progress_callback:
            await progress_callback(100, "Processo concluído!")

        logger.info("Limpeza dos arquivos temporários")
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

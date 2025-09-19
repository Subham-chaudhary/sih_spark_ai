import os
import google.generativeai as genai
from sqlalchemy import create_engine, Column, Integer, String, MetaData, Table, JSON
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.sql import text
from typing import Dict, Any, Optional
from dotenv import load_dotenv

load_dotenv()

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
DATABASE_URL = os.getenv("DATABASE_URL")
GOOGLE_EMBEDDING_MODEL = "gemini-embedding-001"

genai.configure(api_key=GOOGLE_API_KEY)

medical_engine = create_engine(DATABASE_URL)
MedicalSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=medical_engine)

session = MedicalSessionLocal()
metadata = MetaData()


#fetching existing data
result_data = session.execute(text("SELECT content FROM medicaldata2;")).mappings().fetchall()
# Convert RowProxy to dictionary
print("Success: " ,type(result_data))
print(len(result_data))

content_list = []
for content in result_data:
    content_list.append(content['content'])

print("Successful to create content_list :",type(content_list[0]))
current = 1
for chunk in content_list:
    try:
        print("__________________________")
        print(f"Generating embedding for chunk {current} out of {len(content_list)}")
        current += 1
        response = genai.embed_content(
            model=GOOGLE_EMBEDDING_MODEL,
            content=chunk,
            task_type="retrieval_document" 
        )
        print("Embedding generated successfully.\n", response['embedding'].__len__())
        session.execute(text("INSERT INTO medicalData3 (content, embedding) VALUES (:content, :embedding)"), {"content": chunk, "embedding":  response['embedding'] })
        print("Embedding inserted successfully.")
    except Exception as e:
        print(f"Error generating embedding: {e}")
        os._exit(0)

session.commit()
session.close()
print("Success")
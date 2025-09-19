import os
import google.generativeai as genai
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import SQLAlchemyError
from typing import Dict, Any, Optional
from dotenv import load_dotenv
from flask import Flask, request, jsonify
from flask_cors import CORS

load_dotenv()
app = Flask(__name__)
CORS(app)
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
GOOGLE_EMBEDDING_MODEL = "gemini-embedding-001"
GOOGLE_LLM_MODEL = "gemini-1.5-flash-8b"

MAIN_DATABASE_URL = os.getenv("MAIN_DATABASE_URL")
MEDICAL_DATABASE_URL = os.getenv("DATABASE_URL")

#Globals for psuedo session
USER_ID = None
USER_DATA = None


if GOOGLE_API_KEY is None:
    print("Please set the GOOGLE_API_KEY environment variable.")
    # In a Flask app, we might want to handle this more gracefully,
    # but for now, we'll keep the original behavior for simplicity.
    # A better approach would be to raise an exception or return an error response.

genai.configure(api_key=GOOGLE_API_KEY)

main_engine = None
MainSessionLocal = None
medical_engine = None
MedicalSessionLocal = None


try:
    main_engine = create_engine(MAIN_DATABASE_URL)
    MainSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=main_engine)

    medical_engine = create_engine(MEDICAL_DATABASE_URL)
    MedicalSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=medical_engine)

except SQLAlchemyError as e:
    print(f"Database connection error: {e}")

def get_user_info_from_db(user_id: str) -> Optional[Dict[str, Any]]:
    if not user_id:
        print("No user ID provided.")
        return None
    if not MainSessionLocal:
        print("Main database session factory not initialized.")
        return None

    db_session_main = MainSessionLocal()
    try:
        query = text("""
        SELECT
        user_name as name, user_role as role, story_titles as program_tile,story_contents as program_content,
        user_hotspot_locations as location, user_hotspot_names as region, user_hotspot_descriptions as news,
        watertest_notes as water_test_note, water_qualities as water_quality, waterbody_names as water_body_name, has_global_alert as global_alert, recent_reports as recent_report
        FROM rag_data_view
        WHERE user_id = :uid
        """)
        user_info = db_session_main.execute(query, {"uid": user_id}).mappings().fetchone()
        print("User retrieved from database")
        return dict(user_info) if user_info else None
    except SQLAlchemyError as e:
        print(f"An error occurred while fetching user info: {e}")
        return None
    finally:
        db_session_main.close()

def generate_embedding(text_content: str) -> Optional[list]:
    try:
        response = genai.embed_content(
            model=GOOGLE_EMBEDDING_MODEL,
            content=text_content,
            task_type="retrieval_document"
        )
        print("Embedding generated successfully.\n", response['embedding'].__len__())
        return response['embedding']
    except Exception as e:
        print(f"Error generating embedding: {e}")
        return None

def retrieve_medical_data(embedding: list) -> str:
    """
    Retrieves relevant medical data from the medicaldata2 table using vector similarity search.
    Mimics the logic from main.py's query_and_embed function.
    """
    if not MedicalSessionLocal:
        print("Medical database session factory not initialized.")
        return "Error: Medical database not configured."

    db_session_medical = MedicalSessionLocal()
    try:
        # Using the same similarity search logic as in main.py
        # Assumes 'embedding' column is of type vector and pgvector extension is enabled.
        search_sql = text(
            "SELECT content FROM medicaldata3 ORDER BY embedding <-> (:embedding)::vector LIMIT 2;"
        )
        result = db_session_medical.execute(search_sql, {"embedding": embedding})
        rows = result.fetchall()

        if not rows:
            return "No relevant medical data found."

        retrieved_content = "\n".join([row[0] for row in rows])
        return retrieved_content
    except SQLAlchemyError as e:
        print(f"An error occurred during medical data retrieval: {e}")
        return "Error retrieving medical data."
    finally:
        db_session_medical.close()

# --- Gemini Wrapper ---

SYSTEM_PROMPT = """
You are Spark AI, an advanced medical assistant chatbot.
Your responsibilities:

1. Always start by greeting the user by name if available (from user data).
2. Understand the user’s symptoms or health-related query. If unclear, politely ask clarifying questions before giving guidance.
3. Use the provided data sources to guide your response:
    - Context: retrieved medical knowledge (retrieved_content)
    - User Data: demographic info, region, water quality, alerts, recent reports
    - Use both to personalize advice.
4. Provide only **pre-treatment guidance**:
    - Lifestyle tips
    - Safe self-care
    - Awareness of environmental/local risks (e.g., low water quality, global alerts)
    - Over-the-counter options if generally considered safe
5. Never provide prescriptions or definitive diagnoses.
6. If important info is missing (e.g., age, sex, key symptoms), politely ask the user.
7. Stay strictly within the scope of symptoms, first aid, and health awareness.
    Do not answer unrelated topics.
8. End with the disclaimer if you gave treatment/self-care advice:
    "This is pre-treatment guidance only. Please consult a licensed doctor for a professional opinion."
"""


def google_gemini_wrapper(user_id: str, query: str) -> str:
    """
    Wrapper function to interact with Google Gemini for medical assistance.
    It retrieves user info, generates embeddings for the query,
    retrieves relevant medical data, and queries Gemini with context.
    """
    global USER_ID, USER_DATA
    print(f"Received query: '{query}' for user ID: '{user_id}'")

    # 1. Get User Info
    # if USER_ID == user_id:
    #     user_data = USER_DATA
    # else:
    user_data = get_user_info_from_db(user_id)
        # USER_DATA = user_data
        # USER_ID = user_id
    if not user_data:
        print("Could not retrieve user data. Proceeding without it.")
        user_data_str = "No user data available."
    else:
        user_data_str = str(user_data) # Convert dict to string for prompt
    print("User Data:", user_data_str)
    # 2. Generate Embedding for the Query
    query_embedding = generate_embedding(query)
    if not query_embedding:
        return "Failed to generate embedding for the query. Please check API key and model configuration."

    # 3. Retrieve Relevant Medical Data
    retrieved_content = retrieve_medical_data(query_embedding)
    print("Retrieved Medical Data:", retrieved_content[:100], "...", len(retrieved_content))
    if "Error retrieving" in retrieved_content or "not configured" in retrieved_content:
        return retrieved_content # Return error message from retrieval

    # 4. Construct the Prompt for Gemini
    prompt = f"""
System Instruction:
{SYSTEM_PROMPT}

Medical Knowledge Context:
{retrieved_content}

User Information:
{user_data_str}

User Query:
{query}

Guidelines for Response:
- Begin with a personalized greeting using the user's name (if available).
- If the query is vague or incomplete, ask for clarifications first.
- Integrate user information (age, sex, lifestyle, region, water quality, alerts, recent reports) with the medical context to tailor advice.
- Highlight environmental/local risks only if relevant to the user’s query or symptoms.
- If possible, make safe assumptions (e.g., if young vs. elderly, urban vs. rural risks).
- Be empathetic, concise, and reassuring.
- Provide **only pre-treatment guidance** (self-care, OTC, lifestyle tips).
- If guidance is provided, end with the safety disclaimer. If the response is only exploratory or asking clarifications, do not add the disclaimer.
"""

    try:
        model = genai.GenerativeModel(GOOGLE_LLM_MODEL)
        generation_config = genai.GenerationConfig(
        temperature=0.5,
        top_p=0.9,
        top_k=40,
        candidate_count=1,
        max_output_tokens=512
        )
        response = model.generate_content(
            prompt,
            generation_config=generation_config
        )

        # Basic check for empty response
        if not response.text.strip():
            return "Gemini API returned an empty response."

        return response.text.strip()

    except Exception as e:
        print(f"Error calling Gemini API: {e}")
        return "An error occurred while processing your request with Gemini. Please try again later."

# --- Flask App Setup ---
app = Flask(__name__)

@app.route('/ask', methods=['POST'])
def ask_spark_ai():
    data = request.get_json()
    user_id = data.get('user_id')
    query = data.get('query')

    if not user_id or not query:
        return jsonify({"error": "user_id and query are required"}), 400

    response_text = google_gemini_wrapper(user_id, query)
    return jsonify({"response": response_text})

@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({"status": "OK"}), 200

@app.route('/model', methods=['POST'])
def quit():
    global GOOGLE_EMBEDDING_MODEL
    previous = GOOGLE_EMBEDDING_MODEL
    data = request.get_json()
    model = data.get('model')
    GOOGLE_EMBEDDING_MODEL = model
    return jsonify({"current_model": model, "previous_model": previous}), 200
# --- Example Usage (for local testing) ---
if __name__ == "__main__":
    
    # response = google_gemini_wrapper("fb6082d1-e5ef-4de3-aecb-eca09f275c96", "I'm feeling sick")
    # print(response.strip())
    app.run(debug=True) # debug=True for development, set to False for production

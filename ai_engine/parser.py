import os
import json
from pypdf import PdfReader
from langchain_core.prompts import ChatPromptTemplate
from langchain_groq import ChatGroq
from models.database import async_sessionmaker, engine, UserProfile
from sqlalchemy.ext.asyncio import AsyncSession

# Load environment variables manually if python-dotenv is not explicitly called in main yet
# In a real app, this is often handled at the application entrypoint (e.g., main.py)

def extract_text_from_pdf(pdf_path: str) -> str:
    """Reads a PDF file and extracts its text."""
    try:
        reader = PdfReader(pdf_path)
        text = ""
        for page in reader.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"
        return text
    except Exception as e:
        print(f"Error reading PDF: {e}")
        return ""

async def parse_resume_with_llm(resume_text: str) -> dict:
    """
    Uses Groq Llama-3 to extract ATS-friendly skills, roles, and experience from resume text.
    """
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise ValueError("GROQ_API_KEY environment variable is missing.")

    # Initialize the Groq model
    # llama3-8b-8192 is blazing fast and free
    llm = ChatGroq(
        groq_api_key=api_key,
        model_name="llama3-8b-8192",
        temperature=0.0
    )

    prompt = ChatPromptTemplate.from_messages([
        ("system", "You are an expert technical recruiter and ATS software analyzer. "
                   "Given a candidate's resume, your job is to extract their core profile data "
                   "in strict JSON format. "
                   "Map their raw experiences into standard ATS-friendly keywords.\n\n"
                   "You must output ONLY valid JSON in the following format:\n"
                   "{{\n"
                   "  \"primary_skills\": [\"Python\", \"React\", \"Machine Learning\"],\n"
                   "  \"target_roles\": [\"Software Engineer Intern\", \"Data Science Intern\"],\n"
                   "  \"experience_level\": \"Junior/Student\"\n"
                   "}}\n\n"
                   "Do not include any Markdown formatting like ```json or any conversational text."),
        ("human", "Here is the candidate's resume:\n\n{resume_text}")
    ])

    chain = prompt | llm

    response = chain.invoke({"resume_text": resume_text})
    
    try:
        # Clean the response in case the LLM ignored instructions and wrapped in markdown
        cleaned_content = response.content.strip()
        if cleaned_content.startswith("```json"):
            cleaned_content = cleaned_content[7:]
        if cleaned_content.endswith("```"):
            cleaned_content = cleaned_content[:-3]
            
        parsed_data = json.loads(cleaned_content.strip())
        return parsed_data
    except json.JSONDecodeError as e:
        print(f"Failed to parse LLM output as JSON. Output was:\n{response.content}")
        raise e

async def save_user_profile(parsed_data: dict) -> UserProfile:
    """
    Saves the parsed dictionary into the database as a UserProfile.
    """
    async_session = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    
    async with async_session() as session:
        # For simplicity, we just create a new profile each time.
        # In a full app with users, we would update the existing user's profile.
        profile = UserProfile(
            primary_skills=parsed_data.get("primary_skills", []),
            target_roles=parsed_data.get("target_roles", []),
            experience_level=parsed_data.get("experience_level", "Unknown")
        )
        session.add(profile)
        await session.commit()
        await session.refresh(profile)
        return profile

async def process_resume_pipeline(pdf_path: str):
    """
    End-to-end pipeline: PDF -> Text -> LLM Extraction -> Database.
    """
    print(f"Processing resume: {pdf_path}")
    text = extract_text_from_pdf(pdf_path)
    
    if not text.strip():
        print("Failed to extract text from PDF or PDF is empty.")
        return None

    print("Extracting ATS keywords with Groq Llama-3...")
    parsed_data = await parse_resume_with_llm(text)
    
    print("Parsed Data:")
    print(json.dumps(parsed_data, indent=2))
    
    print("Saving to database...")
    profile = await save_user_profile(parsed_data)
    print(f"Successfully saved UserProfile with ID: {profile.id}")
    
    return profile

import os
from sqlalchemy import select
from models.database import async_sessionmaker, engine, Internship, UserProfile
from sqlalchemy.ext.asyncio import AsyncSession
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS

class InternshipMatcher:
    def __init__(self):
        # We use a lightweight local model suitable for 16GB RAM and CPU/GPU
        self.embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")

    async def get_all_internships(self) -> list[Internship]:
        async_session = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
        async with async_session() as session:
            stmt = select(Internship)
            result = await session.execute(stmt)
            return result.scalars().all()

    async def rank_internships_for_user(self, user_profile: UserProfile, top_k: int = 10):
        """
        Ranks internships from the database against a specific UserProfile using FAISS.
        """
        internships = await self.get_all_internships()
        
        if not internships:
            print("No internships found in the database. Run the scraper first.")
            return []

        print(f"Embedding {len(internships)} internships for vector matching...")
        
        # Prepare text representations of internships
        texts = []
        metadatas = []
        
        for job in internships:
            # Combine role, company, and location to create a strong semantic representation
            text_rep = f"Role: {job.title}. Company: {job.company}. Description/Location: {job.description}."
            texts.append(text_rep)
            metadatas.append({
                "id": job.id,
                "title": job.title,
                "company": job.company,
                "apply_url": job.apply_url,
                "deadline": job.deadline
            })

        # Create FAISS vector store
        vectorstore = FAISS.from_texts(texts, self.embeddings, metadatas=metadatas)
        
        # Prepare the user query based on their profile
        skills_str = ", ".join(user_profile.primary_skills)
        roles_str = ", ".join(user_profile.target_roles)
        query = f"Looking for roles: {roles_str}. My skills include: {skills_str}. Experience level: {user_profile.experience_level}."
        
        print(f"User Query Vector: {query}")
        
        # Perform similarity search
        results = vectorstore.similarity_search_with_score(query, k=top_k)
        
        ranked_jobs = []
        for doc, score in results:
            # Lower score means smaller distance (closer match in FAISS L2 distance)
            job_data = doc.metadata
            job_data["match_score"] = float(score)
            ranked_jobs.append(job_data)
            
        return ranked_jobs

async def run_matcher_demo():
    # Helper to test the matcher
    async_session = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with async_session() as session:
        # Get the latest user profile
        stmt = select(UserProfile).order_by(UserProfile.id.desc()).limit(1)
        result = await session.execute(stmt)
        user = result.scalar_one_or_none()
        
        if not user:
            print("No UserProfile found. Please run the parser first.")
            return
            
        matcher = InternshipMatcher()
        ranked = await matcher.rank_internships_for_user(user)
        
        print("\n--- Top Internship Matches ---")
        for i, job in enumerate(ranked, 1):
            print(f"{i}. {job['title']} at {job['company']}")
            print(f"   Deadline: {job['deadline']} | Score: {job['match_score']:.4f}")
            print(f"   URL: {job['apply_url']}\n")

if __name__ == "__main__":
    import asyncio
    asyncio.run(run_matcher_demo())

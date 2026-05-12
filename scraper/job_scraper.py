import asyncio
import logging
import re
from playwright.async_api import async_playwright
from sqlalchemy.dialects.sqlite import insert
from models.database import async_session, init_db, Internship

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

class GitHubScraper:
    def __init__(self):
        # SimplifyJobs maintains the most active lists for tech internships
        self.url = "https://github.com/SimplifyJobs/Summer2025-Internships"
        self.source_board = "SimplifyJobs GitHub"

    async def scrape_and_save(self):
        logger.info(f"Starting scraper for {self.url} in HEADED mode...")
        await init_db()
        
        async with async_playwright() as p:
            # Running in headed mode so you can see it
            browser = await p.chromium.launch(headless=False)
            context = await browser.new_context()
            page = await context.new_page()
            
            logger.info("Navigating to page...")
            await page.goto(self.url, wait_until="domcontentloaded")
            
            logger.info("Waiting for table to render...")
            # Wait for markdown table to load
            await page.wait_for_selector(".markdown-body table", timeout=10000)
            
            logger.info("Extracting table rows...")
            rows = await page.query_selector_all(".markdown-body table tbody tr")
            
            jobs_scraped = 0
            
            for row in rows:
                cells = await row.query_selector_all("td")
                if len(cells) < 4:
                    continue
                
                # Default Markdown Table Columns: Company | Role | Location | Application/Link | Date Posted
                company = await cells[0].inner_text()
                title = await cells[1].inner_text()
                location = await cells[2].inner_text()
                
                # App Link
                link_element = await cells[3].query_selector("a")
                if link_element:
                    apply_url = await link_element.get_attribute("href")
                else:
                    apply_url = await cells[3].inner_text()
                    
                # Skip closed jobs
                if "🔒" in apply_url or not apply_url.startswith("http"):
                    continue
                
                # Deadline or Date Posted (Column 5)
                deadline = None
                if len(cells) >= 5:
                    deadline_text = await cells[4].inner_text()
                    # Clean up the deadline/date text
                    deadline = deadline_text.strip()
                    if not deadline:
                        deadline = None

                company = company.strip()
                title = title.strip()
                apply_url = apply_url.strip()
                
                # Upsert into database
                async with async_session() as session:
                    stmt = insert(Internship).values(
                        title=title,
                        company=company,
                        description=location,
                        apply_url=apply_url,
                        source_board=self.source_board,
                        deadline=deadline
                    )
                    
                    # Ignore duplicate URLs to avoid inserting the same job twice
                    stmt = stmt.on_conflict_do_nothing(index_elements=['apply_url'])
                    
                    await session.execute(stmt)
                    await session.commit()
                    
                jobs_scraped += 1
                
            logger.info(f"Successfully scraped and processed {jobs_scraped} active internships.")
            
            await browser.close()

if __name__ == "__main__":
    scraper = GitHubScraper()
    asyncio.run(scraper.scrape_and_save())

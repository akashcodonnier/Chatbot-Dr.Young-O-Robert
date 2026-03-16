#!/usr/bin/env python3
"""
Web Scraper and Embedding Tool for Dr. Robert Young's Content

This module scrapes articles from multiple sources (case studies and Dr. Robert Young's blog)
and stores them in a database with vector embeddings for semantic search.

Features:
- Scrapes content from WordPress blog and case studies
- Extracts clean article content with noise filtering
- Generates semantic embeddings using sentence-transformers
- Stores structured data in MySQL database
- Handles rate limiting and respectful scraping practices
- Supports multiple content sources and categories

Scraping Sources:
1. Main WordPress Site: https://phoreveryoung.wordpress.com/
2. Dr. Robert Young Blog: https://drrobertyoung.com/blog/

Data Processing Pipeline:
1. Extract raw HTML content
2. Clean and filter relevant text
3. Generate vector embeddings
4. Store in database with metadata
"""

# Standard library imports
import time           # Timing and delays for respectful scraping
import logging        # Logging for monitoring and debugging
import warnings       # Warning suppression for cleaner output
import re             # Regular expressions for pattern matching
from urllib.parse import urljoin  # URL joining utilities

# Third-party imports
import requests                    # HTTP requests for web scraping
from bs4 import BeautifulSoup     # HTML parsing and content extraction
from sentence_transformers import SentenceTransformer  # Vector embedding generation

# Local imports
import sys
import os
# Add parent directory to path to import database module
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from database.db import get_connection  # Database connection utility

# Suppress SSL warnings for cleaner output during scraping
warnings.filterwarnings("ignore")

# Configure logging for detailed progress tracking
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Configuration constants for scraping behavior
DR_YOUNG_BLOG_URL = "https://drrobertyoung.com/blog/"
MAIN_WORDPRESS_URL = "https://phoreveryoung.wordpress.com/"
HEADERS = {"User-Agent": "Mozilla/5.0 (MultiSiteBot/1.0)"}  # Identify bot properly
MIN_CONTENT_LENGTH = 300  # Minimum content length to store an article (characters)
PAGE_DELAY = 1            # Delay between pages (seconds) for rate limiting
ARTICLE_DELAY = 2         # Delay between articles (seconds) for respectful scraping


def discover_subcategories(main_category_slug):
    """
    Discover subcategories within a main category
    
    Args:
        main_category_slug (str): Main category slug
    
    Returns:
        list: List of subcategory slugs
    """
    subcategories = set()
    main_category_url = f"https://phoreveryoung.wordpress.com/category/{main_category_slug}/"
    
    try:
        logger.info(f"🔍 Discovering subcategories in: {main_category_slug}")
        response = requests.get(main_category_url, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(response.text, "html.parser")
        
        # Look for subcategory links
        subcategory_links = soup.find_all('a', href=re.compile(
            rf'https://phoreveryoung\.wordpress\.com/category/{re.escape(main_category_slug)}/[^/"]+/'))
        
        for link in subcategory_links:
            href = link.get('href')
            if href:
                # Extract subcategory name
                pattern = rf'https://phoreveryoung\.wordpress\.com/category/{re.escape(main_category_slug)}/([^/"]+)/'
                match = re.search(pattern, href)
                if match:
                    subcategory = match.group(1)
                    if subcategory and subcategory not in ['feed', 'page']:
                        full_subcategory_path = f"{main_category_slug}/{subcategory}"
                        subcategories.add(full_subcategory_path)
                        logger.info(f"  📂 Found subcategory: {full_subcategory_path}")
        
        logger.info(f"✅ Found {len(subcategories)} subcategories in {main_category_slug}")
        return list(subcategories)
        
    except Exception as e:
        logger.warning(f"⚠️ Could not discover subcategories for {main_category_slug}: {e}")
        return []

def discover_all_categories():
    """
    Dynamically discover all categories and subcategories from the main WordPress page
    
    This function scrapes the main page and identifies all available categories
    and their subcategories by analyzing the HTML structure.
    
    Returns:
        list: List of category slugs to scrape (including subcategories)
    """
    logger.info("🔍 DISCOVERING CATEGORIES AND SUBCATEGORIES FROM MAIN WORDPRESS PAGE")
    
    try:
        # Fetch the main WordPress page
        response = requests.get(MAIN_WORDPRESS_URL, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(response.text, "html.parser")
        
        categories_found = set()
        
        # Method 1: Find category links in navigation/menu
        nav_links = soup.find_all('a', href=re.compile(r'https://phoreveryoung\.wordpress\.com/category/'))
        for link in nav_links:
            href = link.get('href')
            if href and '/category/' in href:
                # Extract category name from URL
                category_part = href.split('/category/')[-1].rstrip('/')
                if category_part and '?' not in category_part:
                    categories_found.add(category_part)
        
        # Method 2: Find category links in article meta data
        article_links = soup.find_all('a', href=re.compile(r'https://phoreveryoung\.wordpress\.com/category/'), rel="category tag")
        for link in article_links:
            href = link.get('href')
            if href and '/category/' in href:
                category_part = href.split('/category/')[-1].rstrip('/')
                if category_part and '?' not in category_part:
                    categories_found.add(category_part)
        
        # Method 3: Look for category classes in HTML
        category_elements = soup.find_all(class_=re.compile(r'category-[\w-]+'))
        for elem in category_elements:
            # Extract category from class names
            classes = elem.get('class', [])
            for cls in classes:
                if cls.startswith('category-') and cls != 'category':
                    category_name = cls.replace('category-', '')
                    if category_name and '_' not in category_name:  # Avoid meta classes
                        categories_found.add(category_name)
        
        # Convert to sorted list
        main_categories = sorted(list(categories_found))
        
        logger.info(f"✅ DISCOVERED {len(main_categories)} MAIN CATEGORIES:")
        for i, cat in enumerate(main_categories, 1):
            logger.info(f"  {i:2d}. {cat}")
        
        # Now discover subcategories for each main category
        all_categories_with_subcategories = main_categories.copy()
        
        logger.info("\n🔍 DISCOVERING SUBCATEGORIES...")
        for main_cat in main_categories:
            subcats = discover_subcategories(main_cat)
            all_categories_with_subcategories.extend(subcats)
            # Small delay between subcategory discoveries
            time.sleep(1)
        
        # Remove duplicates and sort
        final_categories = sorted(list(set(all_categories_with_subcategories)))
        
        logger.info(f"\n✅ FINAL DISCOVERY COMPLETE!")
        logger.info(f"📊 TOTAL CATEGORIES (including subcategories): {len(final_categories)}")
        
        # Show breakdown
        main_count = len(main_categories)
        sub_count = len(final_categories) - main_count
        logger.info(f"   • Main categories: {main_count}")
        logger.info(f"   • Subcategories: {sub_count}")
        
        logger.info("\n📚 ALL DISCOVERED CATEGORIES:")
        for i, cat in enumerate(final_categories, 1):
            prefix = "📁" if cat in main_categories else "📂"
            logger.info(f"  {i:2d}. {prefix} {cat}")
            
        return final_categories
        
    except Exception as e:
        logger.error(f"❌ Failed to discover categories: {e}")
        # Return fallback list if discovery fails
        logger.info("🔄 Using fallback category list")
        return [
            "before-and-after",
            "funny",
            "alkaline-lifestyle-and-diet",
            "health",
            "health/nutrition",
            "research",
            "products/water",
            "health/weight-loss",
            "retreats"
        ]

# Initialize sentence transformer model for embeddings
# Using all-MiniLM-L6-v2 for efficient sentence embeddings (22.7M parameters)
model = SentenceTransformer("all-MiniLM-L6-v2")


def extract_clean_article_content(soup):
    """
    Extract clean article content from a BeautifulSoup object
    
    This function attempts to find the main content of an article by trying various
    common HTML selectors and filtering out unwanted elements like navigation,
    advertisements, and footer content.
    
    Args:
        soup (BeautifulSoup): Parsed HTML document
        
    Returns:
        str: Cleaned article content or empty string if no content found
    """
    # Try common selectors for article content in order of preference
    selectors = [
        "article",                           # Standard article tag
        "div.entry-content",                 # WordPress entry content
        "div.elementor-widget-theme-post-content",  # Elementor theme content
        "main"                               # Main content area
    ]

    content_root = None
    for sel in selectors:
        content_root = soup.select_one(sel)
        if content_root:
            break

    # Return empty if no content container found
    if not content_root:
        return ""

    # Extract text from common content elements
    elements = content_root.find_all(
        ["p", "h1", "h2", "h3", "h4", "li"],  # Text-containing elements
        recursive=True
    )

    content_parts = []
    for el in elements:
        text = el.get_text(" ", strip=True)

        # Skip short texts that are likely navigation or formatting
        if len(text) < 30:
            continue

        # Skip unwanted content sections commonly found in footers/menus
        if any(skip in text.lower() for skip in [
            "share this", "related", "author", "posted on", "subscribe",
            "navigation", "footer", "copyright", "all rights reserved",
            "privacy policy", "terms of service", "cookie", "menu",
            "search", "leave a comment", "reply", "previous post",
            "next post", "facebook", "twitter", "linkedin", "email"
        ]):
            continue

        content_parts.append(text)

    return "\n".join(content_parts)

# Establish database connection and cursor
conn = get_connection()
cur = conn.cursor()

# Create articles table if it doesn't exist
cur.execute("""
CREATE TABLE IF NOT EXISTS dr_young_all_articles (
    id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    title TEXT,
    url TEXT UNIQUE,
    content LONGTEXT,
    embedding LONGTEXT
)
""")
conn.commit()

# Index creation commented out due to MariaDB compatibility issues
# cur.execute("CREATE INDEX IF NOT EXISTS idx_content_length ON dr_young_all_articles((CHAR_LENGTH(content)));")
# conn.commit()


def scrape_single_category(category_slug):
    """
    Scrape a single category from phoreveryoung.wordpress.com
    
    Args:
        category_slug (str): The category slug (e.g., 'health/nutrition' or 'research')
    
    Returns:
        int: Number of articles successfully scraped and stored
    """
    total_articles = 0
    base_url = f"https://phoreveryoung.wordpress.com/category/{category_slug}/"
    page_url = base_url

    logger.info(f"🚀 SCRAPING CATEGORY: {category_slug}")

    while page_url:
        # Fetch page content
        try:
            response = requests.get(page_url, headers=HEADERS, timeout=15)
            soup = BeautifulSoup(response.text, "html.parser")
        except Exception as e:
            logger.error(f"❌ Failed to fetch {page_url}: {e}")
            break

        # Find all articles on the page
        articles = soup.find_all("article")
        if not articles:
            logger.warning(f"⚠️ No articles found on {page_url}")
            break

        logger.info(f"📄 Found {len(articles)} articles on page: {page_url}")
        
        for i, art in enumerate(articles, 1):
            # Extract article URL - use rel="bookmark" (WordPress permalink) first
            title_link = (
                art.find("a", rel="bookmark", href=True) or
                (art.find(class_="entry-title") and art.find(class_="entry-title").find("a", href=True)) or
                art.find("h2", class_=lambda c: c and "title" in c and art.find("a", href=True)) or
                art.find("a", href=True)
            )
            if not title_link:
                continue

            url = title_link.get("href")
            if not url:
                continue

            # Check if article already exists in database (by URL)
            cur.execute("SELECT 1 FROM dr_young_all_articles WHERE url=%s", (url,))
            result = cur.fetchone()
            cur.fetchall()  # Consume any remaining results
            if result:
                logger.debug(f"⏭️ Skipping existing article by URL: {url}")
                continue

            # Fetch detailed article content
            try:
                detail_res = requests.get(
                    url,
                    headers=HEADERS,
                    timeout=10,
                    verify=False
                )
                detail_soup = BeautifulSoup(detail_res.text, "html.parser")
                # Use canonical URL if available (most accurate article URL)
                canonical = detail_soup.find("link", rel="canonical")
                if canonical and canonical.get("href"):
                    url = canonical["href"]
                elif detail_res.url != url:
                    url = detail_res.url  # Use final URL after redirects
            except Exception as e:
                logger.warning(f"⚠️ Failed to fetch article {url}: {e}")
                continue

            detail_soup = BeautifulSoup(detail_res.text, "html.parser")

            # Extract article title - look for the correct article title
            # First try entry-title class (WordPress standard)
            title_elem = detail_soup.find(class_="entry-title")
            
            # If not found, try the first h1 that is not the site header
            if not title_elem:
                h1_tags = detail_soup.find_all("h1")
                # Skip the first h1 if it contains site name
                for h1 in h1_tags:
                    text = h1.get_text(strip=True)
                    if text and "pHorever Young" not in text and "Blog" not in text:
                        title_elem = h1
                        break
                # If all h1 tags contain site name, use the first one
                if not title_elem and h1_tags:
                    title_elem = h1_tags[0]
            
            title = title_elem.get_text(strip=True) if title_elem else "Untitled"

            # Show article title being processed
            logger.info(f"📝 [{category_slug}] Processing article {i}/{len(articles)}: INSERTED {title}")

            # Extract and clean article content
            content = extract_clean_article_content(detail_soup)
            if len(content) < MIN_CONTENT_LENGTH:
                logger.debug(f"⏭️ Content too short for {title} ({len(content)} chars)")
                continue

            # Generate embedding for semantic search
            embedding = model.encode(content).tolist()

            # Check for duplicates: if same title AND same content, skip
            cur.execute("SELECT title, content FROM dr_young_all_articles WHERE title = %s", (title,))
            result = cur.fetchone()
            cur.fetchall()  # Consume any remaining results
            if result:
                existing_title, existing_content = result
                # If content is also the same, skip (true duplicate)
                if existing_content == content:
                    logger.debug(f"⏭️ Skipping exact duplicate (same title and content): {title}")
                    continue
                else:
                    # Same title but different content - this is a different article, so proceed
                    logger.debug(f"📝 Same title but different content found: {title}")
                    # Continue with insertion below
            
            # Insert article into database
            cur.execute("""
                INSERT INTO dr_young_all_articles
                (title, url, content, embedding)
                VALUES (%s, %s, %s, %s)
            """, (title, url, content, str(embedding)))

            # Get the ID of the inserted row
            inserted_id = cur.lastrowid
            conn.commit()
            total_articles += 1
            logger.info(f"✅ [{category_slug}] INSERTED (ID: {inserted_id}): {title}")

            # Respectful delay between articles
            time.sleep(ARTICLE_DELAY)

        # Get next page URL for pagination
        next_link = soup.find("a", class_="next")
        page_url = urljoin(base_url, next_link["href"]) if next_link and next_link.get("href") else None
        if page_url:
            logger.info(f"➡️ Moving to next page: {page_url}")
            time.sleep(PAGE_DELAY)

    logger.info(f"🏁 FINISHED CATEGORY {category_slug}: {total_articles} articles")
    return total_articles


def scrape_all_categories():
    """
    Scrape all categories from phoreveryoung.wordpress.com
    
    This function scrapes articles from all identified categories,
    extracts their content, generates embeddings, and stores them in the database.
    
    Returns:
        tuple: (total_articles, category_stats_dict) - Total articles and per-category stats
    """
    global ALL_CATEGORIES
    total_articles = 0
    failed_categories = []
    category_stats = {}
    
    logger.info("🚀 STARTING FULL CATEGORY SCRAPER")
    logger.info(f"📋 Total categories to scrape: {len(ALL_CATEGORIES)}")
    
    for i, category in enumerate(ALL_CATEGORIES, 1):
        logger.info(f"\n[{i}/{len(ALL_CATEGORIES)}] Processing category: {category}")
        try:
            articles_count = scrape_single_category(category)
            total_articles += articles_count
            category_stats[category] = articles_count
            logger.info(f"✅ Completed {category}: {articles_count} articles")
        except Exception as e:
            logger.error(f"❌ Failed to scrape category {category}: {e}")
            failed_categories.append(category)
            category_stats[category] = 0
        
        # Add extra delay between categories
        if i < len(ALL_CATEGORIES):
            logger.info(f"⏳ Waiting before next category...")
            time.sleep(5)
    
    logger.info("\n🏁 FULL CATEGORY SCRAPING COMPLETED")
    logger.info(f"📊 Total articles scraped: {total_articles}")
    if failed_categories:
        logger.warning(f"⚠️ Failed categories: {failed_categories}")
    
    return total_articles, category_stats

def scrape_dr_young_blog():
    """
    Scrape all articles from Dr. Robert Young's blog using WordPress REST API.
    Uses paginated API calls (100 posts per page) to get all articles reliably.

    Returns:
        tuple: (total_articles, category_stats_dict)
    """
    total_articles = 0
    category_stats = {"drrobertyoung_blog": 0}
    REST_API_URL = "https://drrobertyoung.com/wp-json/wp/v2/posts"
    PER_PAGE = 100

    logger.info("🚀 SCRAPING DR. ROBERT YOUNG BLOG (via WordPress REST API)")

    page = 1
    while True:
        try:
            resp = requests.get(
                REST_API_URL,
                params={"per_page": PER_PAGE, "page": page, "_fields": "id,title,link,content"},
                headers=HEADERS,
                timeout=30
            )
        except Exception as e:
            logger.error(f"❌ API request failed (page {page}): {e}")
            break

        # 400 means no more pages
        if resp.status_code == 400:
            logger.info(f"✅ No more pages after page {page - 1}")
            break

        if resp.status_code != 200:
            logger.error(f"❌ API returned status {resp.status_code} on page {page}")
            break

        posts = resp.json()
        if not posts:
            logger.info(f"✅ Empty response, done at page {page}")
            break

        logger.info(f"📄 Page {page}: {len(posts)} posts fetched from REST API")

        for post in posts:
            article_url = post.get("link", "")
            title = BeautifulSoup(post.get("title", {}).get("rendered", ""), "html.parser").get_text(strip=True) or "Untitled"
            content_html = post.get("content", {}).get("rendered", "")

            if not article_url or not content_html:
                continue

            # Check if already exists in DB
            cur.execute("SELECT 1 FROM dr_young_all_articles WHERE url=%s", (article_url,))
            result = cur.fetchone()
            cur.fetchall()
            if result:
                logger.debug(f"⏭️ Skipping existing: {article_url}")
                continue

            # Parse content HTML
            content_soup = BeautifulSoup(content_html, "html.parser")
            content = extract_clean_article_content(content_soup)

            # Fallback: plain text if selectors return nothing
            if len(content) < MIN_CONTENT_LENGTH:
                content = content_soup.get_text(" ", strip=True)

            if len(content) < MIN_CONTENT_LENGTH:
                logger.debug(f"⏭️ Content too short for: {title}")
                continue

            # Check duplicate by title + content
            cur.execute("SELECT content FROM dr_young_all_articles WHERE title = %s", (title,))
            dup = cur.fetchone()
            cur.fetchall()
            if dup and dup[0] == content:
                logger.debug(f"⏭️ Exact duplicate skipped: {title}")
                continue

            # Generate embedding
            embedding = model.encode(content).tolist()

            # Insert into DB
            cur.execute("""
                INSERT INTO dr_young_all_articles (title, url, content, embedding)
                VALUES (%s, %s, %s, %s)
            """, (title, article_url, content, str(embedding)))
            inserted_id = cur.lastrowid
            conn.commit()
            total_articles += 1
            category_stats["drrobertyoung_blog"] += 1
            logger.info(f"✅ [drrobertyoung_blog] INSERTED (ID: {inserted_id}): {title}")

            time.sleep(0.5)  # Light delay (no HTML page fetch needed)

        if len(posts) < PER_PAGE:
            # Last page reached
            break

        page += 1
        time.sleep(PAGE_DELAY)

    logger.info(f"🏁 FINISHED DR. ROBERT YOUNG BLOG: {total_articles} articles ({page} pages)")
    return total_articles, category_stats


# Removed unused function scrape_dr_young_all_categories()


# Main execution block
try:
    # Use the existing global database connection
    # conn and cur are already initialized at module level (lines 274-275)
    pass
    
    logger.info("🚀 STARTING MULTI-SITE SCRAPING")

    # Scrape Dr. Robert Young's blog FIRST (REST API - fast, no categories)
    logger.info("\n=== DRROBERTYOUNG.COM/BLOG ===")
    blog_articles, blog_category_stats = scrape_dr_young_blog()

    # Scrape WordPress site second
    logger.info("\n=== PHOREVERYOUNG.WORDPRESS.COM ===")
    all_categories = discover_all_categories()
    ALL_CATEGORIES = all_categories
    wp_articles, wp_category_stats = scrape_all_categories()

    # Log final statistics
    logger.info("\n🎉 MULTI-SITE SCRAPING COMPLETED")
    logger.info(f"Blog Articles: {blog_articles}")
    logger.info(f"WordPress Categories: {len(all_categories)}")
    logger.info(f"WordPress Articles: {wp_articles}")
    logger.info(f"Total Articles Scraped: {wp_articles + blog_articles}")
    
    # Detailed category breakdown
    logger.info("\n📋 DETAILED CATEGORY BREAKDOWN:")
    logger.info("\nWordPress Categories:")
    for category, count in wp_category_stats.items():
        prefix = "📁" if '/' not in category else "📂"  # Main category vs subcategory
        logger.info(f"  {prefix} {category}: {count} articles")
    
    logger.info("\nDr. Robert Young Blog Categories:")
    for category, count in blog_category_stats.items():
        logger.info(f"  📁 {category}: {count} articles")
    
    # Summary by category type
    main_cats = [cat for cat in all_categories if '/' not in cat]
    sub_cats = [cat for cat in all_categories if '/' in cat]
    
    logger.info(f"\n📊 SUMMARY:")
    logger.info(f"  WordPress main categories: {len(main_cats)} ({sum(wp_category_stats.get(cat, 0) for cat in main_cats)} articles)")
    logger.info(f"  WordPress subcategories: {len(sub_cats)} ({sum(wp_category_stats.get(cat, 0) for cat in sub_cats)} articles)")
    logger.info(f"  Blog categories: {len(blog_category_stats)} ({blog_articles} articles)")
    logger.info(f"  Total categories: {len(all_categories) + len(blog_category_stats)} ({wp_articles + blog_articles} articles)")

finally:
    # Always close database connection
    if 'conn' in globals():
        conn.close()

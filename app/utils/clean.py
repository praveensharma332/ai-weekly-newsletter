import re
import hashlib
from bs4 import BeautifulSoup, Comment

def clean_html(raw_html: str) -> str:
    """Cleans HTML content, removing scripts, styling, navigation, footers, comments, and sidebars."""
    if not raw_html:
        return ""
        
    soup = BeautifulSoup(raw_html, "html.parser")
    
    # 1. Remove comments
    for comment in soup.find_all(text=lambda text: isinstance(text, Comment)):
        comment.extract()

    # 2. Remove script, style, iframe, form, header, footer, nav, aside, ad elements
    noise_selectors = [
        "script", "style", "iframe", "noscript", "form", 
        "header", "footer", "nav", "aside", ".ad", ".ads", 
        ".sidebar", "#sidebar", ".widget", ".comment", ".comments",
        ".menu", ".navigation", ".cookie-consent", "#cookie-consent",
        ".social-share", ".share", ".footer-links"
    ]
    
    for tag in soup.find_all(noise_selectors):
        tag.extract()
        
    # 3. Extract text
    text = soup.get_text(separator="\n")
    
    # 4. Clean up whitespace and boilerplate lines
    cleaned_lines = []
    boilerplate_patterns = [
        r"cookie policy", r"accept cookies", r"subscribe to our newsletter",
        r"all rights reserved", r"terms of service", r"privacy policy",
        r"sign up for free", r"log in / register", r"read more at",
        r"follow us on twitter", r"share this article", r"written by"
    ]
    
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
            
        # Filter boilerplate lines
        is_boilerplate = False
        for pattern in boilerplate_patterns:
            if re.search(pattern, line.lower()):
                is_boilerplate = True
                break
                
        if not is_boilerplate and len(line) > 5:
            cleaned_lines.append(line)
            
    return "\n".join(cleaned_lines)

def generate_dedup_hash(title: str, url: str) -> str:
    """Generates a unique SHA-256 hash for deduplication based on normalized title and url."""
    norm_title = title.strip().lower()
    norm_url = url.strip().lower()
    # Remove protocol and query params from URL for stronger URL matching
    norm_url = re.sub(r"^https?://(www\.)?", "", norm_url)
    norm_url = norm_url.split("?")[0].rstrip("/")
    
    input_str = f"{norm_title}|{norm_url}"
    return hashlib.sha256(input_str.encode("utf-8")).hexdigest()

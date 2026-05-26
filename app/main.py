import os
import logging
from datetime import date, datetime
from typing import List, Optional
from fastapi import FastAPI, HTTPException, BackgroundTasks, Query
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel

from app.storage.database import db_session
from app.storage.models import Article, Newsletter
from app.providers import get_provider
from app.clustering.embedder import SemanticEmbedder
from app.scheduler.scheduler import NewsletterScheduler
from app.config.settings import settings

logger = logging.getLogger("newsletter.dashboard")

app = FastAPI(
    title="AI Weekly Newsletter Dashboard",
    description="Local engineering dashboard to browse briefs, vector search articles, and trigger fetch pipelines.",
    version="1.0.0"
)

# Initialize Scheduler
scheduler = NewsletterScheduler()

@app.on_event("startup")
def startup_event():
    """Startup routine starting scheduler background threads."""
    logger.info("Starting up FastAPI application...")
    try:
        scheduler.start()
    except Exception as e:
        logger.error(f"Failed to start scheduler on startup: {e}")

@app.on_event("shutdown")
def shutdown_event():
    """Shutdown routine stopping background threads."""
    logger.info("Shutting down FastAPI application...")
    scheduler.stop()


# ----------------------------------------------------
# API ENDPOINTS
# ----------------------------------------------------

@app.get("/api/newsletters", response_class=JSONResponse)
def get_newsletters():
    """Fetch archived newsletters."""
    newsletters = db_session.query(Newsletter).order_by(Newsletter.issue_date.desc()).all()
    return [n.to_dict() for n in newsletters]

@app.get("/api/newsletters/{issue_date}", response_class=JSONResponse)
def get_newsletter_detail(issue_date: str):
    """Fetch detailed content of an individual issue."""
    try:
        parsed_date = datetime.strptime(issue_date, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")
        
    newsletter = db_session.query(Newsletter).filter(Newsletter.issue_date == parsed_date).first()
    if not newsletter:
        raise HTTPException(status_code=404, detail="Newsletter not found.")
    return {
        "title": newsletter.title,
        "issue_date": newsletter.issue_date.isoformat(),
        "tldr": newsletter.tldr,
        "content_html": newsletter.content_html,
        "content_markdown": newsletter.content_markdown
    }

@app.get("/api/stats", response_class=JSONResponse)
def get_database_stats():
    """Returns database and collection statistics."""
    total_articles = db_session.query(Article).count()
    unused_articles = db_session.query(Article).filter(Article.is_used == False).count()
    total_newsletters = db_session.query(Newsletter).count()
    return {
        "total_articles": total_articles,
        "unused_articles": unused_articles,
        "total_newsletters": total_newsletters
    }

class SearchQuery(BaseModel):
    query: str
    top_k: int = 5

@app.get("/api/search", response_class=JSONResponse)
def semantic_vector_search(q: str = Query(..., min_length=2)):
    """Semantic vector search across stored articles using sentence-transformers."""
    articles = db_session.query(Article).all()
    if not articles:
        return []
        
    embedder = SemanticEmbedder()
    # Prepare list of dicts for search engine
    articles_data = []
    for art in articles:
        d = art.to_dict()
        d["embedding"] = art.embedding
        articles_data.append(d)
        
    results = embedder.search_similar_articles(q, articles_data, top_k=5)
    
    # Format response
    search_results = []
    for art_dict, score in results:
        # Strip large raw content to save response size
        art_dict.pop("cleaned_content", None)
        search_results.append({
            "article": art_dict,
            "score": round(score, 4)
        })
    return search_results

@app.post("/api/pipeline/run", response_class=JSONResponse)
def trigger_pipeline_run(background_tasks: BackgroundTasks):
    """Triggers the weekly newsletter compilation pipeline in background."""
    background_tasks.add_task(scheduler.run_newsletter_pipeline)
    return {"status": "success", "message": "Newsletter generation pipeline triggered in the background."}


# ----------------------------------------------------
# DASHBOARD HTML INTERFACE
# ----------------------------------------------------

@app.get("/", response_class=HTMLResponse)
def serve_dashboard():
    """Serves a beautifully crafted, responsive dashboard interface to manage the newsletter generator."""
    html_content = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>AI Weekly Newsletter Management Console</title>
        <link rel="preconnect" href="https://fonts.googleapis.com">
        <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
        <link href="https://fonts.googleapis.com/css2?family=Fira+Code:wght@400;500&family=Inter:wght@300;400;500;600;700&family=Outfit:wght@400;500;600;700;800&display=swap" rel="stylesheet">
        <style>
            :root {
                --bg-color: #080c14;
                --surface-color: #0f172a;
                --surface-accent: #1e293b;
                --text-primary: #f8fafc;
                --text-secondary: #94a3b8;
                --accent-blue: #3b82f6;
                --accent-purple: #8b5cf6;
                --accent-cyan: #06b6d4;
                --accent-gradient: linear-gradient(135deg, #8b5cf6 0%, #3b82f6 50%, #06b6d4 100%);
                --border-color: rgba(255, 255, 255, 0.08);
                --shadow-primary: 0 10px 25px -5px rgba(0, 0, 0, 0.5);
            }

            * {
                box-sizing: border-box;
                margin: 0;
                padding: 0;
            }

            body {
                font-family: 'Inter', sans-serif;
                background-color: var(--bg-color);
                color: var(--text-primary);
                line-height: 1.6;
                display: flex;
                height: 100vh;
                overflow: hidden;
            }

            /* Sidebar Styling */
            .sidebar {
                width: 280px;
                background: var(--surface-color);
                border-right: 1px solid var(--border-color);
                display: flex;
                flex-direction: column;
                padding: 30px 20px;
                flex-shrink: 0;
            }

            .logo {
                font-family: 'Outfit', sans-serif;
                font-weight: 800;
                font-size: 1.4rem;
                background: var(--accent-gradient);
                -webkit-background-clip: text;
                -webkit-text-fill-color: transparent;
                margin-bottom: 30px;
                text-align: center;
            }

            .nav-menu {
                list-style: none;
                flex-grow: 1;
            }

            .nav-item {
                padding: 12px 16px;
                border-radius: 12px;
                cursor: pointer;
                color: var(--text-secondary);
                font-weight: 500;
                margin-bottom: 8px;
                transition: all 0.2s ease;
                display: flex;
                align-items: center;
                gap: 12px;
            }

            .nav-item:hover, .nav-item.active {
                background: rgba(59, 130, 246, 0.1);
                color: var(--text-primary);
            }

            .nav-item.active {
                border: 1px solid rgba(59, 130, 246, 0.2);
            }

            .sidebar-footer {
                border-top: 1px solid var(--border-color);
                padding-top: 20px;
                text-align: center;
                font-size: 0.8rem;
                color: var(--text-secondary);
            }

            /* Main Workspace Area */
            .main-content {
                flex-grow: 1;
                display: flex;
                flex-direction: column;
                height: 100%;
                overflow: hidden;
                background: #06090f;
            }

            header {
                height: 70px;
                border-bottom: 1px solid var(--border-color);
                display: flex;
                align-items: center;
                justify-content: space-between;
                padding: 0 40px;
                background: var(--surface-color);
                flex-shrink: 0;
            }

            h2 {
                font-family: 'Outfit', sans-serif;
                font-weight: 700;
            }

            .btn {
                background: var(--accent-gradient);
                color: white;
                border: none;
                padding: 10px 20px;
                border-radius: 10px;
                font-weight: 600;
                cursor: pointer;
                transition: transform 0.2s ease, box-shadow 0.2s ease;
                font-family: 'Inter', sans-serif;
            }

            .btn:hover {
                transform: translateY(-2px);
                box-shadow: 0 4px 15px rgba(59, 130, 246, 0.4);
            }

            .btn-secondary {
                background: var(--surface-accent);
                border: 1px solid var(--border-color);
                color: var(--text-primary);
            }

            /* Dynamic Panels */
            .panel {
                display: none;
                flex-grow: 1;
                padding: 40px;
                overflow-y: auto;
            }

            .panel.active {
                display: flex;
                flex-direction: column;
            }

            /* Stats Grid Layout */
            .stats-grid {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
                gap: 24px;
                margin-bottom: 40px;
            }

            .stat-card {
                background: var(--surface-color);
                border: 1px solid var(--border-color);
                border-radius: 16px;
                padding: 24px;
                box-shadow: var(--shadow-primary);
                position: relative;
                overflow: hidden;
            }

            .stat-card::after {
                content: '';
                position: absolute;
                bottom: 0;
                left: 0;
                width: 100%;
                height: 4px;
                background: var(--accent-gradient);
            }

            .stat-title {
                color: var(--text-secondary);
                font-size: 0.85rem;
                text-transform: uppercase;
                letter-spacing: 0.05em;
                margin-bottom: 8px;
            }

            .stat-value {
                font-size: 2.2rem;
                font-weight: 800;
                font-family: 'Outfit', sans-serif;
            }

            /* Table Layout */
            .table-container {
                background: var(--surface-color);
                border: 1px solid var(--border-color);
                border-radius: 16px;
                overflow: hidden;
                box-shadow: var(--shadow-primary);
            }

            table {
                width: 100%;
                border-collapse: collapse;
                text-align: left;
            }

            th, td {
                padding: 16px 24px;
                border-bottom: 1px solid var(--border-color);
            }

            th {
                background: var(--surface-accent);
                color: var(--text-secondary);
                font-weight: 600;
                font-size: 0.85rem;
                text-transform: uppercase;
                letter-spacing: 0.05em;
            }

            tr:hover td {
                background: rgba(255, 255, 255, 0.02);
            }

            tr {
                cursor: pointer;
            }

            /* Search Form */
            .search-box {
                background: var(--surface-color);
                border: 1px solid var(--border-color);
                border-radius: 16px;
                padding: 24px;
                margin-bottom: 30px;
                box-shadow: var(--shadow-primary);
                display: flex;
                gap: 16px;
            }

            .input-search {
                flex-grow: 1;
                background: var(--surface-accent);
                border: 1px solid var(--border-color);
                border-radius: 10px;
                padding: 12px 16px;
                color: white;
                font-family: 'Inter', sans-serif;
                font-size: 1rem;
            }

            .input-search:focus {
                outline: none;
                border-color: var(--accent-blue);
            }

            /* Vector Search Results */
            .result-card {
                background: var(--surface-color);
                border: 1px solid var(--border-color);
                border-radius: 16px;
                padding: 24px;
                margin-bottom: 16px;
                box-shadow: var(--shadow-primary);
                transition: transform 0.2s ease;
            }

            .result-card:hover {
                transform: translateX(4px);
                border-color: rgba(59, 130, 246, 0.3);
            }

            .result-header {
                display: flex;
                justify-content: space-between;
                align-items: center;
                margin-bottom: 12px;
            }

            .result-title {
                font-family: 'Outfit', sans-serif;
                font-weight: 700;
                font-size: 1.1rem;
            }

            .score-tag {
                background: rgba(6, 182, 212, 0.1);
                color: var(--accent-cyan);
                padding: 4px 10px;
                border-radius: 99px;
                font-size: 0.8rem;
                font-weight: 600;
                border: 1px solid rgba(6, 182, 212, 0.2);
            }

            .result-meta {
                color: var(--text-secondary);
                font-size: 0.85rem;
                margin-bottom: 10px;
            }

            .result-summary {
                color: var(--text-secondary);
            }

            /* Newsletter Viewer Frame */
            .viewer-container {
                display: flex;
                height: 100%;
                gap: 20px;
            }

            .viewer-sidebar {
                width: 250px;
                background: var(--surface-color);
                border: 1px solid var(--border-color);
                border-radius: 16px;
                padding: 20px;
                display: flex;
                flex-direction: column;
                gap: 12px;
                overflow-y: auto;
                flex-shrink: 0;
            }

            .viewer-sidebar-title {
                font-family: 'Outfit', sans-serif;
                font-weight: 700;
                font-size: 1rem;
                margin-bottom: 10px;
                color: var(--text-primary);
            }

            .viewer-item {
                padding: 10px 12px;
                border-radius: 8px;
                cursor: pointer;
                font-size: 0.9rem;
                color: var(--text-secondary);
                background: var(--surface-accent);
                transition: background 0.2s ease, color 0.2s ease;
                white-space: nowrap;
                overflow: hidden;
                text-overflow: ellipsis;
            }

            .viewer-item:hover, .viewer-item.active {
                background: rgba(59, 130, 246, 0.1);
                color: var(--text-primary);
                border: 1px solid rgba(59, 130, 246, 0.2);
            }

            .viewer-main {
                flex-grow: 1;
                background: var(--surface-color);
                border: 1px solid var(--border-color);
                border-radius: 16px;
                padding: 40px;
                overflow-y: auto;
                box-shadow: var(--shadow-primary);
            }

            /* Toast Notification */
            .toast {
                position: fixed;
                bottom: 30px;
                right: 30px;
                background: var(--accent-gradient);
                color: white;
                padding: 16px 24px;
                border-radius: 12px;
                box-shadow: 0 10px 30px rgba(0,0,0,0.5);
                transform: translateY(150%);
                transition: transform 0.3s cubic-bezier(0.175, 0.885, 0.32, 1.275);
                z-index: 1000;
                font-weight: 600;
            }

            .toast.show {
                transform: translateY(0);
            }
        </style>
    </head>
    <body>
        <!-- Sidebar Navigation -->
        <div class="sidebar">
            <div class="logo">AI Newsletter Engine</div>
            <ul class="nav-menu">
                <li class="nav-item active" onclick="switchPanel('dashboard')">Console</li>
                <li class="nav-item" onclick="switchPanel('viewer')">Archive Viewer</li>
                <li class="nav-item" onclick="switchPanel('search')">Vector Search</li>
            </ul>
            <div class="sidebar-footer">
                <p>System status: Active</p>
                <p>Host: 127.0.0.1</p>
            </div>
        </div>

        <!-- Main Dashboard Workspace -->
        <div class="main-content">
            <header>
                <h2 id="header-title">Management Console</h2>
                <div style="display: flex; gap: 12px;">
                    <button class="btn btn-secondary" onclick="runManualPipeline()">Trigger Manual Run</button>
                </div>
            </header>

            <!-- Console Panel -->
            <div id="panel-dashboard" class="panel active">
                <div class="stats-grid">
                    <div class="stat-card">
                        <div class="stat-title">Unused Articles in Queue</div>
                        <div class="stat-value" id="stat-unused">0</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-title">Total Database Articles</div>
                        <div class="stat-value" id="stat-total">0</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-title">Published Issues</div>
                        <div class="stat-value" id="stat-newsletters">0</div>
                    </div>
                </div>

                <h3 style="margin-bottom: 20px; font-family: 'Outfit'; font-weight: 700;">Archived Briefs</h3>
                <div class="table-container">
                    <table>
                        <thead>
                            <tr>
                                <th>Date</th>
                                <th>Briefing Title</th>
                                <th>Actions</th>
                            </tr>
                        </thead>
                        <tbody id="briefs-table-body">
                            <!-- Newsletters will render here -->
                        </tbody>
                    </table>
                </div>
            </div>

            <!-- Archive Viewer Panel -->
            <div id="panel-viewer" class="panel">
                <div class="viewer-container">
                    <div class="viewer-sidebar" id="viewer-sidebar-list">
                        <div class="viewer-sidebar-title">Select Issue</div>
                        <!-- Date list dynamically loaded -->
                    </div>
                    <div class="viewer-main" id="viewer-iframe-container">
                        <div style="text-align: center; color: var(--text-secondary); margin-top: 100px;">
                            Select an issue from the archive sidebar to load its briefing.
                        </div>
                    </div>
                </div>
            </div>

            <!-- Vector Search Panel -->
            <div id="panel-search" class="panel">
                <div class="search-box">
                    <input type="text" id="search-input" class="input-search" placeholder="Query stored summaries semantically (e.g. 'GPU memory KV Cache' or 'quantization performance')...">
                    <button class="btn" onclick="executeSemanticSearch()">Query DB</button>
                </div>

                <div id="search-results-list" style="margin-top: 20px;">
                    <div style="text-align: center; color: var(--text-secondary); padding: 40px;">
                        Input a topic above and perform vector search.
                    </div>
                </div>
            </div>
        </div>

        <!-- Toast Notifications -->
        <div id="toast-notify" class="toast">Pipeline execution started in the background.</div>

        <!-- Dashboard Core Logic -->
        <script>
            // Panel switching
            function switchPanel(panelId) {
                // Remove active classes
                document.querySelectorAll('.panel').forEach(p => p.classList.remove('active'));
                document.querySelectorAll('.nav-item').forEach(i => i.classList.remove('active'));

                // Set active panel
                const targetPanel = document.getElementById('panel-' + panelId);
                targetPanel.classList.add('active');

                // Highlight correct nav item
                let navIdx = 0;
                if (panelId === 'viewer') navIdx = 1;
                else if (panelId === 'search') navIdx = 2;
                document.querySelectorAll('.nav-item')[navIdx].classList.add('active');

                // Update Header Title
                const titles = {
                    'dashboard': 'Management Console',
                    'viewer': 'Archive Briefings Viewer',
                    'search': 'Semantic Vector Search'
                };
                document.getElementById('header-title').textContent = titles[panelId];

                // Refresh states
                if (panelId === 'dashboard') {
                    fetchStats();
                    fetchNewsletters();
                } else if (panelId === 'viewer') {
                    loadArchiveSidebar();
                }
            }

            // Toast Alert
            function showToast(message) {
                const toast = document.getElementById('toast-notify');
                toast.textContent = message;
                toast.classList.add('show');
                setTimeout(() => {
                    toast.classList.remove('show');
                }, 4000);
            }

            // Stats loader
            async function fetchStats() {
                try {
                    const res = await fetch('/api/stats');
                    const data = await res.json();
                    document.getElementById('stat-unused').textContent = data.unused_articles;
                    document.getElementById('stat-total').textContent = data.total_articles;
                    document.getElementById('stat-newsletters').textContent = data.total_newsletters;
                } catch (e) {
                    console.error("Failed to load statistics: ", e);
                }
            }

            // Newsletters table loader
            async function fetchNewsletters() {
                try {
                    const res = await fetch('/api/newsletters');
                    const data = await res.json();
                    const tbody = document.getElementById('briefs-table-body');
                    
                    // Securely replace children
                    tbody.replaceChildren();
                    
                    if (data.length === 0) {
                        const tr = document.createElement('tr');
                        const td = document.createElement('td');
                        td.setAttribute('colspan', '3');
                        td.style.textAlign = 'center';
                        td.style.color = 'var(--text-secondary)';
                        td.textContent = 'No generated newsletters registered in DB. Please trigger a manual run.';
                        tr.appendChild(td);
                        tbody.appendChild(tr);
                        return;
                    }

                    data.forEach(item => {
                        const tr = document.createElement('tr');
                        
                        const tdDate = document.createElement('td');
                        tdDate.textContent = item.issue_date;
                        tdDate.style.fontWeight = '600';
                        
                        const tdTitle = document.createElement('td');
                        tdTitle.textContent = item.title;
                        
                        const tdActions = document.createElement('td');
                        const viewBtn = document.createElement('button');
                        viewBtn.className = 'btn btn-secondary';
                        viewBtn.style.padding = '6px 12px';
                        viewBtn.style.fontSize = '0.8rem';
                        viewBtn.textContent = 'Open Viewer';
                        viewBtn.onclick = (e) => {
                            e.stopPropagation();
                            switchPanel('viewer');
                            loadNewsletterIntoViewer(item.issue_date);
                        };
                        tdActions.appendChild(viewBtn);

                        tr.appendChild(tdDate);
                        tr.appendChild(tdTitle);
                        tr.appendChild(tdActions);
                        
                        tr.onclick = () => {
                            switchPanel('viewer');
                            loadNewsletterIntoViewer(item.issue_date);
                        };

                        tbody.appendChild(tr);
                    });
                } catch (e) {
                    console.error("Failed to fetch newsletters: ", e);
                }
            }

            // Trigger Manual Pipeline
            async function runManualPipeline() {
                showToast("Newsletter fetch & compile pipeline started in the background...");
                try {
                    const res = await fetch('/api/pipeline/run', { method: 'POST' });
                    const data = await res.json();
                    showToast("Pipeline is executing! Check console logs for live progress.");
                    setTimeout(() => {
                        fetchStats();
                        fetchNewsletters();
                    }, 5000);
                } catch (e) {
                    showToast("Failed to trigger pipeline manual run.");
                }
            }

            // Load dates into sidebar
            async function loadArchiveSidebar() {
                try {
                    const res = await fetch('/api/newsletters');
                    const data = await res.json();
                    const sidebar = document.getElementById('viewer-sidebar-list');
                    
                    // Securely clear but keep the title
                    const titleElement = sidebar.querySelector('.viewer-sidebar-title');
                    sidebar.replaceChildren(titleElement);

                    if (data.length === 0) {
                        const div = document.createElement('div');
                        div.style.fontSize = '0.85rem';
                        div.style.color = 'var(--text-secondary)';
                        div.textContent = 'No archives found.';
                        sidebar.appendChild(div);
                        return;
                    }

                    data.forEach(item => {
                        const div = document.createElement('div');
                        div.className = 'viewer-item';
                        div.textContent = item.issue_date + ': ' + item.title;
                        div.onclick = () => {
                            // Highlight item
                            document.querySelectorAll('.viewer-item').forEach(i => i.classList.remove('active'));
                            div.classList.add('active');
                            loadNewsletterIntoViewer(item.issue_date);
                        };
                        sidebar.appendChild(div);
                    });
                } catch (e) {
                    console.error("Failed to load archive list: ", e);
                }
            }

            // Load issue detail into viewer
            async function loadNewsletterIntoViewer(issueDate) {
                const container = document.getElementById('viewer-iframe-container');
                container.textContent = 'Loading Briefing Content...';
                
                try {
                    const res = await fetch('/api/newsletters/' + issueDate);
                    const data = await res.json();
                    
                    // Embed inside HTMLResponse using an iframe or direct HTML injection (fully sanitised as generated by the local engine)
                    const iframe = document.createElement('iframe');
                    iframe.style.width = '100%';
                    iframe.style.height = '700px';
                    iframe.style.border = 'none';
                    iframe.style.borderRadius = '12px';
                    iframe.style.background = 'var(--bg-color)';
                    
                    container.replaceChildren(iframe);
                    
                    const doc = iframe.contentDocument || iframe.contentWindow.document;
                    doc.open();
                    doc.write(data.content_html);
                    doc.close();
                } catch (e) {
                    container.textContent = 'Failed to load newsletter briefing content.';
                }
            }

            // Vector Search
            async function executeSemanticSearch() {
                const query = document.getElementById('search-input').value.trim();
                const container = document.getElementById('search-results-list');
                
                if (!query) {
                    showToast("Please input a search query.");
                    return;
                }

                container.textContent = 'Querying database using sentence-transformers vector embeddings...';
                
                try {
                    const res = await fetch('/api/search?q=' + encodeURIComponent(query));
                    const data = await res.json();
                    
                    container.replaceChildren();
                    
                    if (data.length === 0) {
                        const div = document.createElement('div');
                        div.style.textAlign = 'center';
                        div.style.color = 'var(--text-secondary)';
                        div.textContent = 'No matching articles or embeddings found. Ensure database contains parsed articles.';
                        container.appendChild(div);
                        return;
                    }

                    data.forEach(item => {
                        const card = document.createElement('div');
                        card.className = 'result-card';

                        const header = document.createElement('div');
                        header.className = 'result-header';

                        const title = document.createElement('div');
                        title.className = 'result-title';
                        title.textContent = item.article.title;

                        const score = document.createElement('div');
                        score.className = 'score-tag';
                        score.textContent = 'Score: ' + item.score;

                        header.appendChild(title);
                        header.appendChild(score);

                        const meta = document.createElement('div');
                        meta.className = 'result-meta';
                        meta.textContent = 'Source: ' + item.article.source + ' | Category: ' + (item.article.category || 'General') + ' | Date: ' + item.article.publish_date.split('T')[0];

                        const summary = document.createElement('div');
                        summary.className = 'result-summary';
                        summary.textContent = item.article.summary;

                        card.appendChild(header);
                        card.appendChild(meta);
                        card.appendChild(summary);

                        container.appendChild(card);
                    });
                } catch (e) {
                    container.textContent = 'Vector search query failed.';
                }
            }

            // Init dashboard
            fetchStats();
            fetchNewsletters();
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content, status_code=200)

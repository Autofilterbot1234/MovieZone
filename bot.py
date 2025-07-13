from flask import Flask, render_template_string, request, redirect, url_for, Response
from pymongo import MongoClient
from bson.objectid import ObjectId
import requests, os
from functools import wraps
from dotenv import load_dotenv
from datetime import datetime

# .env ফাইল থেকে এনভায়রনমেন্ট ভেরিয়েবল লোড করুন
load_dotenv()

app = Flask(__name__)

# Environment variables
MONGO_URI = os.getenv("MONGO_URI")
TMDB_API_KEY = os.getenv("TMDB_API_KEY")
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "password")

# --- অ্যাডমিন অথেন্টিকেশন ফাংশন ---
def check_auth(username, password):
    return username == ADMIN_USERNAME and password == ADMIN_PASSWORD

def authenticate():
    return Response(
    'Could not verify your access level for that URL.\n'
    'You have to login with proper credentials', 401,
    {'WWW-Authenticate': 'Basic realm="Login Required"'})

def requires_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.authorization
        if not auth or not check_auth(auth.username, auth.password):
            return authenticate()
        return f(*args, **kwargs)
    return decorated
# --- অথেন্টিকেশন শেষ ---

# Check if environment variables are set
if not MONGO_URI:
    print("Error: MONGO_URI environment variable must be set. Exiting.")
    exit(1)
if not TMDB_API_KEY:
    print("Warning: TMDB_API_KEY is not set. Movie details will not be auto-fetched.")

# Database connection
try:
    client = MongoClient(MONGO_URI)
    db = client["movie_db"]
    movies = db["movies"]
    settings = db["settings"]
    feedback = db["feedback"]
    print("Successfully connected to MongoDB!")
except Exception as e:
    print(f"Error connecting to MongoDB: {e}. Exiting.")
    exit(1)


# === Context Processor: সমস্ত টেমপ্লেটে বিজ্ঞাপনের কোড সহজলভ্য করার জন্য ===
@app.context_processor
def inject_ads():
    ad_codes = settings.find_one()
    return dict(ad_settings=(ad_codes or {}))


# --- START OF index_html TEMPLATE ---
# MODIFIED: Carousel is removed, replaced with a grid. Movie card CSS is changed.
index_html = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0, user-scalable=no" />
<title>MovieZone - Your Entertainment Hub</title>
<style>
  @import url('https://fonts.googleapis.com/css2?family=Bebas+Neue&family=Roboto:wght@400;500;700&display=swap');
  :root {
      --netflix-red: #E50914; --netflix-black: #141414;
      --text-light: #f5f5f5; --text-dark: #a0a0a0;
      --nav-height: 60px;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    font-family: 'Roboto', sans-serif; background-color: var(--netflix-black);
    color: var(--text-light); overflow-x: hidden;
  }
  a { text-decoration: none; color: inherit; }
  ::-webkit-scrollbar { width: 8px; }
  ::-webkit-scrollbar-track { background: #222; }
  ::-webkit-scrollbar-thumb { background: #555; }
  ::-webkit-scrollbar-thumb:hover { background: var(--netflix-red); }

  .main-nav {
      position: fixed; top: 0; left: 0; width: 100%; padding: 15px 50px;
      display: flex; justify-content: space-between; align-items: center; z-index: 100;
      transition: background-color 0.3s ease;
      background: linear-gradient(to bottom, rgba(0,0,0,0.8) 10%, rgba(0,0,0,0));
  }
  .main-nav.scrolled { background-color: var(--netflix-black); }
  .logo {
      font-family: 'Bebas Neue', sans-serif; font-size: 32px; color: var(--netflix-red);
      font-weight: 700; letter-spacing: 1px;
  }
  .search-input {
      background-color: rgba(0,0,0,0.7); border: 1px solid #777;
      color: var(--text-light); padding: 8px 15px; border-radius: 4px;
      transition: width 0.3s ease, background-color 0.3s ease; width: 250px;
  }
  .search-input:focus { background-color: rgba(0,0,0,0.9); border-color: var(--text-light); outline: none; }

  .tags-section {
    padding: 80px 50px 20px 50px;
    background-color: var(--netflix-black);
  }
  .tags-container {
    display: flex; flex-wrap: wrap;
    justify-content: center;
    gap: 10px;
  }
  .tag-link {
    padding: 6px 16px;
    background-color: rgba(255, 255, 255, 0.1);
    border: 1px solid #444; border-radius: 50px;
    font-weight: 500; font-size: 0.85rem;
    transition: background-color 0.3s, border-color 0.3s, color 0.3s;
  }
  .tag-link:hover { background-color: var(--netflix-red); border-color: var(--netflix-red); color: white; }

  .hero-section { height: 85vh; position: relative; color: white; overflow: hidden; }
  .hero-slide {
      position: absolute; top: 0; left: 0; width: 100%; height: 100%;
      background-size: cover; background-position: center top;
      display: flex; align-items: flex-end; padding: 50px;
      opacity: 0; transition: opacity 1.5s ease-in-out; z-index: 1;
  }
  .hero-slide.active { opacity: 1; z-index: 2; }
  .hero-slide::before {
      content: ''; position: absolute; top: 0; left: 0; right: 0; bottom: 0;
      background: linear-gradient(to top, var(--netflix-black) 10%, transparent 50%),
                  linear-gradient(to right, rgba(0,0,0,0.8) 0%, transparent 60%);
  }
  .hero-content { position: relative; z-index: 3; max-width: 50%; }
  .hero-title { font-family: 'Bebas Neue', sans-serif; font-size: 5rem; font-weight: 700; margin-bottom: 1rem; line-height: 1; }
  .hero-overview {
      font-size: 1.1rem; line-height: 1.5; margin-bottom: 1.5rem; max-width: 600px;
      display: -webkit-box; -webkit-line-clamp: 3; -webkit-box-orient: vertical; overflow: hidden;
  }
  .hero-buttons .btn {
      padding: 8px 20px;
      margin-right: 0.8rem;
      border: none; border-radius: 4px;
      font-size: 0.9rem;
      font-weight: 700; cursor: pointer; transition: opacity 0.3s ease;
      display: inline-flex; align-items: center; gap: 8px;
  }
  .btn.btn-primary { background-color: var(--netflix-red); color: white; }
  .btn.btn-secondary { background-color: rgba(109, 109, 110, 0.7); color: white; }
  .btn:hover { opacity: 0.8; }

  main { padding-top: 0; }
  .content-section { padding: 30px 50px; }
  .section-header {
      display: flex; justify-content: space-between; align-items: center;
      margin-bottom: 20px;
  }
  .section-title { font-family: 'Roboto', sans-serif; font-weight: 700; font-size: 1.6rem; margin: 0; }
  .see-all-link { color: var(--text-dark); font-weight: 700; font-size: 0.9rem; }
  
  .movie-grid {
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
      gap: 20px 15px;
  }

  .movie-card {
      background-color: transparent;
      cursor: pointer;
      display: block;
      transition: transform 0.2s ease-in-out;
  }
  .movie-card:hover { transform: scale(1.04); }
  .poster-container {
    position: relative;
    border-radius: 4px; overflow: hidden;
    margin-bottom: 10px;
    box-shadow: 0 4px 10px rgba(0,0,0,0.3);
  }
  .movie-poster {
      width: 100%;
      aspect-ratio: 2 / 3;
      object-fit: cover;
      display: block;
      background-color: #222;
  }
  .poster-badge {
    position: absolute; top: 10px; left: 10px; background-color: var(--netflix-red);
    color: white; padding: 5px 10px; font-size: 12px; font-weight: 700;
    border-radius: 4px; z-index: 3; box-shadow: 0 2px 5px rgba(0,0,0,0.5);
  }
  .card-title {
      font-size: 0.95rem; font-weight: 500;
      color: var(--text-light);
      white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
      text-align: left;
  }
  
  .full-page-grid-container { padding: 100px 50px 50px 50px; }
  .full-page-grid-title { font-size: 2.5rem; font-weight: 700; margin-bottom: 30px; }
  
  .bottom-nav {
      display: none; position: fixed; bottom: 0; left: 0; right: 0;
      height: var(--nav-height); background-color: #181818;
      border-top: 1px solid #282828; justify-content: space-around;
      align-items: center; z-index: 200;
  }
  .nav-item {
      display: flex; flex-direction: column; align-items: center;
      color: var(--text-dark); font-size: 10px; flex-grow: 1;
      padding: 5px 0; transition: color 0.2s ease;
  }
  .nav-item i { font-size: 20px; margin-bottom: 4px; }
  .nav-item.active { color: var(--text-light); }
  .nav-item.active .fa-home, .nav-item.active .fa-envelope, .nav-item.active .fa-layer-group { color: var(--netflix-red); }
  .ad-container { margin: 25px 50px; display: flex; justify-content: center; align-items: center; }

  .telegram-join-section {
    background-color: #181818; padding: 40px 20px;
    margin-top: 50px; text-align: center;
  }
  .telegram-join-section .telegram-icon {
    font-size: 4rem; color: #2AABEE; margin-bottom: 15px;
  }
  .telegram-join-section h2 {
    font-family: 'Bebas Neue', sans-serif; font-size: 2.5rem;
    color: var(--text-light); margin-bottom: 10px;
  }
  .telegram-join-section p {
    font-size: 1.1rem; color: var(--text-dark); max-width: 600px;
    margin: 0 auto 25px auto;
  }
  .telegram-join-button {
    display: inline-flex; align-items: center; gap: 10px;
    background-color: #2AABEE; color: white;
    padding: 12px 30px; border-radius: 50px;
    font-size: 1.1rem; font-weight: 700;
    transition: transform 0.2s ease, background-color 0.2s ease;
  }
  .telegram-join-button:hover { transform: scale(1.05); background-color: #1e96d1; }
  .telegram-join-button i { font-size: 1.3rem; }

  @media (max-width: 768px) {
      body { padding-bottom: var(--nav-height); }
      .main-nav { padding: 10px 15px; }
      .logo { font-size: 24px; }
      .search-input { width: 150px; }
      .tags-section { padding: 80px 15px 15px 15px; }
      .tag-link { padding: 6px 15px; font-size: 0.8rem; }
      .hero-section { height: 60vh; }
      .hero-slide { padding: 15px; align-items: center; }
      .hero-content { max-width: 90%; text-align: center; }
      .hero-title { font-size: 2.8rem; }
      .hero-overview { display: none; }
      .content-section { padding: 25px 15px; }
      .section-title { font-size: 1.2rem; }
      .movie-grid { grid-template-columns: repeat(auto-fill, minmax(110px, 1fr)); gap: 15px 10px; }
      .full-page-grid-container { padding: 80px 15px 30px; }
      .full-page-grid-title { font-size: 1.8rem; }
      .bottom-nav { display: flex; }
      .ad-container { margin: 25px 15px; }
      .telegram-join-section h2 { font-size: 2rem; }
      .telegram-join-section p { font-size: 1rem; }
  }
</style>
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.2.0/css/all.min.css">
</head>
<body>
<header class="main-nav">
  <a href="{{ url_for('home') }}" class="logo">MovieZone</a>
  <form method="GET" action="/" class="search-form">
    <input type="search" name="q" class="search-input" placeholder="Search..." value="{{ query|default('') }}" />
  </form>
</header>

<main>
  {% macro render_movie_card(m) %}
    <a href="{{ url_for('movie_detail', movie_id=m._id) }}" class="movie-card">
      <div class="poster-container">
        {% if m.poster_badge %}<div class="poster-badge">{{ m.poster_badge }}</div>{% endif %}
        <img class="movie-poster" loading="lazy" src="{{ m.poster or 'https://via.placeholder.com/400x600.png?text=No+Image' }}" alt="{{ m.title }}">
      </div>
      <h4 class="card-title">{{ m.title }}</h4>
    </a>
  {% endmacro %}

  {% if is_full_page_list %}
    <div class="full-page-grid-container">
      <h2 class="full-page-grid-title">{{ query }}</h2>
      {% if movies|length == 0 %}<p style="text-align:center; color: var(--text-dark); margin-top: 40px;">No content found.</p>
      {% else %}<div class="movie-grid">{% for m in movies %}{{ render_movie_card(m) }}{% endfor %}</div>{% endif %}
    </div>
  {% else %}
    {% if all_badges %}
    <div class="tags-section">
        <div class="tags-container">
            {% for badge in all_badges %}<a href="{{ url_for('movies_by_badge', badge_name=badge) }}" class="tag-link">{{ badge }}</a>{% endfor %}
        </div>
    </div>
    {% endif %}
    {% if recently_added %}
      <div class="hero-section">
        {% for movie in recently_added %}
          <div class="hero-slide {% if loop.first %}active{% endif %}" style="background-image: url('{{ movie.poster or '' }}');">
            <div class="hero-content">
              <h1 class="hero-title">{{ movie.title }}</h1>
              <p class="hero-overview">{{ movie.overview }}</p>
              <div class="hero-buttons">
                 {% if movie.watch_link and not movie.is_coming_soon %}<a href="{{ url_for('watch_movie', movie_id=movie._id) }}" class="btn btn-primary"><i class="fas fa-play"></i> Watch Now</a>{% endif %}
                <a href="{{ url_for('movie_detail', movie_id=movie._id) }}" class="btn btn-secondary"><i class="fas fa-info-circle"></i> More Info</a>
              </div>
            </div>
          </div>
        {% endfor %}
      </div>
    {% endif %}

    {% macro render_grid_section(title, movies_list, endpoint) %}
      {% if movies_list %}
      <section class="content-section">
        <div class="section-header">
          <h2 class="section-title">{{ title }}</h2>
          <a href="{{ url_for(endpoint) }}" class="see-all-link">See All ></a>
        </div>
        <div class="movie-grid">
            {% for m in movies_list %}
                {{ render_movie_card(m) }}
            {% endfor %}
        </div>
      </section>
      {% endif %}
    {% endmacro %}
    
    {{ render_grid_section('Trending Now', trending_movies, 'trending_movies') }}
    {% if ad_settings.banner_ad_code %}<div class="ad-container">{{ ad_settings.banner_ad_code|safe }}</div>{% endif %}
    {{ render_grid_section('Latest Movies', latest_movies, 'movies_only') }}
    {% if ad_settings.native_banner_code %}<div class="ad-container">{{ ad_settings.native_banner_code|safe }}</div>{% endif %}
    {{ render_grid_section('Web Series', latest_series, 'webseries') }}
    {{ render_grid_section('Recently Added', recently_added_full, 'recently_added_all') }}
    {{ render_grid_section('Coming Soon', coming_soon_movies, 'coming_soon') }}
    
    <div class="telegram-join-section">
        <i class="fa-brands fa-telegram telegram-icon"></i>
        <h2>Join Our Telegram Channel</h2>
        <p>Get the latest movie updates, news, and direct download links right on your phone!</p>
        <a href="https://t.me/+60goZWp-FpkxNzVl" target="_blank" class="telegram-join-button">
            <i class="fa-brands fa-telegram"></i> Join Main Channel
        </a>
    </div>
  {% endif %}
</main>

<nav class="bottom-nav">
  <a href="{{ url_for('home') }}" class="nav-item {% if request.endpoint == 'home' %}active{% endif %}"><i class="fas fa-home"></i><span>Home</span></a>
  <a href="{{ url_for('genres_page') }}" class="nav-item {% if request.endpoint == 'genres_page' %}active{% endif %}"><i class="fas fa-layer-group"></i><span>Genres</span></a>
  <a href="{{ url_for('movies_only') }}" class="nav-item {% if request.endpoint == 'movies_only' %}active{% endif %}"><i class="fas fa-film"></i><span>Movies</span></a>
  <a href="{{ url_for('webseries') }}" class="nav-item {% if request.endpoint == 'webseries' %}active{% endif %}"><i class="fas fa-tv"></i><span>Series</span></a>
  <a href="{{ url_for('contact') }}" class="nav-item {% if request.endpoint == 'contact' %}active{% endif %}"><i class="fas fa-envelope"></i><span>Request</span></a>
</nav>

<script>
    const nav = document.querySelector('.main-nav');
    window.addEventListener('scroll', () => { window.scrollY > 50 ? nav.classList.add('scrolled') : nav.classList.remove('scrolled'); });

    document.addEventListener('DOMContentLoaded', function() {
        const slides = document.querySelectorAll('.hero-slide');
        if (slides.length > 1) {
            let currentSlide = 0;
            const showSlide = (index) => slides.forEach((s, i) => s.classList.toggle('active', i === index));
            setInterval(() => { currentSlide = (currentSlide + 1) % slides.length; showSlide(currentSlide); }, 5000);
        }
    });
</script>
{% if ad_settings.popunder_code %}{{ ad_settings.popunder_code|safe }}{% endif %}
{% if ad_settings.social_bar_code %}{{ ad_settings.social_bar_code|safe }}{% endif %}
</body>
</html>
"""
# --- END OF index_html TEMPLATE ---


# --- বাকি টেমপ্লেটগুলো অপরিবর্তিত ---
genres_html = """...""" # আপনার আগের কোডের মতই থাকবে
detail_html = """...""" # আপনার আগের কোডের মতই থাকবে
watch_html = """...""" # আপনার আগের কোডের মতই থাকবে
admin_html = """...""" # আপনার আগের কোডের মতই থাকবে
edit_html = """...""" # আপনার আগের কোডের মতই থাকবে
contact_html = """...""" # আপনার আগের কোডের মতই থাকবে

# ----------------- Flask Routes (Final Version) -----------------

def get_tmdb_details_by_title(title, content_type):
    """
    NEW HELPER FUNCTION: Fetches TMDB data by title and content type.
    Returns a dictionary with details, or an empty dictionary on failure.
    """
    if not TMDB_API_KEY:
        return {}
    
    tmdb_type = "tv" if content_type == "series" else "movie"
    details = {}
    try:
        # Search for the content to get its TMDB ID
        search_url = f"https://api.themoviedb.org/3/search/{tmdb_type}?api_key={TMDB_API_KEY}&query={requests.utils.quote(title)}"
        search_res = requests.get(search_url, timeout=5).json()
        
        if not search_res.get("results"):
            print(f"No TMDB results found for '{title}'")
            return {}
            
        tmdb_id = search_res["results"][0].get("id")
        if not tmdb_id:
            return {}

        # Fetch detailed information using the ID
        detail_url = f"https://api.themoviedb.org/3/{tmdb_type}/{tmdb_id}?api_key={TMDB_API_KEY}"
        res = requests.get(detail_url, timeout=5).json()
        
        details["tmdb_id"] = tmdb_id
        if res.get("poster_path"):
            details["poster"] = f"https://image.tmdb.org/t/p/w500{res['poster_path']}"
        if res.get("overview"):
            details["overview"] = res["overview"]
        
        release_date = res.get("release_date") if tmdb_type == "movie" else res.get("first_air_date")
        if release_date:
            details["release_date"] = release_date
            
        if res.get("genres"):
            details["genres"] = [g['name'] for g in res.get("genres", [])]
        if res.get("vote_average"):
            details["vote_average"] = res.get("vote_average")
            
        print(f"Successfully fetched TMDB data for '{title}'.")
        return details
        
    except requests.RequestException as e:
        print(f"TMDb API error while fetching '{title}': {e}")
        return {}


def fetch_and_prepare_data(form):
    """
    NEW HELPER FUNCTION: Processes form data and fetches from TMDB if necessary.
    This is the core solution for the poster loading issue.
    """
    title = form.get("title")
    content_type = form.get("content_type", "movie")
    
    # Base data from form
    movie_data = {
        "title": title,
        "type": content_type,
        "is_trending": form.get("is_trending") == "true",
        "is_coming_soon": form.get("is_coming_soon") == "true",
        "poster_badge": form.get("poster_badge", "").strip(),
        "poster": form.get("poster_url", "").strip(),
        "overview": form.get("overview", "").strip(),
        "release_date": form.get("release_date", "").strip(),
        "genres": [g.strip() for g in form.get("genres", "").split(',') if g.strip()]
    }

    # If essential details are missing, fetch from TMDb
    if not movie_data["poster"] or not movie_data["overview"]:
        print(f"Manual details missing for '{title}'. Fetching from TMDb...")
        tmdb_data = get_tmdb_details_by_title(title, content_type)
        
        # Update movie_data with TMDB data, but only if the field was empty
        if not movie_data.get("poster"): movie_data["poster"] = tmdb_data.get("poster")
        if not movie_data.get("overview"): movie_data["overview"] = tmdb_data.get("overview")
        if not movie_data.get("release_date"): movie_data["release_date"] = tmdb_data.get("release_date")
        if not movie_data.get("genres"): movie_data["genres"] = tmdb_data.get("genres")
        # Always update tmdb_id and vote_average if available
        if tmdb_data.get("tmdb_id"): movie_data["tmdb_id"] = tmdb_data.get("tmdb_id")
        if tmdb_data.get("vote_average"): movie_data["vote_average"] = tmdb_data.get("vote_average")

    # Add links based on content type
    if content_type == "movie":
        movie_data["watch_link"] = form.get("watch_link", "")
        links = []
        if form.get("link_480p"): links.append({"quality": "480p", "url": form.get("link_480p")})
        if form.get("link_720p"): links.append({"quality": "720p", "url": form.get("link_720p")})
        if form.get("link_1080p"): links.append({"quality": "1080p", "url": form.get("link_1080p")})
        movie_data["links"] = links
    else:  # series
        episodes = []
        episode_numbers = form.getlist('episode_number[]')
        for i in range(len(episode_numbers)):
            ep_links = []
            if form.getlist('episode_link_480p[]')[i]:
                ep_links.append({"quality": "480p", "url": form.getlist('episode_link_480p[]')[i]})
            if form.getlist('episode_link_720p[]')[i]:
                ep_links.append({"quality": "720p", "url": form.getlist('episode_link_720p[]')[i]})
            
            episodes.append({
                "episode_number": int(episode_numbers[i]),
                "title": form.getlist('episode_title[]')[i],
                "watch_link": form.getlist('episode_watch_link[]')[i],
                "links": ep_links
            })
        movie_data["episodes"] = episodes
        
    return movie_data


def process_movie_list(movie_list):
    for item in movie_list:
        if '_id' in item: item['_id'] = str(item['_id'])
    return movie_list

@app.route('/')
def home():
    query = request.args.get('q')
    if query:
        movies_list = list(movies.find({"title": {"$regex": query, "$options": "i"}}).sort('_id', -1))
        # MODIFIED: Use the same grid for search results
        return render_template_string(index_html, movies=process_movie_list(movies_list), query=f'Results for "{query}"', is_full_page_list=True)
    
    all_badges = movies.distinct("poster_badge")
    all_badges = sorted([badge for badge in all_badges if badge])

    limit = 12 # MODIFIED: Changed from 18 to 12
    context = {
        "trending_movies": process_movie_list(list(movies.find({"is_trending": True, "is_coming_soon": {"$ne": True}}).sort('_id', -1).limit(limit))),
        "latest_movies": process_movie_list(list(movies.find({"type": "movie", "is_coming_soon": {"$ne": True}}).sort('_id', -1).limit(limit))),
        "latest_series": process_movie_list(list(movies.find({"type": "series", "is_coming_soon": {"$ne": True}}).sort('_id', -1).limit(limit))),
        "coming_soon_movies": process_movie_list(list(movies.find({"is_coming_soon": True}).sort('_id', -1).limit(limit))),
        "recently_added": process_movie_list(list(movies.find({"is_coming_soon": {"$ne": True}}).sort('_id', -1).limit(6))), # For hero slider
        "recently_added_full": process_movie_list(list(movies.find({"is_coming_soon": {"$ne": True}}).sort('_id', -1).limit(limit))),
        "is_full_page_list": False, "query": "", "all_badges": all_badges
    }
    return render_template_string(index_html, **context)

@app.route('/movie/<movie_id>')
def movie_detail(movie_id):
    try:
        movie = movies.find_one({"_id": ObjectId(movie_id)})
        if not movie: return "Content not found", 404
        
        # The old get_tmdb_details is no longer needed as data is fetched on creation
        # We can keep a simplified version for older content if needed, but for now we remove it
        movie['_id'] = str(movie['_id'])
        
        related_movies = []
        if movie.get("genres"):
            related_movies = list(movies.find({"genres": {"$in": movie["genres"]}, "_id": {"$ne": ObjectId(movie_id)}}).limit(12))
        if not related_movies:
            related_movies = list(movies.find({"_id": {"$ne": ObjectId(movie_id)}, "is_coming_soon": {"$ne": True}}).sort("_id", -1).limit(12))

        # We need a small function just for the trailer
        def get_trailer_key(tmdb_id, tmdb_type):
            if not TMDB_API_KEY or not tmdb_id: return None
            try:
                video_url = f"https://api.themoviedb.org/3/{tmdb_type}/{tmdb_id}/videos?api_key={TMDB_API_KEY}"
                video_res = requests.get(video_url, timeout=5).json()
                for v in video_res.get("results", []):
                    if v['type'] == 'Trailer' and v['site'] == 'YouTube': return v['key']
            except requests.RequestException: pass
            return None
        
        trailer_key = get_trailer_key(movie.get("tmdb_id"), "tv" if movie.get("type") == "series" else "movie")
        
        return render_template_string(detail_html, movie=movie, trailer_key=trailer_key, related_movies=process_movie_list(related_movies))
    except Exception as e:
        print(f"Error in movie_detail: {e}")
        return render_template_string(detail_html, movie=None, trailer_key=None, related_movies=[])


@app.route('/watch/<movie_id>')
def watch_movie(movie_id):
    try:
        movie = movies.find_one({"_id": ObjectId(movie_id)})
        if not movie: return "Content not found.", 404
        watch_link, title = movie.get("watch_link"), movie.get("title")
        episode_num = request.args.get('ep')
        if episode_num and movie.get('type') == 'series' and movie.get('episodes'):
            for ep in movie['episodes']:
                if str(ep.get('episode_number')) == episode_num:
                    watch_link, title = ep.get('watch_link'), f"{title} - E{episode_num}: {ep.get('title')}"
                    break
        if watch_link: return render_template_string(watch_html, watch_link=watch_link, title=title)
        return "Watch link not found for this content.", 404
    except Exception as e:
        print(f"Watch page error: {e}")
        return "An error occurred.", 500

@app.route('/contact', methods=['GET', 'POST'])
def contact():
    if request.method == 'POST':
        feedback_data = {
            "type": request.form.get("type"), "content_title": request.form.get("content_title"),
            "message": request.form.get("message"), "email": request.form.get("email", "").strip(),
            "reported_content_id": request.form.get("reported_content_id"), "timestamp": datetime.utcnow()
        }
        feedback.insert_one(feedback_data)
        return render_template_string(contact_html, message_sent=True)
    prefill_title, prefill_id = request.args.get('title', ''), request.args.get('report_id', '')
    prefill_type = 'Problem Report' if prefill_id else 'Movie Request'
    return render_template_string(contact_html, message_sent=False, prefill_title=prefill_title, prefill_id=prefill_id, prefill_type=prefill_type)

@app.route('/admin', methods=["GET", "POST"])
@requires_auth
def admin():
    if request.method == "POST":
        if 'title' in request.form:
            # MODIFIED: Use the new helper function to prepare data
            movie_data = fetch_and_prepare_data(request.form)
            movies.insert_one(movie_data)
            print(f"Added new content: '{movie_data['title']}'")
        return redirect(url_for('admin'))
    
    all_content = process_movie_list(list(movies.find().sort('_id', -1)))
    feedback_list = process_movie_list(list(feedback.find().sort('timestamp', -1)))
    return render_template_string(admin_html, all_content=all_content, feedback_list=feedback_list)

@app.route('/admin/save_ads', methods=['POST'])
@requires_auth
def save_ads():
    ad_codes = { "popunder_code": request.form.get("popunder_code", ""), "social_bar_code": request.form.get("social_bar_code", ""), "banner_ad_code": request.form.get("banner_ad_code", ""), "native_banner_code": request.form.get("native_banner_code", "") }
    settings.update_one({}, {"$set": ad_codes}, upsert=True)
    return redirect(url_for('admin'))

@app.route('/edit_movie/<movie_id>', methods=["GET", "POST"])
@requires_auth
def edit_movie(movie_id):
    movie_obj = movies.find_one({"_id": ObjectId(movie_id)})
    if not movie_obj: return "Movie not found", 404
    
    if request.method == "POST":
        # MODIFIED: Use the helper function for updates as well
        update_data = fetch_and_prepare_data(request.form)
        
        # Clear fields that are not relevant for the new content type
        if update_data['type'] == 'movie':
            movies.update_one({"_id": ObjectId(movie_id)}, {"$unset": {"episodes": ""}})
        else: # series
            movies.update_one({"_id": ObjectId(movie_id)}, {"$unset": {"links": "", "watch_link": ""}})
            
        movies.update_one({"_id": ObjectId(movie_id)}, {"$set": update_data})
        print(f"Updated content: '{update_data['title']}'")
        return redirect(url_for('admin'))
    
    movie_obj['_id'] = str(movie_obj['_id'])
    return render_template_string(edit_html, movie=movie_obj)

@app.route('/delete_movie/<movie_id>')
@requires_auth
def delete_movie(movie_id):
    movies.delete_one({"_id": ObjectId(movie_id)})
    return redirect(url_for('admin'))

@app.route('/feedback/delete/<feedback_id>')
@requires_auth
def delete_feedback(feedback_id):
    feedback.delete_one({"_id": ObjectId(feedback_id)})
    return redirect(url_for('admin'))

def render_full_list(content_list, title):
    return render_template_string(index_html, movies=process_movie_list(content_list), query=title, is_full_page_list=True)

@app.route('/badge/<badge_name>')
def movies_by_badge(badge_name):
    return render_full_list(list(movies.find({"poster_badge": badge_name}).sort('_id', -1)), f'Tag: {badge_name}')

@app.route('/genres')
def genres_page():
    all_genres = movies.distinct("genres")
    all_genres = sorted([g for g in all_genres if g])
    return render_template_string(genres_html, genres=all_genres, title="Browse by Genre")

@app.route('/genre/<genre_name>')
def movies_by_genre(genre_name):
    return render_full_list(list(movies.find({"genres": genre_name}).sort('_id', -1)), f'Genre: {genre_name}')

@app.route('/trending_movies')
def trending_movies():
    return render_full_list(list(movies.find({"is_trending": True, "is_coming_soon": {"$ne": True}}).sort('_id', -1)), "Trending Now")

@app.route('/movies_only')
def movies_only():
    return render_full_list(list(movies.find({"type": "movie", "is_coming_soon": {"$ne": True}}).sort('_id', -1)), "All Movies")

@app.route('/webseries')
def webseries():
    return render_full_list(list(movies.find({"type": "series", "is_coming_soon": {"$ne": True}}).sort('_id', -1)), "All Web Series")

@app.route('/coming_soon')
def coming_soon():
    return render_full_list(list(movies.find({"is_coming_soon": True}).sort('_id', -1)), "Coming Soon")

@app.route('/recently_added')
def recently_added_all():
    return render_full_list(list(movies.find({"is_coming_soon": {"$ne": True}}).sort('_id', -1)), "Recently Added")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=False)

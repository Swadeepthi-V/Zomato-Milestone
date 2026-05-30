# Google Stitch UI Prompt: Premium CulinaryMind Interface (Multi-Screen Flow)

Below is the highly detailed design and frontend generation prompt for Google Stitch to generate a state-of-the-art, multi-screen UI for **CulinaryMind** (Zomato-Milestone recommendation system).

***

```markdown
# Role & Context
You are a principal frontend designer and developer. Generate a premium, state-of-the-art multi-screen web application interface named "CulinaryMind" – an AI-powered Zomato recommendation service. The system combines structured local restaurant catalog filtering with real-time Groq LLM reasoning to output grounded, hyper-personalized, and explainable recommendations.

---

# 🎨 Brand & Design Aesthetics
- **Theme**: Premium dark mode. Use a curated dark color palette (deep charcoals `#0F0F12`, obsidian blacks, and midnight slate) instead of flat `#000`.
- **Accents & Gradients**: High-energy culinary gradients – warm orange-red to bright amber (representing flame, spices, and premium dining) like `linear-gradient(135deg, #FF416C 0%, #FF4B2B 100%)`.
- **Materiality & Glassmorphism**: Use frosted-glass panels (`backdrop-filter: blur(16px)`), subtle translucent borders (`rgba(255,255,255,0.08)`), dynamic inner glows, and soft neon shadow elevations.
- **Typography**: Clean, premium sans-serif typography. Import "Outfit" or "Plus Jakarta Sans" from Google Fonts. 
- **Transitions**: Silky-smooth cross-fade or slide animations when moving between Screen 1 and Screen 2 to create an immersive, app-like experience.

---

# 📱 Screen Flow & Architecture
The application must consist of **at least 2 distinct screens** or interactive views with state transitions:

## 🖥️ Screen 1: The Preference Input Console (Home Screen)
This screen is clean and focused entirely on capturing user preferences.
- **Header Section**:
  - Elegant logo badge and system status label (e.g. "Groq RAG Pipeline Active").
  - Catchy H1 heading: "CulinaryMind" with a glowing text gradient.
  - A concise, premium subtitle: "Structured local catalog filtering meets explainable AI curation."
- **Quick Presets Panel**:
  - 3 beautifully designed mini preset cards that allow users to quick-fill their settings. Each card has distinct culinary icons and soft border glows:
    - **Preset 1 (Romantic Bangalore)**: "Bangalore • Medium budget • 4.0+ rating • Italian cuisine with a fine dining feel"
    - **Preset 2 (Spicy Hyderabad)**: "Hyderabad • Low budget • 4.2+ rating • Biryani & North Indian in Madhapur/Miyapur"
    - **Preset 3 (Premium Coastal)**: "Mumbai • High budget • 4.5+ rating • Continental rooftop vibes"
  - *Clicking a preset automatically populates the form and smoothly triggers the submission transition to Screen 2.*
- **Frosted Preference Console (Glassmorphic Form)**:
  - **Location Search**: Autocomplete drop-down. Needs to support dynamic locations populated from the backend `/locations` endpoint, supporting Bangalore areas (Indiranagar, Bellandur, etc.) and Hyderabad areas (Madhapur, Bachupally, Miyapur, Suchitra, etc.).
  - **Budget Selection**: Modern, segmented radio cards (buttons) for "LOW", "MEDIUM", and "HIGH" instead of traditional radios.
  - **Cuisine Selector**: Premium tag list or clean search box for specific cuisines (Italian, Biryani, South Indian, North Indian, etc.).
  - **Minimum Rating Slider**: Custom range slider (from 1.0 to 5.0 in increments of 0.1) with real-time value text display.
  - **Additional Preferences (AI Textarea)**: A prominent, neon-bordered text area for natural language constraints (e.g. "rooftop terrace view, kid-friendly, authentic wood-fired oven").
- **CTA Actions**:
  - A large, primary "Curate Recommendations" button with a glowing background gradient that animates on hover. Clicking it validates the inputs and transitions to the loading sequence.

---

## ⏳ Transition State: The Real-time RAG Pipeline Loader
When the form is submitted, Screen 1 hides and this high-fidelity loading container becomes active with a glowing progress circle:
- Display animated progress checkmarks for 3 sequential pipeline stages:
  - 🔍 **Stage 1**: "Querying Catalog..." — Filtering active candidate sets in selected location.
  - 🏷️ **Stage 2**: "RAG Matrix Filtering..." — Narrowing down candidates based on budget, cuisine, and rating constraints.
  - 🤖 **Stage 3**: "Invoking Groq LLM..." — Synthesizing and ranking top recommendations with grounded, explainable rationales.
- *Once the API response returns, this loading state smoothly cross-fades into Screen 2.*

---

## 🖥️ Screen 2: The Curated Curation Dashboard (Results Screen)
This screen is completely dedicated to displaying the rich results from the recommendation engine.
- **Top Summary Banner**:
  - A high-impact frosted text banner displaying the LLM's natural-language selection summary paragraph (e.g., "Three strong Italian options in Bangalore for families...").
- **Curated Results Grid**:
  - A beautifully spaced grid showing the top 3-5 recommendation cards:
    - Large **Rank Badge** (e.g., #1, #2, #3) in a high-contrast gradient circle overlapping the card edge.
    - **Title Row**: Restaurant name, colored rating badge (with gold star icon), and clickable link vector.
    - **Meta Tags**: Beautiful pill badges showing the restaurant's cuisine, estimated cost, and specific neighborhood area.
    - **AI Explanation Box**: A dedicated, callout panel containing the natural-language justification. Use a distinct subtle background and typography so the AI rationale is immediately readable and prioritized.
- **Pipeline Telemetry Footer (JSON Metadata Badges)**:
  - A clean, modern stats bar below the grid displaying technical metrics returned by the API metadata block:
    - **Engine**: Groq (e.g. `llama-3.3-70b-versatile`)
    - **Candidates Scanned**: Count (e.g. `30 candidates filtered`)
    - **Latency**: Total milliseconds (e.g. `840 ms`)
    - **Hallucinations Dropped**: Zero-trust grounding count
- **Action Toolbar**:
  - A prominent "Modify Preferences" button with an arrow-back icon that smoothly transitions back to Screen 1 (preserving the user's previously filled-in form fields).
  - A "Start New Search" button that clears fields and returns to Screen 1.

---

# 💻 Code & API Contract Requirements
Generate a single-file semantic HTML structure (`index.html`) styling with custom-property CSS (`style.css`), and lightweight JS logic (`app.js`) that binds form values and handles communication seamlessly:
- **GET `/locations`**: Fetches list of cities/areas to populate the autocomplete dropdown.
- **POST `/recommend`**: Sends JSON payload on submit containing:
  ```json
  {
    "location": "Madhapur",
    "budget": "medium",
    "cuisine": "Biryani",
    "min_rating": 4.0,
    "additional_preferences": "spicy tandoori, seating view",
    "top_k": 5
  }
  ```
- **API Response Shape**:
  ```json
  {
    "summary": "AI summary text...",
    "recommendations": [
      {
        "rank": 1,
        "restaurant": {
          "id": "r_1a2b3c",
          "name": "Bawarchi",
          "location": "Hyderabad",
          "cuisine": "Biryani, North Indian",
          "cost": "₹600 for two",
          "rating": 4.5
        },
        "explanation": "Custom RAG explanation..."
      }
    ],
    "meta": {
      "candidate_count": 12,
      "model": "llama-3.3-70b-versatile",
      "latency_ms": 1200
    }
  }
  ```

Return the complete HTML structure, CSS custom properties, and vanilla JS so it can drop directly into the project's static assets folder without external framework build requirements.
```

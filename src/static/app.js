/* ==========================================================================
   CulinaryMind — Core JavaScript Controller
   ========================================================================== */

document.addEventListener("DOMContentLoaded", () => {
    // DOM Cache
    const form = document.getElementById("recommendation-form");
    const locationInput = document.getElementById("location-input");
    const cuisineInput = document.getElementById("cuisine-input");
    const ratingInput = document.getElementById("rating-input");
    const ratingVal = document.getElementById("rating-val");
    const additionalInput = document.getElementById("additional-input");
    const submitBtn = document.getElementById("submit-btn");
    const resetBtn = document.getElementById("reset-btn");

    const presetsPanel = document.getElementById("presets-panel");
    const filtersSummary = document.getElementById("filters-summary");
    const loadingState = document.getElementById("loading-state");
    const loadingStageTitle = document.getElementById("loading-stage-title");
    const loadingStageDesc = document.getElementById("loading-stage-desc");
    const resultsOutput = document.getElementById("results-output");
    const emptyState = document.getElementById("empty-state");
    const emptyStateMessage = document.getElementById("empty-state-message");
    const emptyResetBtn = document.getElementById("empty-reset-btn");

    const recommendationsGrid = document.getElementById("recommendations-grid");
    const selectionSummary = document.getElementById("selection-summary");
    const selectionSummaryContainer = document.getElementById("selection-summary-container");
    const resultsMetaBadge = document.getElementById("results-meta-badge");

    const metaEngine = document.getElementById("meta-engine");
    const metaCandidates = document.getElementById("meta-candidates");
    const metaLatency = document.getElementById("meta-latency");

    const tagLocation = document.getElementById("tag-location");
    const tagBudget = document.getElementById("tag-budget");
    const tagCuisine = document.getElementById("tag-cuisine");
    const tagCuisineWrapper = document.getElementById("tag-cuisine-wrapper");
    const tagRating = document.getElementById("tag-rating");
    const tagRatingWrapper = document.getElementById("tag-rating-wrapper");

    // Dynamic Locations Data (populated on load from backend)
    let popularLocations = [
        "Bangalore", "Delhi", "Mumbai", "Kolkata", "Chennai",
        "Hyderabad", "Pune", "Noida", "Gurgaon", "New Delhi"
    ];

    async function loadUniqueLocations() {
        try {
            const response = await fetch("/locations");
            if (response.ok) {
                const locations = await response.json();
                if (Array.isArray(locations) && locations.length > 0) {
                    popularLocations = locations;
                }
            }
        } catch (error) {
            console.warn("Failed to load dynamic location list, falling back to static cities:", error);
        }
        populateLocationSelect();
    }

    function populateLocationSelect() {
        locationInput.innerHTML = '<option value="" disabled selected>Select a location...</option>';
        popularLocations.forEach(loc => {
            const opt = document.createElement("option");
            opt.value = loc;
            opt.textContent = loc;
            locationInput.appendChild(opt);
        });
    }
    loadUniqueLocations();

    // Setup Rating Slider Feedback
    ratingInput.addEventListener("input", (e) => {
        ratingVal.textContent = parseFloat(e.target.value).toFixed(1);
    });

    // Preset Configurations
    const presets = {
        "1": {
            location: "Bangalore",
            budget: "medium",
            cuisine: "Italian",
            min_rating: 4.0,
            additional: "highly rated pasta, authentic stone baked pizza, romantic atmosphere"
        },
        "2": {
            location: "Delhi",
            budget: "low",
            cuisine: "North Indian",
            min_rating: 3.8,
            additional: "spicy chicken tikka, street side dhabha style, casual dining"
        },
        "3": {
            location: "Mumbai",
            budget: "high",
            cuisine: "Continental",
            min_rating: 4.2,
            additional: "beautiful rooftop scenery, premium fine dining view, signature cocktails"
        }
    };

    // Preset Card Clicking
    document.querySelectorAll(".preset-card").forEach(card => {
        card.addEventListener("click", () => {
            const id = card.getAttribute("data-preset");
            const config = presets[id];
            if (config) {
                locationInput.value = config.location;
                document.querySelector(`input[name="budget"][value="${config.budget}"]`).checked = true;
                cuisineInput.value = config.cuisine;
                ratingInput.value = config.min_rating;
                ratingVal.textContent = parseFloat(config.min_rating).toFixed(1);
                additionalInput.value = config.additional;

                // Automatically submit the query
                triggerCuration();
            }
        });
    });

    // Form Reset Handles
    function clearForm() {
        form.reset();
        ratingVal.textContent = "4.0";
        hideResultsAndStates();
        presetsPanel.classList.remove("hidden");
    }

    resetBtn.addEventListener("click", clearForm);
    emptyResetBtn.addEventListener("click", clearForm);

    // Hide all outputs
    function hideResultsAndStates() {
        presetsPanel.classList.add("hidden");
        filtersSummary.classList.add("hidden");
        loadingState.classList.add("hidden");
        resultsOutput.classList.add("hidden");
        emptyState.classList.add("hidden");
    }

    // Submit handler
    form.addEventListener("submit", (e) => {
        e.preventDefault();
        triggerCuration();
    });

    // Pipeline runner
    async function triggerCuration() {
        const location = locationInput.value.trim();
        const budget = document.querySelector('input[name="budget"]:checked').value;
        const cuisine = cuisineInput.value.trim();
        const minRating = parseFloat(ratingInput.value);
        const additional = additionalInput.value.trim();

        if (!location) {
            alert("Please enter a valid location.");
            locationInput.focus();
            return;
        }

        // 1. Prepare UI States
        hideResultsAndStates();
        loadingState.classList.remove("hidden");

        // 2. Set Filter Badges
        tagLocation.textContent = location;
        tagBudget.textContent = budget.toUpperCase();

        if (cuisine) {
            tagCuisine.textContent = cuisine;
            tagCuisineWrapper.classList.remove("hidden");
        } else {
            tagCuisineWrapper.classList.add("hidden");
        }

        tagRating.textContent = `≥ ${minRating.toFixed(1)}`;
        filtersSummary.classList.remove("hidden");

        // 3. Build API Payload
        const payload = {
            location: location,
            budget: budget,
            cuisine: cuisine || "",
            min_rating: minRating,
            additional_preferences: additional || null,
            top_k: 5
        };

        // Simulated Stage Changes in Loading Box (Enhances AI RAG visibility)
        const stages = [
            { title: "Querying Restaurant Catalog...", desc: `Filtering candidate sets in ${location} matches` },
            { title: "RAG Candidate Reduction...", desc: "Filtering cuisine tags and ratings matrix" },
            { title: "Invoking Groq LLM Inference...", desc: "Synthesizing customized AI explanations" }
        ];

        let stageIdx = 0;
        const stageInterval = setInterval(() => {
            if (stageIdx < stages.length - 1) {
                stageIdx++;
                loadingStageTitle.textContent = stages[stageIdx].title;
                loadingStageDesc.textContent = stages[stageIdx].desc;
            }
        }, 800);

        try {
            // Trigger API Request
            const response = await fetch("/recommend", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload)
            });

            clearInterval(stageInterval);

            if (response.status === 422) {
                const errData = await response.json();
                const detail = errData.detail ? JSON.stringify(errData.detail) : "Invalid input parameters.";
                throw new Error(`Validation Error (422): ${detail}`);
            }

            if (!response.ok) {
                const errData = await response.json().catch(() => ({}));
                throw new Error(errData.detail || `Server error (${response.status})`);
            }

            const data = await response.json();

            // 4. Render recommendations
            renderResults(data);

        } catch (error) {
            clearInterval(stageInterval);
            console.error("Curation Fetch Error:", error);

            // Render Failure State
            loadingState.classList.add("hidden");
            emptyStateMessage.textContent = `Communication error: ${error.message}. Ensure your backend server is active.`;
            emptyState.classList.remove("hidden");
        }
    }

    // Results Renderer
    function renderResults(data) {
        loadingState.classList.add("hidden");
        recommendationsGrid.innerHTML = "";

        // Empty filter state check
        if (!data.recommendations || data.recommendations.length === 0) {
            emptyStateMessage.textContent = data.message || "No restaurants match your filters. Try widening search parameters.";
            emptyState.classList.remove("hidden");
            return;
        }

        // Display optional LLM curated summary
        if (data.summary) {
            selectionSummary.textContent = data.summary;
            selectionSummaryContainer.classList.remove("hidden");
        } else {
            selectionSummaryContainer.classList.add("hidden");
        }

        // Render Cards
        data.recommendations.forEach(rec => {
            const r = rec.restaurant;
            const card = document.createElement("div");
            card.className = "rec-card";

            // Format rating stars
            const ratingScore = r.rating ? r.rating.toFixed(1) : "N/A";

            // Format cost
            const costStr = r.cost ? r.cost : "N/A";

            card.innerHTML = `
                <div class="rank-badge">${rec.rank}</div>
                <div class="rec-content">
                    <div class="rec-main-info">
                        <div class="rec-title-row">
                            <h3 class="rec-name">${escapeHtml(r.name)}</h3>
                            <span class="rating-badge"><i class="fa-solid fa-star"></i> ${ratingScore}</span>
                        </div>
                        <div class="rec-meta-tags">
                            <span class="tag tag-cuisine"><i class="fa-solid fa-utensils"></i> ${escapeHtml(r.cuisine)}</span>
                            <span class="tag tag-cost"><i class="fa-solid fa-wallet"></i> ${escapeHtml(costStr)}</span>
                            <span class="tag tag-cost"><i class="fa-solid fa-location-pin"></i> ${escapeHtml(r.location)}</span>
                        </div>
                    </div>
                    <div class="ai-explanation">
                        <p>${escapeHtml(rec.explanation)}</p>
                    </div>
                </div>
            `;
            recommendationsGrid.appendChild(card);
        });

        // Set Metadata Block
        const meta = data.meta || {};
        resultsMetaBadge.textContent = `${data.recommendations.length} matching curated`;
        metaEngine.innerHTML = `<i class="fa-solid fa-microchip"></i> Engine: <span>${meta.model || "N/A"}</span>`;
        metaCandidates.innerHTML = `<i class="fa-solid fa-database"></i> Candidates parsed: <span>${meta.candidate_count || 0}</span>`;

        const latency = meta.latency_ms !== undefined ? `${meta.latency_ms} ms` : "N/A";
        metaLatency.innerHTML = `<i class="fa-solid fa-stopwatch"></i> Latency: <span>${latency}</span>`;

        resultsOutput.classList.remove("hidden");
    }

    // HTML Sanitizer utility
    function escapeHtml(unsafe) {
        if (!unsafe) return "";
        return unsafe
            .toString()
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#039;");
    }
});

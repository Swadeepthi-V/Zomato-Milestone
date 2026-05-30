# Project Context: AI-Powered Restaurant Recommendation System

## Overview

Build an AI-powered restaurant recommendation service inspired by Zomato. The system suggests restaurants based on user preferences by combining structured restaurant data with a Large Language Model (LLM) to produce personalized, human-like recommendations.

## Objectives

The application must:

1. Accept user preferences (location, budget, cuisine, ratings, and optional constraints).
2. Use a real-world restaurant dataset for grounding recommendations.
3. Leverage an LLM to generate personalized, explainable suggestions.
4. Present clear, useful results to the user.

## Data Source

| Item | Detail |
|------|--------|
| Dataset | Zomato restaurant data on Hugging Face |
| URL | https://huggingface.co/datasets/ManikaSaini/zomato-restaurant-recommendation |
| Relevant fields | Restaurant name, location, cuisine, cost, rating, and related metadata |

### Data Ingestion

- Load and preprocess the dataset from Hugging Face.
- Extract and normalize fields needed for filtering and display.

## User Input

Collect the following preferences:

| Field | Examples |
|-------|----------|
| Location | Delhi, Bangalore |
| Budget | low, medium, high |
| Cuisine | Italian, Chinese |
| Minimum rating | Numeric threshold |
| Additional preferences | family-friendly, quick service, etc. |

## System Workflow

```
┌─────────────┐     ┌──────────────┐     ┌──────────────────┐     ┌─────────────┐
│ Data        │────▶│ User Input   │────▶│ Integration      │────▶│ LLM         │
│ Ingestion   │     │ Collection   │     │ Layer (filter +  │     │ Recommendation│
└─────────────┘     └──────────────┘     │ prompt)          │     │ Engine      │
                                         └──────────────────┘     └──────┬──────┘
                                                                          │
                                                                          ▼
                                                                   ┌─────────────┐
                                                                   │ Output      │
                                                                   │ Display     │
                                                                   └─────────────┘
```

### 1. Data Ingestion

Load, clean, and prepare restaurant records from the Hugging Face dataset.

### 2. User Input

Gather structured preferences from the user (see table above).

### 3. Integration Layer

- Filter restaurant data according to user preferences.
- Prepare a structured subset of candidates for the LLM.
- Design a prompt that enables the LLM to reason over and rank options.

### 4. Recommendation Engine

Use the LLM to:

- Rank restaurants against user preferences.
- Explain why each recommendation fits.
- Optionally summarize the overall set of choices.

### 5. Output Display

Present top recommendations in a user-friendly format. Each result should include:

| Field | Description |
|-------|-------------|
| Restaurant Name | Name of the venue |
| Cuisine | Cuisine type(s) |
| Rating | User or aggregate rating |
| Estimated Cost | Cost indicator or range |
| AI-generated explanation | Why this restaurant matches the user’s preferences |

## Design Considerations

- **Grounding**: Recommendations should be driven by filtered dataset rows, not invented venues.
- **Prompt design**: The integration layer prompt should pass structured candidate data and explicit user criteria so the LLM can rank and justify choices.
- **Transparency**: Explanations should tie back to stated preferences (location, budget, cuisine, rating, extras).
- **UX**: Output should be scannable and actionable for end users.

## Success Criteria

- User preferences correctly narrow the candidate set from the Zomato dataset.
- The LLM returns ranked recommendations with clear, preference-aware explanations.
- Results are displayed consistently with name, cuisine, rating, cost, and explanation per item.

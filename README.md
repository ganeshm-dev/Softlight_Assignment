# AI Automation Agent — Softlight Assessment

This project is part of the **Softlight Assignment**, demonstrating an **autonomous browser automation system** built using **Gemini + Playwright**.

It takes **natural-language instructions** like:
> “Create a new project in Linear named *AI Test Project*”
and executes them automatically inside a **real browser** — handling login, navigation, and UI interaction.

## Overview

This system combines **LLM reasoning** and **browser automation**:
- Understands the user’s natural-language task
- Determines the base domain and correct login URL
- Injects cookies (if available) or navigates to `/login`
- Generates task-specific URLs via Gemini
- Executes structured UI actions automatically

## Architecture Flow
User Task  -->  Gemini (LLM reasoning + planning)  -->  URL Detection (base + login + task)  -->  Playwright (browser control + cookies)  -->  Action Execution + JSON Report

## Setup Instructions

### 1. Clone the Repository
```bash
git clone https://github.com/ganeshm-dev/Softlight_Assignment.git
cd Softlight_Assignment

###  2. Create and Activate Virtual Environment 
python -m venv venv
venv\Scripts\activate

### 3. Install Dependencies
pip install -r requirements.txt

### 4. Run Example Tasks
**Linear Tasks**
python -m Code.main --task "Create a new project in Linear named 'AI Test Project'" --outdir .\Dataset\Linear\Task1
python -m Code.main --task "Assign issue 'Backend Integration' to user 'Ganesh'" --outdir .\Dataset\Linear\Task2

**Notion Tasks**
python -m Code.main --task "Create a new page in Notion titled 'Automation Summary'" --outdir .\Dataset\Notion\Task1
python -m Code.main --task "Create a new database in Notion titled 'Automation Logs'" --outdir .\Dataset\Notion\Task2
python -m Code.main --task "Add a row in Notion database 'Automation Logs' with title 'Test Case 1'" --outdir .\Dataset\Notion\Task3


### How It Works

- Agent asks Gemini for the base site URL (e.g., https://linear.app).
- If cookies exist — direct navigation to dashboard.
- If not, it appends /login automatically.
- After login, agent requests Gemini to generate a task-specific URL.
- URL is cleaned, validated, and opened in browser.
- Agent then asks Gemini for a UI plan, which includes the actions to perform.
- Playwright executes each UI action step by step.
- A structured report.json is generated under the specified --outdir.

### Example Run Output
[Agent] Starting from https://linear.app
[Controller] Injected 30 cookies into session.
[Agent] ✅ Logged in automatically via injected cookies.
[Agent] Asking Gemini for task-specific URL...
[Agent] Generated clean task URL: https://linear.app/new?type=Project&name=AI%20Test%20Project
[Agent] Executing structured UI plan...
✅ Automation completed successfully.


### Future Improvements

- Replace static LLM URL reasoning with live DOM exploration
- Add retry/recovery mechanisms for failed navigation
- Enhance multi-step planning (sub-task delegation)
- Integrate session replay and vision-based element recognition
- Store task analytics and results in SQLite or MongoDB

### requirements.txt
playwright
google-generativeai
requests
tqdm


### AI Assistance Note

This project was developed with the guidance and technical assistance of ChatGPT (OpenAI GPT-5) for debugging, architecture alignment, and prompt optimization.
All final code, integration, and testing were implemented and validated manually by Ganesh Babu Medepalli.

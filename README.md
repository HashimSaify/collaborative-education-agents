# 🎓 Collaborative Education Agents (Gemini Edition)

> **A production-style multi-agent AI system powered exclusively by Google Gemini.**

---

## 📌 Project Overview

This project demonstrates a specialised multi-agent AI system where a **Researcher Agent** and a **Writer Agent** collaborate to generate high-quality study materials.

**Powered by:** Google Gemini 1.5 Flash (via CrewAI)

---

## 🚀 Setup Instructions

1. **Get a Gemini API Key**: Visit [Google AI Studio](https://aistudio.google.com/) to get your free key.
2. **Configure Environment**:
   - Rename `.env.example` to `.env`.
   - Add your key: `GOOGLE_API_KEY=your_key_here`.
3. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```
4. **Run the App**:
   ```bash
   python main.py --topic "Photosynthesis"
   ```

---

## 🏗️ Architecture

- **Researcher Agent**: Conducts academic research and outputs structured JSON.
- **Writer Agent**: Transforms JSON into polished Markdown study guides.
- **Orchestrator**: Manages the hand-off and state between agents.

---

## 📂 Key Files

- `main.py`: CLI Entry point.
- `app_ui.py`: Streamlit Web Interface.
- `agents/`: Agent logic for Researcher and Writer.
- `core/`: State management and hand-off protocols.
- `requirements.txt`: Project dependencies.

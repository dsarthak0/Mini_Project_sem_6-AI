import os
import streamlit as st
import requests
import json
from dotenv import load_dotenv
from PIL import Image
import google.generativeai as genai
from pdf2image import convert_from_path
import pytesseract
import pdfplumber
import re


# Load environment variables
load_dotenv()

# Configure Gemini
genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))
SCRAPINGDOG_API_KEY = os.getenv("SCRAPINGDOG_API_KEY")

# PDF text extractor
def extract_text_from_pdf(pdf_path):
    text = ""
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text
        if text.strip():
            return text.strip()
    except:
        pass

    try:
        images = convert_from_path(pdf_path)
        for image in images:
            text += pytesseract.image_to_string(image) + "\n"
    except:
        pass

    return text.strip()

# Analyze resume
def analyze_resume(resume_text, job_description=None):
    model = genai.GenerativeModel("gemini-1.5-flash")

    prompt = f"""
    You are an experienced HR professional. Analyze the following resume:
    - Key skills
    - Strengths & weaknesses
    - Skills to improve
    - Recommended courses
    - ATS resume score (out of 100)

    Resume:
    {resume_text}
    """
    if job_description:
        prompt += f"""

        Job Description:
        {job_description}

        Compare the resume with the job description and adjust the ATS score accordingly.
        """

    response = model.generate_content(prompt)
    result = response.text.strip()
    score = extract_score(result)
    return result, score

# Extract score
def extract_score(text):
    match = re.search(r'(\d{1,2}|100)\s*/\s*100', text)
    if not match:
        match = re.search(r'\b(\d{1,2}|100)\b', text)
    return int(match.group(1)) if match else None

# Extract skills
def extract_skills(resume_text):
    model = genai.GenerativeModel("gemini-1.5-flash")
    prompt = f"""
    Extract only technical and soft skills from this resume as a comma-separated list.

    Resume:
    {resume_text}
    """
    response = model.generate_content(prompt)
    return [skill.strip() for skill in response.text.split(",")]

# Get job recommendations
def fetch_jobs(skills, location="100293800", max_jobs=10):
    url = "https://api.scrapingdog.com/linkedinjobs/"
    job_results = []

    for skill in skills[:5]:
        page = 1
        while True:
            params = {
                "api_key": SCRAPINGDOG_API_KEY,
                "field": skill,
                "geoid": location,
                "page": str(page),
                "sort_by": "week",
                "job_type": "full_time",
                "exp_level": "entry_level"
            }
            response = requests.get(url, params=params)

            if response.status_code == 200:
                data = response.json()
                if not isinstance(data, list) or not data:
                    break
                for job in data[:3]:
                    job_results.append({
                        "title": job["job_position"],
                        "company": job["company_name"],
                        "link": job["job_link"],
                    })
                if len(job_results) >= max_jobs or len(data) < 10:
                    return job_results[:max_jobs]
                page += 1
            else:
                break

    return job_results[:max_jobs]

# --- Streamlit Web App ---
# Add this at the top of your Streamlit script


# Theme toggle
if "dark_mode" not in st.session_state:
    st.session_state.dark_mode = False

st.sidebar.title("⚙️ Settings")
st.session_state.dark_mode = st.sidebar.toggle("🌙 Dark Mode", value=st.session_state.dark_mode)

# Define color variables based on theme
if st.session_state.dark_mode:
    bg_color = "#000000"
    text_color = "#f0f0f0"
    accent_color = "#1f77b4"
else:
    bg_color = "#f9f9f9"
    text_color = "#262730"
    accent_color = "#4CAF50"

# Custom CSS styles for dark/light mode
st.markdown(f"""
    <style>
        html, body, [class*="css"]  {{
            background-color: {bg_color};
            color: {text_color};
        }}
        .stButton>button {{
            background-color: {accent_color};
            color: white;
            font-weight: bold;
            border: none;
            border-radius: 0.4em;
            padding: 0.5em 1em;
        }}
        .stButton>button:hover {{
            background-color: #45a049;
        }}
        .stSelectbox, .stTextArea, .stFileUploader, .stRadio, .stTextInput {{
            border-radius: 0.4em;
        }}
        h1, h2, h3, h4 {{
            color: {accent_color};
        }}
    </style>
""", unsafe_allow_html=True)

# st.set_page_config(page_title="AI Resume Chatbot", layout="centered")
st.title("🤖 AI Resume Chatbot Assistant")

if "stage" not in st.session_state:
    st.session_state.stage = "start"
if "resume_text" not in st.session_state:
    st.session_state.resume_text = None
if "score" not in st.session_state:
    st.session_state.score = None
if "analysis" not in st.session_state:
    st.session_state.analysis = None
if "skills" not in st.session_state:
    st.session_state.skills = []

# Start screen
if st.session_state.stage == "start":
    st.markdown("👋 Welcome! What would you like to do?")
    option = st.selectbox(
        "Choose an option:",
        ["Get ATS Score", "Get Resume Analysis", "Enter Preferred Job Description"]
    )
    uploaded_file = st.file_uploader("Upload your resume (PDF)", type="pdf")

    job_desc = None
    if option == "Enter Preferred Job Description":
        job_desc = st.text_area("Paste the Job Description here...")

    if uploaded_file and st.button("Submit"):
        with open("resume.pdf", "wb") as f:
            f.write(uploaded_file.read())
        text = extract_text_from_pdf("resume.pdf")
        st.session_state.resume_text = text

        st.session_state.analysis, st.session_state.score = analyze_resume(
            text,
            job_description=job_desc if option == "Enter Preferred Job Description" else None
        )

        st.session_state.skills = extract_skills(text)
        st.session_state.stage = "results"
        st.experimental_rerun()

# Results screen
elif st.session_state.stage == "results":
    st.subheader("📄 Resume Analysis")
    st.write(st.session_state.analysis)

    if st.session_state.score is not None:
        st.success(f"📊 ATS Resume Score: **{st.session_state.score}/100**")
    else:
        st.warning("Could not determine a score.")

    st.markdown("### 🧠 Extracted Skills")
    st.write(", ".join(st.session_state.skills))

    action = st.radio("What would you like to do next?", ["Get Job Recommendations", "Analyze Another Resume"])

    if action == "Get Job Recommendations":
        with st.spinner("Searching for jobs..."):
            jobs = fetch_jobs(st.session_state.skills)
        if jobs:
            st.markdown("### 💼 Job Matches")
            for job in jobs:
                st.markdown(f"- [{job['title']} - {job['company']}]({job['link']})")
        else:
            st.warning("No jobs found based on your skills.")

    elif action == "Analyze Another Resume":
        for key in ["resume_text", "score", "analysis", "skills"]:
            st.session_state[key] = None
        st.session_state.stage = "start"
        st.experimental_rerun()

# Footer
st.markdown("---")
st.markdown("<center>🚀 Built with <b>Streamlit</b> & <b>Gemini AI</b></center>", unsafe_allow_html=True)





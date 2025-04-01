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

# Load environment variables
load_dotenv()

# Configure Google Gemini AI
genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))

# Scrapingdog API Key
SCRAPINGDOG_API_KEY = os.getenv("SCRAPINGDOG_API_KEY")

# Function to extract text from PDF
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
    except Exception as e:
        print(f"Direct text extraction failed: {e}")
    
    print("Falling back to OCR for image-based PDF.")
    try:
        images = convert_from_path(pdf_path)
        for image in images:
            page_text = pytesseract.image_to_string(image)
            text += page_text + "\n"
    except Exception as e:
        print(f"OCR failed: {e}")
    
    return text.strip()

# Function to analyze resume with Gemini AI and provide a score
def analyze_resume(resume_text, job_description=None):
    if not resume_text:
        return {"error": "Resume text is required for analysis."}
    
    model = genai.GenerativeModel("gemini-1.5-flash")
    
    base_prompt = f"""
    You are an experienced HR professional. Review the provided resume and provide an analysis including:
    - Key skills the candidate has
    - Strengths and weaknesses
    - Suggested skills to improve
    - Recommended courses to enhance skills
    - Provide a resume score out of 100 based on structure, relevance, and clarity.
    
    Resume:
    {resume_text}
    """

    if job_description:
        base_prompt += f"""
        Additionally, compare this resume to the following job description:
        
        Job Description:
        {job_description}
        
        Highlight the strengths and weaknesses of the applicant in relation to the specified job requirements.
        Adjust the resume score based on relevance to this job.
        """

    response = model.generate_content(base_prompt)
    analysis_text = response.text.strip()
    score = extract_score_from_analysis(analysis_text)
    
    return analysis_text, score

# Function to extract the resume score from the AI response
def extract_score_from_analysis(analysis_text):
    import re
    score_match = re.search(r'\b(\d{1,2}|100)\b', analysis_text)
    return int(score_match.group()) if score_match else None

# Function to extract skills separately from resume
def extract_skills(resume_text):
    model = genai.GenerativeModel("gemini-1.5-flash")
    
    prompt = f"""
    Extract the main technical and soft skills from the following resume.
    Provide only a comma-separated list of skills.
    
    Resume:
    {resume_text}
    """
    
    response = model.generate_content(prompt)
    skills = response.text.strip().split(", ")
    return skills

# Function to fetch jobs using Scrapingdog API
def fetch_jobs_from_scrapingdog(skills, location="100293800",max_jobs=10):  # Use correct geoid for India
    url = "https://api.scrapingdog.com/linkedinjobs/"
    job_results = []
    
    for skill in skills[:5]:  # Limit to 5 skills to avoid excessive API calls
        page = 1

        while True:  # Loop to fetch multiple pages
            params = {
                "api_key": SCRAPINGDOG_API_KEY,
                "field": skill,
                "geoid": location,  # Corrected geoid for India
                "page": str(page),
                "sort_by": "week",  # Optional: Get jobs from the last 7 days
                "job_type": "full_time",  # Optional: Only full-time jobs
                "exp_level": "entry_level"  # Optional: Entry-level jobs
            }
            response = requests.get(url, params=params)

            print(f"Requesting jobs for skill: {skill} (Page {page})")  # Debug log

            if response.status_code == 200:
                try:
                    data = response.json()
                    print("Full API Response:", data)  # 🔍 Debugging: Print full API response

                    if not isinstance(data, list):  # Ensure response is a list
                        print("Unexpected API response format:", data)
                        break

                    if not data:  # If response is empty, stop fetching more pages
                        break

                    for job in data[:3]:  # Get top 3 jobs per page
                        job_results.append(
                            {
                                "title": job["job_position"],
                                "company": job["company_name"],
                                "link": job["job_link"],
                            }
                        )

                    page += 1  # Go to next page
                    if len(data) < 10:  # Stop if less than 10 jobs on the page
                        break
                    if len(job_results) >= max_jobs:
                        
                        return job_results[:max_jobs]
                
                except Exception as e:
                    print(f"Error processing JSON response: {e}")
                    break
            else:
                print(f"API Request failed: {response.status_code} - {response.text}")
                break

    return job_results[:max_jobs]




# Streamlit app
st.set_page_config(page_title="AI Resume & Job Matcher", layout="wide")

st.title("AI Resume Analyzer & Job Recommender")
st.write("Upload your resume, and we’ll suggest jobs that match your skills!")

col1, col2 = st.columns(2)
with col1:
    uploaded_file = st.file_uploader("Upload your resume (PDF)", type=["pdf"])
with col2:
    job_description = st.text_area("Enter Job Description:", placeholder="Paste the job description here...")

if uploaded_file:
    st.success("Resume uploaded successfully!")

if uploaded_file and st.button("Analyze Resume & Get Job Matches"):
    with st.spinner("Processing..."):
        with open("uploaded_resume.pdf", "wb") as f:
            f.write(uploaded_file.getbuffer())
        
        resume_text = extract_text_from_pdf("uploaded_resume.pdf")
        
        # Resume Analysis
        st.write("## 📑 Resume Analysis")
        analysis, score = analyze_resume(resume_text, job_description)
        st.write(analysis)
        
        if score is not None:
            st.write(f"### 📊 Resume Score: **{score}/100**")
        else:
            st.warning("Could not determine resume score.")

        # Extract Skills
        extracted_skills = extract_skills(resume_text)
        st.write("### 🔹 Extracted Skills:")
        st.write(", ".join(extracted_skills))

        # Fetch Jobs from Scrapingdog
        st.write("## 🔍 Job Recommendations")
        matching_jobs = fetch_jobs_from_scrapingdog(extracted_skills)

        if matching_jobs:
            for job in matching_jobs:
                st.markdown(f"🔹 [{job['title']} - {job['company']}]({job['link']})")
        else:
            st.warning("No matching jobs found! The API may have changed or the skill parameters may not be returning results.")
            




st.markdown("---")
st.markdown(
    """<p style='text-align: center;'>Powered by <b>Streamlit</b> and <b>Google Gemini AI</b></p>""",
    unsafe_allow_html=True,
)





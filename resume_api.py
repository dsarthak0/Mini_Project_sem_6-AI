from flask import Flask, request, jsonify
from app import extract_text_from_pdf, analyze_resume, extract_skills, fetch_jobs as fetch_jobs_from_scrapingdog


app = Flask(__name__)

@app.route("/analyze-resume", methods=["POST"])
def analyze():
    resume = request.files.get("resume")
    job_desc = request.form.get("job_description", "")

    resume_path = "temp_resume.pdf"
    resume.save(resume_path)

    resume_text = extract_text_from_pdf(resume_path)
    analysis, score = analyze_resume(resume_text, job_desc)
    return jsonify({
        "analysis": analysis,
        "score": score
    })

@app.route("/get-jobs", methods=["POST"])
def get_jobs():
    skills = request.json.get("skills", [])
    jobs = fetch_jobs_from_scrapingdog(skills)
    return jsonify(jobs)

if __name__ == "__main__":
    app.run(port=5000)

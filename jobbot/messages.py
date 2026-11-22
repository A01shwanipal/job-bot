"""Template-based application message. Uses ONLY facts from config/profile.yaml."""
from .matcher import matched_skills


def build_message(job, profile: dict) -> str:
    per, links = profile["personal"], profile["links"]
    text = f"{job['title']} {job['description']}".lower()
    skills = sorted(matched_skills(text, profile), key=lambda x: -x[1])[:4]
    skill_names = [n for n, _ in skills]

    # projects whose tech overlaps the job text
    def overlap(p):
        return sum(1 for t in p.get("tech", []) if t.lower() in text)
    projects = sorted(profile.get("projects", []), key=overlap, reverse=True)
    projects = [p for p in projects if overlap(p) > 0][:1] or profile.get("projects", [])[:1]

    parts = [f"Dear {job['company']} Hiring Team,", ""]
    parts.append(f"I am {per['full_name']}, a {profile['headline']}, and I would like to be considered "
                 f"for the {job['title']} position.")
    if skill_names:
        joined = ", ".join(skill_names[:-1]) + (" and " if len(skill_names) > 1 else "") + skill_names[-1]
        parts.append(f"Your posting mentions {joined}, which are part of the stack I work with.")
    for p in projects:
        parts.append(f"I have built {p['name']}, {p['summary']}.")
    for e in profile.get("experience", [])[:1]:
        parts.append(f"I also completed a {e}.")
    links_line = " | ".join(f"{k.capitalize()}: {v}" for k, v in links.items() if v)
    parts += ["", "My resume is attached. I would welcome the chance to discuss how I can contribute to your team.",
              "", f"Regards,\n{per['full_name']}", links_line]
    return "\n".join(parts)

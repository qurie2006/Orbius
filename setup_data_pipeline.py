import json
import re
from datasets import load_dataset
import pandas as pd
from sentence_transformers import SentenceTransformer
import numpy as np
from collections import Counter
import os

# Target roles
TARGET_ROLES = [
    "Software Engineer",
    "Backend Developer",
    "Frontend Developer",
    "Data Scientist"
]

# Boilerplate patterns to remove
BOILERPLATE_PATTERNS = [
    r'equal opportunity employer',
    r'visa sponsorship',
    r'diversity and inclusion',
    r'benefits package',
    r'insurance benefits',
    r'retirements plans',
    r'paid time off',
    r'discrimination',
    r'affirmative action',
    r'background check',
    r'drug test',
    r'employment is at will',
    r'this position is',
    r'we are looking for',
    r'the ideal candidate',
    r'must be authorized',
    r'requirements.*:',
    r'qualifications.*:',
    r'benefits.*:',
    r'compensation.*:',
]

def clean_text(text):
    """Remove boilerplate legal text and extract relevant sections."""
    if not text or not isinstance(text, str):
        return ""

    # Convert to lowercase for pattern matching
    text_lower = text.lower()

    # Remove boilerplate sections
    for pattern in BOILERPLATE_PATTERNS:
        text_lower = re.sub(pattern, '', text_lower, flags=re.IGNORECASE)

    # Extract relevant sections
    sections = []
    section_patterns = [
        r'responsibilities?:\s*(.*?)(?=\n\n|\n[A-Z]|\Z)',
        r'skills?:\s*(.*?)(?=\n\n|\n[A-Z]|\Z)',
        r'experience?:\s*(.*?)(?=\n\n|\n[A-Z]|\Z)',
        r'requirements?:\s*(.*?)(?=\n\n|\n[A-Z]|\Z)',
        r'qualifications?:\s*(.*?)(?=\n\n|\n[A-Z]|\Z)',
    ]

    for pattern in section_patterns:
        matches = re.findall(pattern, text_lower, re.IGNORECASE | re.DOTALL)
        sections.extend(matches)

    # If no sections found, return cleaned text
    if not sections:
        return text_lower.strip()

    # Combine sections
    relevant_text = ' '.join(sections)
    return relevant_text.strip()

def extract_keywords(text, top_n=20):
    """Extract top keywords from text."""
    if not text or not isinstance(text, str):
        return []

    # Simple keyword extraction (can be enhanced)
    words = re.findall(r'\b[a-z]{3,}\b', text.lower())
    # Filter out common stopwords
    stopwords = {'the', 'and', 'for', 'are', 'but', 'not', 'you', 'all', 'can', 'had',
                 'her', 'was', 'one', 'our', 'out', 'day', 'get', 'has', 'him', 'his',
                 'how', 'its', 'may', 'new', 'now', 'old', 'see', 'two', 'way', 'who',
                 'boy', 'did', 'has', 'let', 'put', 'say', 'she', 'too', 'use', 'with',
                 'work', 'will', 'from', 'this', 'that', 'have', 'been', 'were', 'when',
                 'more', 'some', 'time', 'very', 'what', 'about', 'which', 'their', 'could',
                 'would', 'should', 'being', 'doing', 'just', 'also', 'other', 'into',
                 'than', 'only', 'over', 'such', 'your', 'after', 'first', 'before',
                 'like', 'these', 'those', 'make', 'through', 'while', 'still', 'each'}

    words = [w for w in words if w not in stopwords and len(w) > 2]
    word_counts = Counter(words)
    return [word for word, count in word_counts.most_common(top_n)]

def load_job_descriptions():
    """Load job descriptions from Hugging Face."""
    print("Loading job descriptions dataset...")
    try:
        # Try loading the recruitment dataset
        dataset = load_dataset("lang-uk/recruitment-dataset-job-descriptions-english", split="train")
        print(f"Loaded {len(dataset)} job descriptions")
        return dataset
    except Exception as e:
        print(f"Error loading job descriptions: {e}")
        # Try alternative dataset
        try:
            dataset = load_dataset("jacob-hugging-face/job-descriptions", split="train")
            print(f"Loaded {len(dataset)} job descriptions from alternative source")
            return dataset
        except Exception as e2:
            print(f"Error loading alternative dataset: {e2}")
            return None

def load_resume_dataset():
    """Load resume dataset from Hugging Face."""
    print("Loading resume dataset...")

    # Try alternative datasets with job titles
    datasets_to_try = [
        "jacob-hugging-face/job-descriptions",  # This has job titles and descriptions we can use as resumes
        "rjray/US_Sanctions_Humanitarian_Demo",
    ]

    for ds_name in datasets_to_try:
        try:
            dataset = load_dataset(ds_name, split="train")
            print(f"Loaded {len(dataset)} entries from {ds_name}")
            print(f"Columns: {dataset.column_names}")
            return dataset
        except Exception as e:
            print(f"Could not load {ds_name}: {e}")
            continue

    # If nothing works, return None and we'll use job descriptions as proxy
    print("Warning: Could not load suitable resume dataset. Will use job descriptions as proxy.")
    return None

def filter_by_role(dataset, role_column='role', text_column='description'):
    """Filter dataset by target roles."""
    if dataset is None:
        return None

    filtered = []
    print(f"\nDataset columns: {dataset.column_names}")

    # Try to find the role column
    possible_role_columns = ['role', 'title', 'job_title', 'position', 'Position', 'category', 'label']
    role_col = None
    for col in possible_role_columns:
        if col in dataset.column_names:
            role_col = col
            break

    if role_col is None:
        print("Could not find role column. Will check all fields for role keywords.")
        # Check all fields for role keywords
        for item in dataset:
            item_text = ' '.join([str(v) for v in item.values() if isinstance(v, str)]).lower()
            for target_role in TARGET_ROLES:
                if target_role.lower() in item_text:
                    filtered.append(item)
                    break
    else:
        print(f"Using role column: {role_col}")
        for item in dataset:
            role = str(item[role_col]).lower() if role_col in item else ""
            # Check if any target role is in the text
            for target_role in TARGET_ROLES:
                if target_role.lower() in role:
                    filtered.append(item)
                    break

    print(f"Filtered to {len(filtered)} entries matching target roles")
    return filtered

def sample_entries(data, max_per_role=100):
    """Sample up to max_per_role entries per role."""
    if not data:
        return []

    sampled = {}
    for item in data:
        # Determine role
        role = "Unknown"
        for target_role in TARGET_ROLES:
            # Check various fields for role
            for key, value in item.items():
                if isinstance(value, str) and target_role.lower() in value.lower():
                    role = target_role
                    break
            if role != "Unknown":
                break

        if role == "Unknown":
            continue  # Skip entries that don't match any target role

        if role not in sampled:
            sampled[role] = []
        if len(sampled[role]) < max_per_role:
            sampled[role].append(item)

    # Flatten
    result = []
    for role, items in sampled.items():
        result.extend(items)
        print(f"Sampled {len(items)} entries for role: {role}")

    return result

def main():
    print("=" * 60)
    print("Setting up Resume Matching Data Pipeline")
    print("=" * 60)

    # Load datasets
    job_dataset = load_job_descriptions()
    resume_dataset = load_resume_dataset()

    if job_dataset is None:
        print("ERROR: Could not load job descriptions dataset. Please check your internet connection.")
        return

    # If resume dataset is None, use a subset of job descriptions as proxy
    if resume_dataset is None:
        print("Using subset of job descriptions as proxy for resumes")
        resume_dataset = job_dataset

    # Filter and sample
    print("\n" + "=" * 60)
    print("Filtering and Sampling")
    print("=" * 60)

    filtered_jobs = filter_by_role(job_dataset)
    sampled_jobs = sample_entries(filtered_jobs, max_per_role=100)

    # If resume_dataset is the same as job_dataset, use a different subset
    if resume_dataset is job_dataset:
        print("Using different subset of job descriptions for resumes")
        # Take entries from filtered_jobs that weren't already in sampled_jobs
        filtered_resumes = [item for item in filtered_jobs if item not in sampled_jobs]
        sampled_resumes = sample_entries(filtered_resumes, max_per_role=50)
    else:
        filtered_resumes = filter_by_role(resume_dataset)
        sampled_resumes = sample_entries(filtered_resumes, max_per_role=100)

    # Clean text
    print("\n" + "=" * 60)
    print("Cleaning Text")
    print("=" * 60)

    # Load embedding model
    print("\nLoading sentence transformer model...")
    model = SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')

    # Process resumes
    print("\nProcessing resumes...")
    resume_data_by_role = {}
    for role in TARGET_ROLES:
        resume_data_by_role[role] = {'texts': [], 'embeddings': [], 'keywords': []}

    for item in sampled_resumes:
        # Determine role first
        role = None
        for target_role in TARGET_ROLES:
            for key, value in item.items():
                if isinstance(value, str) and target_role.lower() in value.lower():
                    role = target_role
                    break
            if role:
                break

        if not role:
            continue

        # Find text field - handle both structured and unstructured data
        text_parts = []

        # Check for structured fields (from datasetmaster/resumes)
        if 'skills' in item and item['skills']:
            if isinstance(item['skills'], str):
                text_parts.append(item['skills'])
            elif isinstance(item['skills'], list):
                text_parts.append(' '.join(str(s) for s in item['skills']))

        if 'experience' in item and item['experience']:
            if isinstance(item['experience'], str):
                text_parts.append(item['experience'])
            elif isinstance(item['experience'], list):
                for exp in item['experience']:
                    if isinstance(exp, dict):
                        text_parts.append(str(exp.get('description', '')))

        if 'education' in item and item['education']:
            if isinstance(item['education'], str):
                text_parts.append(item['education'])
            elif isinstance(item['education'], list):
                for edu in item['education']:
                    if isinstance(edu, dict):
                        text_parts.append(str(edu.get('degree', '')) + ' ' + str(edu.get('field', '')))

        # Check for general text fields (from other datasets)
        for key in ['Long Description', 'description', 'text', 'content', 'job_description', 'resume', 'Resume_str']:
            if key in item and item[key]:
                text_parts.append(str(item[key]))

        if not text_parts:
            continue

        text = ' '.join(text_parts)
        cleaned = clean_text(text)
        keywords = extract_keywords(cleaned)

        if cleaned:
            resume_data_by_role[role]['texts'].append(cleaned)
            resume_data_by_role[role]['keywords'].extend(keywords)

    # Compute embeddings for resumes
    print("Computing resume embeddings...")
    for role in TARGET_ROLES:
        texts = resume_data_by_role[role]['texts']
        if texts:
            embeddings = model.encode(texts, show_progress_bar=True)
            resume_data_by_role[role]['embeddings'] = embeddings
            # Compute centroid
            centroid = np.mean(embeddings, axis=0)
            resume_data_by_role[role]['centroid'] = centroid.tolist()
            # Get top keywords
            keyword_counts = Counter(resume_data_by_role[role]['keywords'])
            resume_data_by_role[role]['top_skills'] = [kw for kw, _ in keyword_counts.most_common(20)]
        else:
            resume_data_by_role[role]['centroid'] = None
            resume_data_by_role[role]['top_skills'] = []

    # Process job descriptions
    print("\nProcessing job descriptions...")
    job_data_by_role = {}
    for role in TARGET_ROLES:
        job_data_by_role[role] = {'texts': [], 'embeddings': [], 'keywords': []}

    for item in sampled_jobs:
        # Determine role first
        role = None
        for target_role in TARGET_ROLES:
            for key, value in item.items():
                if isinstance(value, str) and target_role.lower() in value.lower():
                    role = target_role
                    break
            if role:
                break

        if not role:
            continue

        # Find text field
        text_parts = []
        for key in ['Long Description', 'description', 'text', 'content', 'job_description']:
            if key in item and item[key]:
                text_parts.append(str(item[key]))

        if not text_parts:
            continue

        text = ' '.join(text_parts)
        cleaned = clean_text(text)
        keywords = extract_keywords(cleaned)

        if cleaned:
            job_data_by_role[role]['texts'].append(cleaned)
            job_data_by_role[role]['keywords'].extend(keywords)

    # Compute embeddings for jobs
    print("Computing job description embeddings...")
    for role in TARGET_ROLES:
        texts = job_data_by_role[role]['texts']
        if texts:
            embeddings = model.encode(texts, show_progress_bar=True)
            job_data_by_role[role]['embeddings'] = embeddings
            # Compute centroid
            centroid = np.mean(embeddings, axis=0)
            job_data_by_role[role]['centroid'] = centroid.tolist()
            # Get top keywords
            keyword_counts = Counter(job_data_by_role[role]['keywords'])
            job_data_by_role[role]['top_skills'] = [kw for kw, _ in keyword_counts.most_common(20)]
        else:
            job_data_by_role[role]['centroid'] = None
            job_data_by_role[role]['top_skills'] = []

    # Prepare role baselines
    print("\nPreparing role baselines...")
    role_baselines = {}
    for role in TARGET_ROLES:
        role_baselines[role] = {
            'resume_count': len(resume_data_by_role[role]['texts']),
            'job_count': len(job_data_by_role[role]['texts']),
            'top_skills': resume_data_by_role[role]['top_skills'],
            'resume_centroid': resume_data_by_role[role]['centroid'],
            'job_centroid': job_data_by_role[role]['centroid']
        }

    # Save role baselines
    output_dir = './test_dataset'
    os.makedirs(output_dir, exist_ok=True)

    baseline_path = os.path.join(output_dir, 'role_baselines.json')
    with open(baseline_path, 'w') as f:
        json.dump(role_baselines, f, indent=2)
    print(f"Saved role baselines to {baseline_path}")

    # Save sample resumes
    print("\nSaving sample resumes...")
    sample_resumes = []
    for role in TARGET_ROLES:
        texts = resume_data_by_role[role]['texts'][:2]  # Take 2 per role
        for i, text in enumerate(texts):
            sample_resumes.append({
                'role': role,
                'sample_id': f"{role}_{i}",
                'text': text
            })

    sample_path = os.path.join(output_dir, 'sample_test_resumes.json')
    with open(sample_path, 'w') as f:
        json.dump(sample_resumes, f, indent=2)
    print(f"Saved sample resumes to {sample_path}")

    # Print verification summary
    print("\n" + "=" * 60)
    print("VERIFICATION SUMMARY")
    print("=" * 60)

    baseline_size = os.path.getsize(baseline_path)
    sample_size = os.path.getsize(sample_path)

    print(f"\nFile Sizes:")
    print(f"  role_baselines.json: {baseline_size} bytes")
    print(f"  sample_test_resumes.json: {sample_size} bytes")

    print(f"\nRow Counts:")
    for role in TARGET_ROLES:
        print(f"  {role}:")
        print(f"    Resumes: {role_baselines[role]['resume_count']}")
        print(f"    Jobs: {role_baselines[role]['job_count']}")

    print(f"\nSample Keys in role_baselines.json:")
    print(f"  {list(role_baselines.keys())}")
    print(f"  Sample role structure: {list(role_baselines['Software Engineer'].keys())}")

    print(f"\nSample Keys in sample_test_resumes.json:")
    if sample_resumes:
        print(f"  {list(sample_resumes[0].keys())}")
        print(f"  Total samples: {len(sample_resumes)}")

    print("\n" + "=" * 60)
    print("Data pipeline setup complete!")
    print("=" * 60)

if __name__ == "__main__":
    main()

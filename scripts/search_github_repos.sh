#!/bin/bash
# Wide net: find GitHub repos for programmatic job search.
# Task 3-2 of worklog. Saves one JSON per query under research/github-repos/raw/
OUT=/home/z/my-project/research/github-repos/raw
mkdir -p "$OUT"

declare -A Q=(
  [q01_jobspy]="github python-jobspy indeed linkedin glassdoor job scraper library"
  [q02_easyapply]="github linkedin easy apply bot automation python"
  [q03_autoapply_ai]="github open source AI agent auto apply jobs LLM"
  [q04_arbeitsagentur]="github arbeitsagentur jobsuche api client python"
  [q05_aggregator]="github open source job board aggregator api scraper"
  [q06_ats]="github greenhouse lever smartrecruiters job scraper ats feeds"
  [q07_germany]="github germany job scraper stepstone xing jobboerse"
  [q08_awesome]="awesome github list job search automation job APIs"
  [q09_adzuna]="github adzuna api client python"
  [q10_eures]="github eures api client job search europe"
  [q11_tracker]="github job application tracker open source CLI"
  [q12_workday]="github workday job posting scraper xml feed"
  [q13_personio]="github personio recruit api job scraper"
  [q14_linkedin_scrape]="github linkedin jobs scraper 2025 python no login"
  [q15_remote]="github free jobs api remote jobs public api"
  [q16_jooble]="github jooble api client job search"
  [q17_llm_resume]="github LLM tailor resume cover letter job application open source"
  [q18_playwright]="github playwright job scraper template site:github.com"
)

SKIP_OK=1   # skip queries whose .json already exists (from a previous run)
for k in "${!Q[@]}"; do
  if [ "$SKIP_OK" = "1" ] && [ -s "$OUT/$k.json" ]; then echo "skip $k (already have)"; continue; fi
  for attempt in 1 2 3; do
    z-ai function -n web_search -a "{\"query\": \"${Q[$k]}\", \"num\": 8}" -o "$OUT/$k.json" 2>"$OUT/$k.err" && break
    echo "retry $k (attempt $attempt) after 429/err"; sleep 8
  done
  sleep 3   # stay under rate limit
done
echo "done"; ls -la "$OUT" | grep -c '\.json'

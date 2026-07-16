"""
Replaces the content between <!-- JOB-PAL-START --> and <!-- JOB-PAL-END -->
in ai-portfolio/README.md with the content of PORTFOLIO.md from job-bot.
"""
import sys

START = "<!-- JOB-PAL-START -->"
END   = "<!-- JOB-PAL-END -->"

portfolio_md   = sys.argv[1]  # path to job-bot/PORTFOLIO.md
readme_path    = sys.argv[2]  # path to ai-portfolio/README.md

with open(portfolio_md) as f:
    new_content = f.read().strip()

with open(readme_path) as f:
    readme = f.read()

start_idx = readme.find(START)
end_idx   = readme.find(END)

if start_idx == -1 or end_idx == -1:
    print(f"ERROR: markers not found in {readme_path}")
    sys.exit(1)

end_idx += len(END)

updated = readme[:start_idx] + START + "\n" + new_content + "\n" + END + readme[end_idx:]

with open(readme_path, "w") as f:
    f.write(updated)

print("Portfolio entry updated successfully.")

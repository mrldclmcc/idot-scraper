# IDOT Bid Letting Scraper - Serverless Version

This is a web-based tool for scraping contract information from Illinois Department of Transportation (IDOT) bid letting pages. It automatically filters for Chicago metro area counties and extracts low bidder and awardee data.

## What This Tool Does

The scraper takes an IDOT "Notice of Letting" repository page URL, which contains a table listing multiple construction contracts. It then:

1. Fetches and parses the repository page
2. Filters contracts by county (Boone, Cook, DuPage, Grundy, Kane, Kendall, Lake, McHenry, Will, or Various)
3. Filters by status (Active, Executed, or Awarded)
4. Extracts the individual contract detail page URLs
5. Scrapes each contract page for low bidder name, bid amount, and awardee information
6. Compiles everything into a downloadable CSV file

## Architecture

This version splits the original single-file HTML tool into two parts:

- **Frontend** (`public/index.html`): A simple web interface where you enter the repository URL and download results
- **Backend** (`api/scrape.py`): A Python serverless function that does the actual web scraping

This architecture solves the CORS proxy problem because the scraping happens server-side, where browser security restrictions don't apply.

## Deployment Instructions

Follow these steps to deploy your scraper to Vercel for free:

### Step 1: Create a GitHub Account (if you don't have one)

1. Go to https://github.com
2. Click "Sign up" and follow the prompts
3. Verify your email address

### Step 2: Create a New Repository

1. Once logged into GitHub, click the "+" icon in the top right corner
2. Select "New repository"
3. Name it something like `idot-scraper`
4. Choose "Public" (required for Vercel's free tier)
5. Do NOT initialize with a README
6. Click "Create repository"

### Step 3: Upload Your Code to GitHub

You have two options:

**Option A: Using GitHub's Web Interface (Easier)**

1. On your new repository page, click "uploading an existing file"
2. Drag and drop all four files from your local computer:
   - `vercel.json`
   - `requirements.txt`
   - The `api` folder (with `scrape.py` inside)
   - The `public` folder (with `index.html` inside)
3. Write a commit message like "Initial commit"
4. Click "Commit changes"

**Option B: Using Git Command Line (If you're comfortable with Git)**

```bash
# Navigate to the folder containing your files
cd /path/to/your/idot-scraper

# Initialize git repository
git init

# Add all files
git add .

# Commit
git commit -m "Initial commit"

# Connect to your GitHub repository (replace YOUR-USERNAME with your GitHub username)
git remote add origin https://github.com/YOUR-USERNAME/idot-scraper.git

# Push to GitHub
git branch -M main
git push -u origin main
```

### Step 4: Create a Vercel Account

1. Go to https://vercel.com
2. Click "Sign Up"
3. Choose "Continue with GitHub" (this makes connecting your repository easier)
4. Authorize Vercel to access your GitHub account

### Step 5: Deploy to Vercel

1. Once logged into Vercel, click "Add New..."
2. Select "Project"
3. You'll see a list of your GitHub repositories - find `idot-scraper` and click "Import"
4. Vercel will auto-detect the settings (you don't need to change anything)
5. Click "Deploy"
6. Wait 1-2 minutes for the deployment to complete

### Step 6: Access Your Tool

Once deployment is complete, Vercel will give you a URL like:

```
https://idot-scraper-abc123.vercel.app
```

Visit this URL in your browser, and you'll see your scraper interface! You can bookmark this URL and access it from any device.

## How to Use the Tool

1. Go to the IDOT website and find a "Notice of Letting" page that lists multiple contracts
2. Copy the full URL (it should look like: `https://webapps1.dot.illinois.gov/WCTB/LbLettingDetail/...`)
3. Paste it into the text box on your deployed scraper
4. Click "Start Scrape"
5. Wait for processing to complete (you'll see status messages)
6. Click "Download CSV" to get your results

## Project Structure

```
idot-scraper/
├── api/
│   └── scrape.py          # Python serverless function (the backend)
├── public/
│   └── index.html         # Web interface (the frontend)
├── vercel.json            # Vercel configuration
└── requirements.txt       # Python dependencies (empty, but required)
```

## Troubleshooting

**"Failed to fetch repository page"**
- Make sure the URL is correct and the IDOT page is accessible
- The IDOT website might be temporarily down

**"No matching contracts found"**
- The repository page might not have any contracts matching the filter criteria
- Check that contracts exist for the specified counties and statuses

**Deployment fails on Vercel**
- Make sure all files are in the correct folders as shown in the structure above
- Check that `vercel.json` is in the root directory
- Verify your GitHub repository is public

**Changes not showing up**
- After making changes to your code, commit and push to GitHub
- Vercel will automatically redeploy (or you can trigger a redeploy manually from the Vercel dashboard)

## Free Tier Limits

Vercel's free tier includes:
- 100GB bandwidth per month
- Unlimited deployments
- Automatic HTTPS
- Custom domain support (optional)

With twice-monthly usage, you'll be well within these limits.

## Future Enhancements

Possible improvements you could make:
- Add email notifications when scraping completes
- Schedule automatic daily/weekly scrapes
- Store results in a database for historical tracking
- Add more filtering options
- Support additional IDOT page formats

## License

Free to use and modify for your purposes.

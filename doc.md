1. receives, parses, and analyzes official transcripts from the Kenya National Assembly

## Key Highlights:

Parses official Hansard PDFs from parliament.go.ke
Extracts structured data: speaker, party, constituency, topic, sentiment
Stores all data in a local SQLite database for offline access
Provides a powerful CLI for querying and reporting
Designed with a web interface layer in mind for future expansion

##  Proposed Solution
 
The Kenya Hansard Analyzer solves this by building an automated pipeline that:
 
1. Scrapes Hansard PDFs from the parliament website on a scheduled basis
2. Parses each document into structured records: speaker, constituency, party, date, topic, and content
3. Stores all records in a normalized SQLite database
4. Analyzes the data using statistical methods and AI to surface patterns and insights
5. Reports findings through a CLI interface with export capabilities
The platform operates entirely offline after initial data ingestion, making it accessible in low-connectivity environments.
 
##  Analytics
 
Computes participation metrics for each MP across all sessions.
 
Metrics computed:
- Total speeches given
- Total words spoken
- Average speech length
- Sessions attended (proxy: sessions with at least one speech)
- Most discussed topics
- Sentiment score (average tone of speeches)
- Participation trend over time

## Project flow
Parliament Website
      │
      │  Scheduled scrape (daily/weekly)
      ▼
Download PDFs ──► Parse ──► Store in SQLite
                                  │
                                  │  Instant retrieval
                                  ▼
                            User runs a query
                                  │
                                  ▼
                            Results displayed


## Delivery Plan

### DAY 1: 
- Write database schema
- Download sample pdfs and observe structure
- Build scrape to get pdf links, download pdfs, 
    - Implement logic to sync pdfs, (discovery and download)
- use pdfplumber to exract data
- validation and testing of extracted data


### DAY 2: 
- Write MP analytics — speech count, word count, sessions, activity over time
- Write topic analytics — keyword map, topic classification, frequency, trending
- Write sentiment analysis using NLTK VADER
- Write trend analysis — topic trends, participation trends, MP leaderboard
- Build CLI foundation with core commands using `click` and `rich`
- Write the MP scorecard report with ASCII charts and speech excerpts
- Write analytics unit tests and run full sync → query → scorecard flow

## Day 3 

- Write AI session and MP summarizer 
- Write party report and party comparison reports
- Write session detail report with AI summary
- Write CSV export for speeches and analytics
- Write the daily sync scheduler

## Day 4

- Write database tests using in-memory SQLite
Run coverage report, write edge case tests to reach 80% coverage
- Audit error handling across all modules
- Write the README
- Sync 10+ real Hansards and smoke-test every CLI command
- Profile performance and add database indexes where needed

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
 
##  Analytics (`analytics/mp_stats.py`)
 
Computes participation metrics for each MP across all sessions.
 
Metrics computed:
- Total speeches given
- Total words spoken
- Average speech length
- Sessions attended (proxy: sessions with at least one speech)
- Most discussed topics
- Sentiment score (average tone of speeches)
- Participation trend over time


platforms
GUI - Tkinter


import logging
import sqlite3
import time
from google import genai
from google.genai import errors as genai_errors

from config import GEMINI_API_KEY, GEMINI_MODEL

logger = logging.getLogger(__name__)


def _get_client():
    """
    Initializes and returns a Gemini client.
    Returns None if no API key is configured.
    """
    if not GEMINI_API_KEY:
        logger.warning("GEMINI_API_KEY not set — AI features disabled.")
        return None
    return genai.Client(api_key=GEMINI_API_KEY)


def _call_gemini(client, prompt: str) -> str:
    """
    Calls Gemini with the given prompt.
    Retries once after 2 seconds on rate limit.
    Raises on InvalidArgument so caller can retry with reduced content.
    Returns fallback string on any other failure.
    """
    try:
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt
        )
        return response.text

    except genai_errors.ClientError as e:
        if "InvalidArgument" in str(e) or "too long" in str(e).lower():
            logger.warning("Prompt too long — retrying with reduced content.")
            raise
        logger.error("Gemini client error: %s", e)
        return "Summary could not be generated."

    except genai_errors.ServerError as e:
        logger.warning("Rate limit or server error — waiting 2s before retry.")
        time.sleep(2)
        try:
            response = client.models.generate_content(
                model=GEMINI_MODEL,
                contents=prompt
            )
            return response.text
        except Exception as retry_exc:
            logger.error("Retry failed: %s", retry_exc)
            return "Summary could not be generated."

    except Exception as e:
        logger.error("Unexpected Gemini error: %s", e)
        return "Summary could not be generated."


def summarize_session(session_id: int, db_path: str) -> str:
    """
    Generates a summary of a parliamentary session.
    
    Args:
        session_id: The ID of the session to summarize
        db_path: Path to the SQLite database
        
    Returns:
        A summary string or fallback message if generation fails
    """
    client = _get_client()
    if not client:
        return "Summary could not be generated."
    
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Fetch session metadata
        cursor.execute(
            "SELECT date, chamber FROM sessions WHERE id = ?",
            (session_id,)
        )
        session_row = cursor.fetchone()
        
        if not session_row:
            return "Summary could not be generated."
        
        date = session_row["date"]
        chamber = session_row["chamber"]
        
        # Fetch all speeches for this session
        cursor.execute("""
            SELECT s.content, s.section, m.name, m.constituency, m.party
            FROM speeches s
            JOIN members m ON s.member_id = m.id
            WHERE s.session_id = ?
            ORDER BY s.id
            LIMIT 30
        """, (session_id,))
        
        speeches = cursor.fetchall()
        
        if not speeches:
            conn.close()
            return "Summary could not be generated."
        
        # Get unique sections
        cursor.execute(
            "SELECT DISTINCT section FROM speeches WHERE session_id = ?",
            (session_id,)
        )
        sections_rows = cursor.fetchall()
        sections = ", ".join([row[0] for row in sections_rows if row[0]])
        
        conn.close()
        
        # Build speeches text with full content
        speeches_text = ""
        for speech in speeches:
            name = speech["name"]
            constituency = speech["constituency"]
            party = speech["party"]
            section = speech["section"] or "General"
            content = speech["content"][:500] if speech["content"] else ""
            
            speeches_text += f"{name} ({constituency}, {party}) [{section}]:\n{content}\n\n"
        
        # Build the prompt
        prompt = f"""You are a parliamentary analyst for Kenya's National Assembly.

        Below is a transcript of a parliamentary session held on {date}.
        Chamber: {chamber}

        The session covered the following sections: {sections}

        Here are the key speeches from this session:

        {speeches_text}

        Write a clear, factual 3-paragraph summary of this session for a Kenyan citizen
        who wants to understand what Parliament discussed and decided. Use plain language.
        Do not use bullet points. Write in prose. Be specific about bills discussed,
        petitions presented, and any notable exchanges."""
        
        # Try with full content first
        try:
            return _call_gemini(client, prompt)
        except genai_errors.ClientError:
            # Retry with reduced content
            logger.info("Retrying session summary with reduced content.")
            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT s.content, s.section, m.name, m.constituency, m.party
                FROM speeches s
                JOIN members m ON s.member_id = m.id
                WHERE s.session_id = ?
                ORDER BY s.id
                LIMIT 20
            """, (session_id,))
            
            speeches = cursor.fetchall()
            
            cursor.execute(
                "SELECT DISTINCT section FROM speeches WHERE session_id = ?",
                (session_id,)
            )
            sections_rows = cursor.fetchall()
            sections = ", ".join([row[0] for row in sections_rows if row[0]])
            
            conn.close()
            
            speeches_text = ""
            for speech in speeches:
                name = speech["name"]
                constituency = speech["constituency"]
                party = speech["party"]
                section = speech["section"] or "General"
                content = speech["content"][:300] if speech["content"] else ""
                
                speeches_text += f"{name} ({constituency}, {party}) [{section}]:\n{content}\n\n"
            
            reduced_prompt = f"""You are a parliamentary analyst for Kenya's National Assembly.

        Below is a transcript of a parliamentary session held on {date}.
        Chamber: {chamber}

        The session covered the following sections: {sections}

        Here are the key speeches from this session:

        {speeches_text}

        Write a clear, factual 3-paragraph summary of this session for a Kenyan citizen
        who wants to understand what Parliament discussed and decided. Use plain language.
        Do not use bullet points. Write in prose. Be specific about bills discussed,
        petitions presented, and any notable exchanges."""
                    
            return _call_gemini(client, reduced_prompt)
    
    except Exception as e:
        logger.error(f"Error generating session summary: {e}")
        return "Summary could not be generated."


def summarize_mp(member_id: int, db_path: str) -> str:
    """
    Generates a summary of an MP's parliamentary record.
    
    Args:
        member_id: The ID of the member to summarize
        db_path: Path to the SQLite database
        
    Returns:
        A summary string or fallback message if generation fails
    """
    client = _get_client()
    if not client:
        return "Summary could not be generated."
    
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Fetch member record
        cursor.execute(
            "SELECT name, constituency, party FROM members WHERE id = ?",
            (member_id,)
        )
        member_row = cursor.fetchone()
        
        if not member_row:
            return "Summary could not be generated."
        
        name = member_row["name"]
        constituency = member_row["constituency"]
        party = member_row["party"]
        
        # Fetch speech count and sessions attended
        cursor.execute(
            "SELECT COUNT(DISTINCT id) as speech_count FROM speeches WHERE member_id = ?",
            (member_id,)
        )
        speech_count = cursor.fetchone()["speech_count"]
        
        cursor.execute(
            "SELECT COUNT(DISTINCT session_id) as session_count FROM speeches WHERE member_id = ?",
            (member_id,)
        )
        sessions_attended = cursor.fetchone()["session_count"]
        
        # Fetch top topics
        cursor.execute("""
            SELECT topic, COUNT(*) as count
            FROM speech_topics
            WHERE speech_id IN (SELECT id FROM speeches WHERE member_id = ?)
            GROUP BY topic
            ORDER BY count DESC
            LIMIT 5
        """, (member_id,))
        
        topics_rows = cursor.fetchall()
        topics = ", ".join([row["topic"] for row in topics_rows])
        
        # Fetch 10 most recent speeches with full content
        cursor.execute("""
            SELECT content, section
            FROM speeches
            WHERE member_id = ?
            ORDER BY created_at DESC
            LIMIT 10
        """, (member_id,))
        
        speeches = cursor.fetchall()
        
        conn.close()
        
        # Build speeches text with full content
        speeches_text = ""
        for speech in speeches:
            section = speech["section"] or "General"
            content = speech["content"][:500] if speech["content"] else ""
            speeches_text += f"[{section}]:\n{content}\n\n"
        
        # Build the prompt
        prompt = f"""You are a parliamentary analyst for Kenya's National Assembly.

        Below is the parliamentary record for {name}, Member of Parliament for
        {constituency} ({party}).

        They have given {speech_count} speeches across {sessions_attended} sessions.
        Their most discussed topics are: {topics}.

        Here are samples of their recent speeches:

        {speeches_text}

        Write a 2-paragraph factual assessment of this MP's parliamentary record for
        a Kenyan citizen. Focus on what issues they champion, how active they are,
        and what their contributions suggest about their priorities. Use plain language.
        Do not use bullet points. Write in prose."""
        
        # Try with full content first
        try:
            return _call_gemini(client, prompt)
        except genai_errors.ClientError:
            # Retry with reduced content
            logger.info("Retrying MP summary with reduced content.")
            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT content, section
                FROM speeches
                WHERE member_id = ?
                ORDER BY created_at DESC
                LIMIT 20
            """, (member_id,))
            
            speeches = cursor.fetchall()
            
            conn.close()
            
            speeches_text = ""
            for speech in speeches:
                section = speech["section"] or "General"
                content = speech["content"][:300] if speech["content"] else ""
                speeches_text += f"[{section}]:\n{content}\n\n"
            
            reduced_prompt = f"""You are a parliamentary analyst for Kenya's National Assembly.

            Below is the parliamentary record for {name}, Member of Parliament for
            {constituency} ({party}).

            They have given {speech_count} speeches across {sessions_attended} sessions.
            Their most discussed topics are: {topics}.

            Here are samples of their recent speeches:

            {speeches_text}

            Write a 2-paragraph factual assessment of this MP's parliamentary record for
            a Kenyan citizen. Focus on what issues they champion, how active they are,
            and what their contributions suggest about their priorities. Use plain language.
            Do not use bullet points. Write in prose."""
                        
            return _call_gemini(client, reduced_prompt)
    
    except Exception as e:
        logger.error(f"Error generating MP summary: {e}")
        return "Summary could not be generated."

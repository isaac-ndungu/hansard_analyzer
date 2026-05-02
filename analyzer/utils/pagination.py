from math import ceil


def paginate(items: list, page: int, per_page: int) -> dict:
    """
    Paginates a list of items.

    Args:
        items:    The full list to paginate.
        page:     Current page number, 1-indexed.
        per_page: Items per page.

    Returns a dict with:
        items       — the slice of items for this page
        page        — current page number
        per_page    — items per page
        total       — total number of items
        total_pages — total number of pages
        has_prev    — True if a previous page exists
        has_next    — True if a next page exists
        prev_page   — previous page number or None
        next_page   — next page number or None
        page_range  — page numbers to show in the UI
        start_item  — first item number on this page (for display)
        end_item    — last item number on this page (for display)
    """
    total = len(items)
    total_pages = ceil(total / per_page) if total > 0 else 1
    page = max(1, min(page, total_pages))

    start = (page - 1) * per_page
    end = start + per_page

    if total_pages <= 7:
        page_range = list(range(1, total_pages + 1))
    else:
        around = set(range(max(1, page - 2), min(total_pages, page + 2) + 1))
        edges = {1, total_pages}
        page_range = sorted(around | edges)

    return {
        "items":       items[start:end],
        "page":        page,
        "per_page":    per_page,
        "total":       total,
        "total_pages": total_pages,
        "has_prev":    page > 1,
        "has_next":    page < total_pages,
        "prev_page":   page - 1 if page > 1 else None,
        "next_page":   page + 1 if page < total_pages else None,
        "page_range":  page_range,
        "start_item":  start + 1 if total > 0 else 0,
        "end_item":    min(end, total),
    }